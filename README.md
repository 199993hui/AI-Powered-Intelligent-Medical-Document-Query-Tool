# AI-Powered Intelligent Medical Document Query Tool

Transform unstructured medical PDFs into an intelligent, searchable knowledge base. Healthcare professionals can ask natural language questions and receive precise, contextually relevant answers with source citations.

## 🏥 Problem Statement

Healthcare professionals in Malaysia struggle with:
- **Time Waste**: 2-3 hours daily manually searching medical PDFs
- **Information Loss**: Critical details buried in complex PDF structures
- **No Knowledge Synthesis**: Cannot leverage collective institutional knowledge

## 🚀 Solution

AI-powered query tool that enables:
- Natural language search across all medical documents
- Instant answers with source attribution
- ChatGPT-like interface for medical professionals
- Intelligent document processing and indexing

## 🏗️ Architecture

### Backend (Flask API)
- **Document Processing**: PDF extraction with OCR, table detection, medical entity recognition
- **AI Search**: Vector similarity search using OpenSearch with medical embeddings
- **Answer Generation**: Google Gemini API for natural language responses
- **Storage**: AWS S3 for PDFs, OpenSearch for searchable chunks

### Frontend (React TypeScript)
- **Document Management**: Upload, categorize, view, and delete medical PDFs
- **AI Search Assistant**: Chat-like interface for natural language queries
- **Source Attribution**: Direct links to relevant PDF sections with relevance scores

### Cloud Infrastructure
- **AWS S3**: Secure PDF storage with presigned URLs
- **OpenSearch**: Vector search engine for semantic similarity
- **Google Gemini**: AI language model for answer synthesis

## 🛠️ Quick Start

### Prerequisites
- Node.js 16+
- Python 3.9+
- AWS CLI configured
- Google Gemini API key

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt

# Create .env file with required environment variables
cp .env.example .env  # or create manually
# Edit .env file and set the following variables:
# AWS_REGION=ap-southeast-1
# OPENAI_API_KEY=your-google-gemini-api-key
# OPENSEARCH_ENDPOINT=https://your-opensearch-domain.amazonaws.com
# OPENSEARCH_INDEX=medical_docs
# S3_BUCKET=your-pdf-storage-bucket
# DYNAMODB_CHAT_TABLE=chat-history

python app.py
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm start
```

### 3. Access Application
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Health Check**: http://localhost:8000/health

## 📋 Features

### ✅ Document Management
- Bulk PDF upload with drag-and-drop
- Document categorization (Clinical Guidelines, Patient Records, Research Papers, etc.)
- PDF viewing with presigned URLs
- Document deletion with automatic index cleanup
- File validation and metadata extraction

### ✅ AI Search Assistant
- Natural language query processing
- Semantic search across all documents
- Medical entity recognition (drugs, dosages, conditions, procedures)
- Source attribution with relevance scores
- Context-aware answer generation
- Medical abbreviation expansion

### ✅ Advanced Processing
- Multi-modal PDF extraction (text, tables, images)
- OCR for scanned documents
- Medical-specific chunking strategies
- Vector embeddings optimized for medical content
- Intelligent document structure preservation

## 🔧 Configuration

### Environment Variables (.env)
Create a `.env` file in the `backend/` directory with these variables:
```bash
AWS_REGION=ap-southeast-1
OPENAI_API_KEY=your-google-gemini-api-key
OPENSEARCH_ENDPOINT=https://your-opensearch-domain.amazonaws.com
OPENSEARCH_INDEX=medical_docs
S3_BUCKET=your-pdf-storage-bucket
DYNAMODB_CHAT_TABLE=chat-history
```

### Supported Document Categories
- `patient_records` - Patient charts, medical histories
- `clinical_guidelines` - Treatment protocols, best practices
- `research_papers` - Clinical studies, medical literature
- `lab_results` - Laboratory reports, diagnostic results
- `medication_schedules` - Drug information, prescriptions

## 🎯 Usage Examples

### Document Upload
1. Navigate to Document Management
2. Click "Upload Documents"
3. Select multiple PDFs
4. Choose appropriate categories
5. Upload and wait for processing

### AI Queries
```
"What are the contraindications for metformin?"
"Describe the treatment protocol for COVID-19 patients with diabetes"
"What is the recommended dosage for insulin in elderly patients?"
"List the side effects of warfarin and monitoring requirements"
```

## 🚀 AWS Deployment

### Step 1: OpenSearch Service
```bash
cd deployment
./create-opensearch.sh
```

### Step 2: Backend (Elastic Beanstalk)
```bash
./eb-deploy.sh
```

### Step 3: Frontend (S3 + CloudFront)
```bash
npm run build
# Upload build/ to S3 bucket
# Configure CloudFront distribution
```

## 📊 Technical Specifications

- **PDF Processing**: PyMuPDF, pdfplumber, Tesseract OCR
- **AI Models**: Google Gemini 1.5 Flash, SentenceTransformers
- **Search Engine**: OpenSearch with vector similarity
- **Frontend**: React 18, TypeScript, Material-UI
- **Backend**: Flask, Python 3.9+
- **Cloud**: AWS S3, OpenSearch Service, Elastic Beanstalk

## 🔒 Security Features

- Presigned URLs for secure PDF access
- Environment variable configuration
- AWS IAM role-based permissions
- HTTPS enforcement
- Input validation and sanitization

## 🤝 Contributing

Built for the Great Malaysia AI Hackathon 2025. This tool addresses real healthcare challenges by making medical knowledge instantly accessible through AI-powered natural language search.

## 📄 License

This project is developed for healthcare innovation and educational purposes.
