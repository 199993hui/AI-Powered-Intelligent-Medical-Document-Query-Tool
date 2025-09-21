from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3, uuid, json
from datetime import datetime
from dotenv import load_dotenv
from services.chat import ChatService
from services.document import DocumentProcessor
from services.pdf_processor import PDFProcessor
from services.embedding_service import EmbeddingService
from services.opensearch_service import OpenSearchService

import fitz  # PyMuPDF for text + images
import pdfplumber  # For tables
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# AWS Configuration
AWS_REGION = "ap-southeast-1"
S3_BUCKET = "echomind-pdf-storage-sg"

s3 = boto3.client("s3", region_name=AWS_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
opensearch_service = OpenSearchService()

# Initialize AI services with error handling
try:
    chat_service = ChatService()
    print("✅ Chat service initialized")
except Exception as e:
    print(f"⚠️ Chat service initialization failed: {str(e)}")
    chat_service = None

try:
    document_processor = DocumentProcessor()
    print("✅ Document processor initialized")
except Exception as e:
    print(f"⚠️ Document processor initialization failed: {str(e)}")
    document_processor = None

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"})

@app.route('/api/categories', methods=['GET'])
def get_categories():
    categories = [
        'patient_records',
        'clinical_guidelines', 
        'research_papers',
        'lab_results',
        'medication_schedules'
    ]
    return jsonify({"categories": categories})

@app.route('/api/documents', methods=['GET'])
def list_documents():
    try:
        response = s3.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix='medical_documents/'
        )
        
        documents = []
        if 'Contents' in response:
            for obj in response['Contents']:
                # Get object metadata
                head_response = s3.head_object(Bucket=S3_BUCKET, Key=obj['Key'])
                metadata = head_response.get('Metadata', {})
                
                # Extract filename from S3 key
                filename = obj['Key'].split('/')[-1]
                
                doc = {
                    'id': obj['Key'],
                    'filename': metadata.get('original_filename', filename),
                    'size': obj['Size'],
                    'upload_date': obj['LastModified'].isoformat(),
                    'categories': metadata.get('categories', '').split(',') if metadata.get('categories') else [],
                    's3_key': obj['Key']
                }
                documents.append(doc)
        
        # Sort by upload date (newest first)
        documents.sort(key=lambda x: x['upload_date'], reverse=True)
        
        return jsonify({
            'documents': documents,
            'total': len(documents)
        })
        
    except Exception as e:
        print(f"❌ Error listing documents: {str(e)}")
        return jsonify({"error": f"Failed to list documents: {str(e)}"}), 500

@app.route('/api/documents/upload', methods=['POST'])
def upload_document():
    print(f"📤 Upload request received")
    print(f"Files: {list(request.files.keys())}")
    print(f"Form data: {dict(request.form)}")
    
    try:
        if 'file' not in request.files:
            print("❌ No file in request")
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        print(f"📄 File: {file.filename}, Content-Type: {file.content_type}")
        
        if file.filename == '':
            print("❌ Empty filename")
            return jsonify({"error": "No file selected"}), 400
        
        # Get categories from form data
        categories = request.form.getlist('categories')
        print(f"📂 Categories: {categories}")
        
        # Validate PDF
        file_content = file.read()
        print(f"🔍 File size: {len(file_content)} bytes")
        
        if not file_content.startswith(b'%PDF'):
            print("❌ Not a PDF file")
            return jsonify({"error": "File is not a PDF"}), 400
        
        print("✅ PDF validation passed")
        
        # Generate meaningful S3 key with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        doc_id = str(uuid.uuid4())[:8]  # Short ID for readability
        
        # Clean filename for S3
        clean_filename = file.filename.replace(' ', '_').replace('(', '').replace(')', '')
        s3_key = f"medical_documents/{timestamp}_{doc_id}_{clean_filename}"
        print(f"☁️  S3 Key: {s3_key}")
        
        # Upload to S3 with category information
        print(f"☁️  Uploading to S3 bucket: {S3_BUCKET}")
        
        # Prepare S3 tags for categories
        tags = []
        for i, category in enumerate(categories[:10]):  # S3 allows max 10 tags
            tags.append(f"category{i+1}={category}")
        
        tag_string = '&'.join(tags) if tags else ''
        
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType='application/pdf',
            Metadata={
                'categories': ','.join(categories),
                'upload_date': datetime.now().isoformat(),
                'original_filename': file.filename,
                'file_size': str(len(file_content)),
                'document_type': 'medical_pdf'
            },
            Tagging=tag_string
        )
        
        print("✅ S3 upload successful")
        
        # Process document with AI services during upload
        document_id = f"{timestamp}_{doc_id}"
        print(f"🤖 Starting AI processing for document: {document_id}")
        
        try:
            if document_processor and document_processor.embedding_service:
                # Process PDF directly with file content
                processing_result = document_processor.embedding_service.process_pdf_content(
                    pdf_content=file_content,
                    document_metadata={
                        'document_id': document_id,
                        'filename': file.filename,
                        'original_filename': file.filename,
                        'categories': categories,
                        'upload_date': datetime.now().isoformat(),
                        'size': len(file_content),
                        's3_key': s3_key
                    }
                )
            else:
                processing_result = {
                    'status': 'upload_only',
                    'message': 'Document uploaded successfully. AI processing will be available once services are configured.'
                }
            print(f"✅ AI processing completed for document: {document_id}")
        except Exception as processing_error:
            print(f"⚠️ AI processing failed for document {document_id}: {str(processing_error)}")
            processing_result = {
                'status': 'processing_failed',
                'error': str(processing_error),
                'fallback': 'Document uploaded successfully, AI processing will retry later'
            }
        
        return jsonify({
            "success": True,
            "document_id": document_id,
            "message": "Document uploaded and processed successfully",
            "s3_key": s3_key,
            "filename": file.filename,
            "size": len(file_content),
            "categories": categories,
            "upload_date": datetime.now().isoformat(),
            "processing": processing_result,
            "ai_ready": processing_result.get('status') == 'completed'
        })
        
    except Exception as e:
        print(f"❌ Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500

# Chat API Endpoints
@app.route('/api/chat/query', methods=['POST'])
def chat_query():
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        session_id = data.get('sessionId')
        history = data.get('history', [])
        
        if not query:
            return jsonify({"error": "Query is required"}), 400
        
        # Process the chat query
        if not chat_service:
            return jsonify({"error": "AI services are not available. Please ensure AWS Bedrock and OpenSearch are properly configured."}), 503
            
        response = chat_service.process_query(
            query=query,
            session_id=session_id,
            history=history
        )
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Chat query error: {str(e)}")
        return jsonify({"error": f"Chat processing failed: {str(e)}"}), 500

@app.route('/api/chat/history/<session_id>', methods=['GET'])
def get_chat_history(session_id):
    try:
        limit = request.args.get('limit', 20, type=int)
        if not chat_service:
            return jsonify({"error": "Chat service not available"}), 503
            
        history = chat_service.get_chat_history(session_id, limit)
        
        return jsonify({
            "sessionId": session_id,
            "messages": history,
            "count": len(history)
        })
        
    except Exception as e:
        print(f"❌ Chat history error: {str(e)}")
        return jsonify({"error": f"Failed to retrieve chat history: {str(e)}"}), 500

@app.route('/api/chat/feedback', methods=['POST'])
def chat_feedback():
    try:
        data = request.get_json()
        session_id = data.get('sessionId')
        message_id = data.get('messageId')
        feedback = data.get('feedback')
        rating = data.get('rating')
        
        if not all([session_id, message_id, feedback]):
            return jsonify({"error": "sessionId, messageId, and feedback are required"}), 400
        
        if not chat_service:
            return jsonify({"error": "Chat service not available"}), 503
            
        success = chat_service.save_feedback(session_id, message_id, feedback, rating)
        
        return jsonify({"success": success})
        
    except Exception as e:
        print(f"❌ Feedback error: {str(e)}")
        return jsonify({"error": f"Failed to save feedback: {str(e)}"}), 500

@app.route('/api/documents/process/<document_id>', methods=['POST'])
def process_document(document_id):
    try:
        if not document_processor:
            return jsonify({"error": "Document processor not available"}), 503
            
        # Check processing status
        status = document_processor.get_processing_status(document_id)
        return jsonify(status)
        
    except Exception as e:
        print(f"❌ Document processing error: {str(e)}")
        return jsonify({"error": f"Processing check failed: {str(e)}"}), 500

# Enhanced Search Endpoints
@app.route('/api/search', methods=['POST'])
def search_documents():
    try:
        if not document_processor:
            return jsonify({"error": "Document processor not available"}), 503
            
        data = request.get_json()
        query = data.get('query', '').strip()
        filters = data.get('filters', {})
        limit = data.get('limit', 10)
        
        if not query:
            return jsonify({"error": "Query is required"}), 400
        
        # Perform enhanced search
        search_results = document_processor.search_documents(query, filters, limit)
        
        return jsonify(search_results)
        
    except Exception as e:
        print(f"❌ Search error: {str(e)}")
        return jsonify({"error": f"Search failed: {str(e)}"}), 500

@app.route('/api/search/suggestions', methods=['GET'])
def get_search_suggestions():
    try:
        if not document_processor:
            return jsonify({"suggestions": []})
            
        partial_query = request.args.get('q', '').strip()
        
        if len(partial_query) < 2:
            return jsonify({"suggestions": []})
        
        suggestions = document_processor.get_search_suggestions(partial_query)
        
        return jsonify({"suggestions": suggestions})
        
    except Exception as e:
        print(f"❌ Suggestions error: {str(e)}")
        return jsonify({"suggestions": []})

@app.route('/api/documents/<document_id>/content', methods=['GET'])
def get_document_content(document_id):
    try:
        if not document_processor:
            return jsonify({"error": "Document processor not available"}), 503
            
        content = document_processor.get_document_content(document_id)
        
        if 'error' in content:
            return jsonify(content), 404
            
        return jsonify(content)
        
    except Exception as e:
        print(f"❌ Document content error: {str(e)}")
        return jsonify({"error": f"Failed to get document content: {str(e)}"}), 500

@app.route('/api/search/stats', methods=['GET'])
def get_search_stats():
    try:
        if not document_processor:
            return jsonify({"error": "Document processor not available"}), 503
            
        stats = document_processor.get_search_stats()
        
        return jsonify(stats)
        
    except Exception as e:
        print(f"❌ Search stats error: {str(e)}")
        return jsonify({"error": f"Failed to get search stats: {str(e)}"}), 500



@app.route('/api/opensearch/verify/<filename>', methods=['GET'])
def verify_opensearch_upload(filename):
    """Check if a PDF was successfully stored in OpenSearch"""
    try:
        if not document_processor or not document_processor.embedding_service:
            return jsonify({"error": "Document processor not available"}), 503
            
        opensearch_service = document_processor.embedding_service.opensearch_service
        verification = opensearch_service.verify_upload(filename)
        
        return jsonify(verification)
        
    except Exception as e:
        print(f"❌ OpenSearch verification error: {str(e)}")
        return jsonify({"error": f"Verification failed: {str(e)}"}), 500

@app.route('/api/opensearch/stats', methods=['GET'])
def get_opensearch_stats():
    """Get OpenSearch index statistics"""
    try:
        if not document_processor or not document_processor.embedding_service:
            return jsonify({"error": "Document processor not available"}), 503
            
        opensearch_service = document_processor.embedding_service.opensearch_service
        stats = opensearch_service.get_index_stats()
        
        return jsonify(stats)
        
    except Exception as e:
        print(f"❌ OpenSearch stats error: {str(e)}")
        return jsonify({"error": f"Stats retrieval failed: {str(e)}"}), 500

@app.route('/api/system/status', methods=['GET'])
def get_system_status():
    """Get overall system status for AI services"""
    try:
        if not chat_service:
            return jsonify({"error": "Chat service not available"}), 503
            
        status = chat_service.get_system_status()
        
        return jsonify({
            'status': 'operational' if all([status['bedrock'], status['opensearch']]) else 'limited',
            'services': status,
            'ready_for_queries': status.get('documents_available', 0) > 0 and status['bedrock'] and status['opensearch'],
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ System status error: {str(e)}")
        return jsonify({"error": f"Status check failed: {str(e)}"}), 500

@app.route('/api/chat/natural-query', methods=['POST'])
def natural_language_query():
    """Enhanced natural language query endpoint with document context"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        session_id = data.get('sessionId')
        include_history = data.get('includeHistory', True)
        
        if not query:
            return jsonify({"error": "Query is required"}), 400
        
        if not chat_service:
            return jsonify({"error": "AI services are not available"}), 503
        
        # Get conversation history if requested
        history = []
        if include_history and session_id:
            history = chat_service.get_chat_history(session_id, limit=5)
        
        # Process the natural language query
        response = chat_service.process_query(
            query=query,
            session_id=session_id,
            history=history
        )
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Natural query error: {str(e)}")
        return jsonify({"error": f"Query processing failed: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)