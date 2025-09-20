# Backend API - Unit 1: Document Management

Flask API for medical PDF document management and processing.

## Setup

1. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. Configure AWS credentials (S3 access)

3. Run the Flask API:
```bash
python app.py
```

## API Endpoints

- `GET /health` - Health check
- `GET /api/categories` - Get document categories
- `POST /api/documents/upload` - Upload PDF
- `GET /api/documents` - List documents
- `GET /api/documents/<id>` - Get document details
- `PUT /api/documents/<id>/categories` - Update categories
- `DELETE /api/documents/<id>` - Delete document

## Test

```bash
python test_flask_api.py
```

The API runs on http://localhost:8000