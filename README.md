# AI-Powered Intelligent Medical Document Query Tool

A comprehensive system for uploading, processing, and querying medical PDF documents using AI.

## Architecture

- **Frontend**: Streamlit web interface (`enhanced_app.py`)
- **Backend**: Flask API for document management (`backend/app.py`)
- **Storage**: AWS S3 for PDF storage
- **Processing**: PDF text extraction and categorization

## Quick Start

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
python app.py
```

### 2. Frontend Setup
```bash
pip install -r frontend_requirements.txt
streamlit run enhanced_app.py
```

### 3. Access
- Frontend: http://localhost:8501
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/health

## Features

✅ **Unit 1: Document Management**
- PDF upload and validation (50MB limit)
- Document categorization
- S3 storage integration
- Document inventory management
- RESTful API

🚧 **Coming Soon**
- Unit 2: Search Engine & Query Processing
- Unit 3: Results & Information Extraction
- Unit 4: Chat Interface Enhancement
- Unit 5: Analytics & Intelligence
- Unit 6: Security & Access Control
- Unit 7: System Operations

## API Endpoints

- `POST /api/documents/upload` - Upload PDF
- `GET /api/documents` - List documents
- `GET /api/categories` - Get categories
- `GET /health` - Health check

## Usage

1. Start the backend API
2. Launch the Streamlit frontend
3. Upload PDF documents via the sidebar
4. Select appropriate categories
5. View document inventory
6. Query documents (coming in Unit 2)
Great Malaysia AI Hackathon 2025

# Development
## To run frontend
Install StreamLit
```pip install streamlit```

Run Streamlit
```streamlit run app.py```