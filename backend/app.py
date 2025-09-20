from flask import Flask, request, jsonify
import boto3
import hashlib
import uuid
import json
from datetime import datetime
import PyPDF2
from io import BytesIO
from dynamodb_service import DynamoDBService

app = Flask(__name__)

# S3 Configuration
s3 = boto3.client("s3")
BUCKET = "echomind-pdf-storage"

# DynamoDB service
db_service = DynamoDBService()

# Document categories
CATEGORIES = [
    "patient_records", "clinical_guidelines", "research_papers", 
    "lab_results", "medication_schedules"
]

def validate_pdf(file_content):
    """Validate PDF file"""
    if len(file_content) > 50 * 1024 * 1024:  # 50MB limit
        return False, "File too large (>50MB)"
    
    # Check if content starts with PDF header
    if not file_content.startswith(b'%PDF'):
        return False, "File is not a PDF"
    
    # Optional: Use magic library if available
    try:
        import magic
        file_type = magic.from_buffer(file_content, mime=True)
        if file_type != 'application/pdf':
            return False, "File is not a PDF"
    except ImportError:
        print("Warning: python-magic not available, using basic PDF validation")
    except Exception as e:
        print(f"Warning: Magic validation failed: {e}")
    
    return True, "Valid"

def calculate_hash(content):
    """Calculate SHA-256 hash"""
    return hashlib.sha256(content).hexdigest()

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "document-management"})

@app.route('/api/categories', methods=['GET'])
def get_categories():
    return jsonify({"categories": CATEGORIES})

@app.route('/api/documents/upload', methods=['POST'])
def upload_document():
    print(f"📤 Upload request received")
    print(f"Files: {list(request.files.keys())}")
    print(f"Form data: {dict(request.form)}")
    
    try:
        # Check if file is present
        if 'file' not in request.files:
            print("❌ No file in request")
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        print(f"📄 File: {file.filename}, Content-Type: {file.content_type}")
        
        if file.filename == '':
            print("❌ Empty filename")
            return jsonify({"error": "No file selected"}), 400
        
        # Get categories
        categories_str = request.form.get('categories', '[]')
        try:
            categories = json.loads(categories_str)
        except:
            return jsonify({"error": "Invalid categories format"}), 400
        
        # Validate categories
        for cat in categories:
            if cat not in CATEGORIES:
                return jsonify({"error": f"Invalid category: {cat}"}), 400
        
        # Read file content
        file_content = file.read()
        
        # Validate PDF
        print(f"🔍 Validating PDF: {len(file_content)} bytes")
        is_valid, message = validate_pdf(file_content)
        if not is_valid:
            print(f"❌ PDF validation failed: {message}")
            return jsonify({"error": message}), 400
        print("✅ PDF validation passed")
        
        # Generate unique ID and S3 key
        doc_id = str(uuid.uuid4())
        s3_key = f"documents/{doc_id}/{file.filename}"
        content_hash = calculate_hash(file_content)
        
        # Upload to S3
        print(f"☁️  Uploading to S3: {s3_key}")
        s3.put_object(
            Bucket=BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType='application/pdf'
        )
        print("✅ S3 upload successful")
        
        # Create metadata
        metadata = {
            "id": doc_id,
            "filename": file.filename,
            "original_filename": file.filename,
            "s3_key": s3_key,
            "size": len(file_content),
            "upload_date": datetime.now().isoformat(),
            "categories": categories,
            "version": 1,
            "content_hash": content_hash,
            "processed": False
        }
        
        # Store metadata in DynamoDB
        if not db_service.save_document(metadata):
            return jsonify({"error": "Failed to save document metadata"}), 500
        
        # Refresh search index for new document
        try:
            from document_search_service import DocumentSearchService
            search_service = DocumentSearchService()
            search_service.refresh_index()
            print(f"✅ Search index refreshed after uploading {file.filename}")
        except Exception as e:
            print(f"⚠️  Warning: Failed to refresh search index: {e}")
        
        return jsonify({
            "success": True,
            "document_id": doc_id,
            "message": "Document uploaded successfully",
            "s3_key": s3_key
        })
        
    except Exception as e:
        print(f"❌ Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500

@app.route('/api/documents', methods=['GET'])
def list_documents():
    documents = db_service.list_documents()
    return jsonify({
        "documents": documents,
        "total": len(documents)
    })

@app.route('/api/documents/<document_id>', methods=['GET'])
def get_document(document_id):
    document = db_service.get_document(document_id)
    if not document:
        return jsonify({"error": "Document not found"}), 404
    
    return jsonify(document)

@app.route('/api/documents/<document_id>/categories', methods=['PUT'])
def update_categories(document_id):
    document = db_service.get_document(document_id)
    if not document:
        return jsonify({"error": "Document not found"}), 404
    
    try:
        data = request.get_json()
        categories = data.get('categories', [])
        
        # Validate categories
        for cat in categories:
            if cat not in CATEGORIES:
                return jsonify({"error": f"Invalid category: {cat}"}), 400
        
        # Update categories in DynamoDB
        if db_service.update_document(document_id, {'categories': categories}):
            return jsonify({"message": "Categories updated successfully"})
        else:
            return jsonify({"error": "Failed to update categories"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/documents/<document_id>', methods=['DELETE'])
def delete_document(document_id):
    document = db_service.get_document(document_id)
    if not document:
        return jsonify({"error": "Document not found"}), 404
    
    try:
        # Delete from S3
        s3_key = document['s3_key']
        s3.delete_object(Bucket=BUCKET, Key=s3_key)
        
        # Delete from DynamoDB
        if db_service.delete_document(document_id):
            return jsonify({"message": "Document deleted successfully"})
        else:
            return jsonify({"error": "Failed to delete document metadata"}), 500
        
    except Exception as e:
        return jsonify({"error": f"Delete failed: {str(e)}"}), 500

# Search Engine Endpoints
@app.route('/api/search/query', methods=['POST'])
def search_query():
    """Process natural language search query with enhanced medical understanding"""
    try:
        data = request.get_json()
        query_text = data.get('query', '').strip()
        
        if not query_text:
            return jsonify({'error': 'Query is required'}), 400
        
        from document_search_service import DocumentSearchService
        search_service = DocumentSearchService()
        
        # Enhanced medical entity extraction
        medical_conditions = ['diabetes', 'hypertension', 'heart disease', 'stroke', 'cancer', 'pneumonia']
        medications = ['insulin', 'metformin', 'lisinopril', 'aspirin', 'warfarin']
        procedures = ['surgery', 'biopsy', 'catheterization', 'endoscopy']
        
        found_conditions = [term for term in medical_conditions if term in query_text.lower()]
        found_medications = [term for term in medications if term in query_text.lower()]
        found_procedures = [term for term in procedures if term in query_text.lower()]
        
        # Search with original query terms
        query_words = [word.strip() for word in query_text.split() if len(word.strip()) > 2]
        
        results = search_service.search_documents(
            query_terms=query_words,
            expanded_query=query_text,
            medical_entities={
                'conditions': found_conditions,
                'medications': found_medications,
                'procedures': found_procedures
            }
        )
        
        return jsonify({
            'query_analysis': {
                'original_query': query_text,
                'query_terms': query_words,
                'medical_entities': {
                    'conditions': found_conditions,
                    'medications': found_medications,
                    'procedures': found_procedures
                },
                'intent': 'medical_search'
            },
            'results': results,
            'total_results': len(results)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search/suggestions', methods=['GET'])
def get_suggestions():
    """Get query suggestions"""
    try:
        partial_query = request.args.get('q', '')
        
        suggestions = [
            f"What medications for {partial_query}",
            f"Show {partial_query} treatment protocols",
            f"Find {partial_query} lab results",
            f"Patient records containing {partial_query}",
            f"{partial_query} clinical guidelines"
        ]
        
        return jsonify({'suggestions': suggestions[:5]})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search/index-status', methods=['GET'])
def get_index_status():
    """Get document index status"""
    try:
        from document_search_service import DocumentSearchService
        search_service = DocumentSearchService()
        stats = search_service.get_index_stats()
        
        return jsonify({
            'indexed_documents': stats['total_documents'],
            'total_content_length': stats['total_content_length'],
            'average_document_size': stats['average_document_size'],
            'last_updated': stats['last_updated']
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)