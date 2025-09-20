#!/usr/bin/env python3
"""
Test frontend-backend connection
"""

import requests
import json

BACKEND_URL = "http://localhost:8000"

def test_backend_endpoints():
    """Test all backend endpoints"""
    print("🔗 Testing Backend Endpoints...")
    
    endpoints = [
        ("/health", "GET"),
        ("/api/categories", "GET"),
        ("/api/documents", "GET"),
        ("/api/search/index-status", "GET")
    ]
    
    for endpoint, method in endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{BACKEND_URL}{endpoint}")
            
            if response.status_code == 200:
                print(f"✅ {method} {endpoint} - Working")
            else:
                print(f"❌ {method} {endpoint} - Failed ({response.status_code})")
                
        except Exception as e:
            print(f"❌ {method} {endpoint} - Error: {e}")

def test_upload_with_real_pdf():
    """Test upload with a real PDF file"""
    print("\n📤 Testing Upload with Real PDF...")
    
    # Create a minimal valid PDF
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test Document) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000189 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
284
%%EOF"""
    
    try:
        files = {
            'file': ('frontend_test.pdf', pdf_content, 'application/pdf')
        }
        data = {
            'categories': json.dumps(['patient_records'])
        }
        
        response = requests.post(f"{BACKEND_URL}/api/documents/upload", 
                               files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Frontend upload test successful!")
            print(f"  Document ID: {result.get('document_id')}")
            print(f"  S3 Key: {result.get('s3_key')}")
            return True
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return False

def main():
    """Run frontend-backend tests"""
    print("🧪 Testing Frontend-Backend Connection")
    print("=" * 45)
    
    # Test backend endpoints
    test_backend_endpoints()
    
    # Test upload
    test_upload_with_real_pdf()
    
    print("\n💡 If upload works here but not in Streamlit:")
    print("1. Check browser console for errors")
    print("2. Verify Streamlit is connecting to http://localhost:8000")
    print("3. Check for CORS issues")
    print("4. Restart both backend and frontend")

if __name__ == "__main__":
    main()