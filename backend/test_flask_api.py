import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    response = requests.get(f"{BASE_URL}/health")
    print("Health Check:", response.json())

def test_categories():
    response = requests.get(f"{BASE_URL}/api/categories")
    print("Categories:", response.json())

def test_upload(pdf_file_path):
    """Test document upload - requires a PDF file"""
    try:
        with open(pdf_file_path, 'rb') as f:
            files = {'file': (pdf_file_path, f, 'application/pdf')}
            data = {'categories': json.dumps(['patient_records', 'lab_results'])}
            
            response = requests.post(f"{BASE_URL}/api/documents/upload", files=files, data=data)
            print("Upload Response:", response.json())
            
            if response.status_code == 200:
                return response.json().get('document_id')
    except FileNotFoundError:
        print(f"PDF file not found: {pdf_file_path}")
    except Exception as e:
        print(f"Upload error: {e}")
    return None

def test_list_documents():
    response = requests.get(f"{BASE_URL}/api/documents")
    print("Documents List:", response.json())

def test_get_document(doc_id):
    if doc_id:
        response = requests.get(f"{BASE_URL}/api/documents/{doc_id}")
        print("Document Details:", response.json())

def test_update_categories(doc_id):
    if doc_id:
        data = {"categories": ["clinical_guidelines", "research_papers"]}
        response = requests.put(f"{BASE_URL}/api/documents/{doc_id}/categories", json=data)
        print("Update Categories:", response.json())

if __name__ == "__main__":
    print("Testing Flask Document Management API")
    print("=" * 50)
    
    test_health()
    test_categories()
    test_list_documents()
    
    # Uncomment and provide a PDF file path to test upload
    # doc_id = test_upload("sample.pdf")
    # test_get_document(doc_id)
    # test_update_categories(doc_id)