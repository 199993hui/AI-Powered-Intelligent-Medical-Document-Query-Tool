from flask import Flask, request, jsonify
import boto3
import hashlib
import uuid
import json
from datetime import datetime
import PyPDF2
import magic
from io import BytesIO
from search_engine import MedicalSearchEngine

app = Flask(__name__)

# S3 Configuration
s3 = boto3.client("s3")
BUCKET = "echomind-pdf-storage"

# Initialize search engine
search_engine = MedicalSearchEngine()

# In-memory storage (replace with database)
documents = {}

# Document categories
CATEGORIES = [
    "patient_records", "clinical_guidelines", "research_papers", 
    "lab_results", "medication_schedules"
]

def validate_pdf(file_content):
    """Validate PDF file"""
    if len(file_content) > 50 * 1024 * 1024:  # 50MB limit
        return False, "File too large (>50MB)"
    
    try:
        file_type = magic.from_buffer(file_content, mime=True)
        if file_type != 'application/pdf':
            return False, "File is not a PDF"
    except:
        return False, "Unable to determine file type"
    
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
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
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
        is_valid, message = validate_pdf(file_content)
        if not is_valid:
            return jsonify({"error": message}), 400
        
        # Generate unique ID and S3 key
        doc_id = str(uuid.uuid4())
        s3_key = f"documents/{doc_id}/{file.filename}"
        content_hash = calculate_hash(file_content)
        
        # Upload to S3
        s3.put_object(
            Bucket=BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType='application/pdf'
        )
        
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
        
        # Store metadata
        documents[doc_id] = metadata
        
        return jsonify({
            "success": True,
            "document_id": doc_id,
            "message": "Document uploaded successfully",
            "s3_key": s3_key
        })
        
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500

@app.route('/api/documents', methods=['GET'])
def list_documents():
    return jsonify({
        "documents": list(documents.values()),
        "total": len(documents)
    })

@app.route('/api/documents/<document_id>', methods=['GET'])
def get_document(document_id):
    if document_id not in documents:
        return jsonify({"error": "Document not found"}), 404
    
    return jsonify(documents[document_id])

@app.route('/api/documents/<document_id>/categories', methods=['PUT'])
def update_categories(document_id):
    if document_id not in documents:
        return jsonify({"error": "Document not found"}), 404
    
    try:
        data = request.get_json()
        categories = data.get('categories', [])
        
        # Validate categories
        for cat in categories:
            if cat not in CATEGORIES:
                return jsonify({"error": f"Invalid category: {cat}"}), 400
        
        # Update categories
        documents[document_id]['categories'] = categories
        
        return jsonify({"message": "Categories updated successfully"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/documents/<document_id>', methods=['DELETE'])
def delete_document(document_id):
    if document_id not in documents:
        return jsonify({"error": "Document not found"}), 404
    
    try:
        # Delete from S3
        s3_key = documents[document_id]['s3_key']
        s3.delete_object(Bucket=BUCKET, Key=s3_key)
        
        # Remove from memory
        del documents[document_id]
        
        return jsonify({"message": "Document deleted successfully"})
        
    except Exception as e:
        return jsonify({"error": f"Delete failed: {str(e)}"}), 500

# Search Engine Endpoints
@app.route('/api/search/query', methods=['POST'])
def search_query():
    """Process natural language search query"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Process query using search engine
        processed_query = search_engine.process_query(query)
        
        if processed_query.get('status') == 'error':
            return jsonify(processed_query), 500
        
        # Search documents
        search_results = search_engine.search_documents(processed_query)
        
        return jsonify({
            'query_analysis': processed_query,
            'results': search_results,
            'total_results': len(search_results)
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)