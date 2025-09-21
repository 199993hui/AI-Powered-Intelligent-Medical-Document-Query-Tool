# Backend Deployment Plan - AWS Medical Document Query Tool

## 📁 File Repository Structure

```
backend/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── config.py                   # Configuration management
├── services/
│   ├── __init__.py
│   ├── s3_service.py          # S3 operations
│   ├── dynamodb_service.py    # Document metadata storage
│   ├── bedrock_service.py     # AI document processing
│   └── search_service.py      # Document search functionality
├── models/
│   ├── __init__.py
│   └── document.py            # Document data models
├── utils/
│   ├── __init__.py
│   ├── validators.py          # File validation utilities
│   └── helpers.py             # Common helper functions
├── tests/
│   ├── __init__.py
│   ├── test_upload.py         # Upload API tests
│   └── test_services.py       # Service layer tests
├── deployment/
│   ├── Dockerfile             # Container configuration
│   ├── docker-compose.yml     # Local development
│   ├── eb-config/             # Elastic Beanstalk config
│   │   └── .ebextensions/
│   └── lambda/                # Lambda deployment files
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
└── README.md                  # Deployment instructions
```

## 🚀 AWS Deployment Options

### Option 1: AWS Elastic Beanstalk (Recommended)
- **Pros**: Easy deployment, auto-scaling, load balancing
- **Cons**: Less control over infrastructure
- **Cost**: Low to medium
- **Files Needed**:
  - `deployment/eb-config/.ebextensions/python.config`
  - `deployment/requirements.txt`
  - `deployment/.platform/hooks/`

### Option 2: AWS Lambda + API Gateway
- **Pros**: Serverless, pay-per-use, auto-scaling
- **Cons**: Cold starts, 15min timeout limit
- **Cost**: Very low for sporadic usage
- **Files Needed**:
  - `deployment/lambda/lambda_function.py`
  - `deployment/lambda/serverless.yml`
  - `deployment/lambda/requirements.txt`

### Option 3: AWS ECS Fargate
- **Pros**: Container-based, scalable, managed
- **Cons**: More complex setup
- **Cost**: Medium
- **Files Needed**:
  - `deployment/Dockerfile`
  - `deployment/ecs-task-definition.json`
  - `deployment/ecs-service.json`

## 📋 Implementation Phases

### Phase 1: Core Backend Structure ✅ CURRENT
- [x] Basic Flask app with upload API
- [x] S3 integration for file storage
- [x] CORS configuration
- [x] Basic error handling

### Phase 2: Enhanced Backend Services
- [ ] **config.py** - Environment-based configuration
- [ ] **services/s3_service.py** - Centralized S3 operations
- [ ] **services/dynamodb_service.py** - Document metadata storage
- [ ] **models/document.py** - Data models and validation
- [ ] **utils/validators.py** - File validation and security

### Phase 3: AI Integration
- [ ] **services/bedrock_service.py** - AWS Bedrock for document processing
- [ ] **services/search_service.py** - Document search and indexing
- [ ] Enhanced document processing pipeline

### Phase 4: API Expansion
- [ ] Document listing and filtering APIs
- [ ] Document retrieval and download APIs
- [ ] Search and query APIs
- [ ] Bulk operations APIs

### Phase 5: Deployment Preparation
- [ ] **Dockerfile** - Container configuration
- [ ] **docker-compose.yml** - Local development environment
- [ ] **deployment/eb-config/** - Elastic Beanstalk configuration
- [ ] Environment variable management
- [ ] Security and IAM role configuration

### Phase 6: Testing & Monitoring
- [ ] **tests/** - Comprehensive test suite
- [ ] Health check endpoints
- [ ] Logging and monitoring setup
- [ ] Performance optimization

## 🔧 Required AWS Resources

### Storage & Database
- **S3 Bucket**: `echomind-pdf-storage-sg` (ap-southeast-1) ✅ EXISTS
- **DynamoDB Table**: `medical-documents` (document metadata)
- **CloudWatch**: Logging and monitoring

### Compute & Networking
- **Elastic Beanstalk Environment** OR **Lambda Functions**
- **API Gateway** (if using Lambda)
- **VPC** (optional, for enhanced security)
- **Application Load Balancer** (if using ECS/EB)

### AI & Search
- **Amazon Bedrock**: Document processing and AI features
- **Amazon OpenSearch**: Advanced document search (optional)
- **Amazon Textract**: PDF text extraction (optional)

### Security & Access
- **IAM Roles**: Service permissions
- **Secrets Manager**: API keys and credentials
- **CloudFront**: CDN for static assets (optional)

## 🔐 Environment Variables

```bash
# AWS Configuration
AWS_REGION=ap-southeast-1
S3_BUCKET=echomind-pdf-storage-sg
DYNAMODB_TABLE=medical-documents

# Application Configuration
FLASK_ENV=production
SECRET_KEY=your-secret-key
MAX_FILE_SIZE=50MB
ALLOWED_EXTENSIONS=pdf

# AI Services (Optional)
BEDROCK_MODEL_ID=anthropic.claude-v2
TEXTRACT_ENABLED=true

# Database (if using RDS)
DATABASE_URL=postgresql://user:pass@host:5432/db
```

## 📦 Deployment Commands

### Elastic Beanstalk Deployment
```bash
# Initialize EB application
eb init medical-document-api --region ap-southeast-1

# Create environment
eb create production --instance-type t3.small

# Deploy application
eb deploy
```

### Lambda Deployment
```bash
# Package and deploy
zip -r deployment.zip . -x "tests/*" "deployment/*"
aws lambda update-function-code --function-name medical-doc-api --zip-file fileb://deployment.zip
```

### Docker Deployment
```bash
# Build image
docker build -t medical-doc-api .

# Run locally
docker-compose up

# Deploy to ECS
aws ecs update-service --cluster medical-docs --service api-service
```

## 🎯 Next Steps

1. **Immediate**: Implement Phase 2 (Enhanced Backend Services)
2. **Short-term**: Add DynamoDB integration and document management APIs
3. **Medium-term**: Integrate AWS Bedrock for AI features
4. **Long-term**: Deploy to production with monitoring and scaling

## 💰 Cost Estimation (Monthly)

### Small Scale (< 1000 documents/month)
- **Elastic Beanstalk**: $15-30
- **S3 Storage**: $1-5
- **DynamoDB**: $1-3
- **Total**: ~$20-40/month

### Medium Scale (< 10,000 documents/month)
- **Elastic Beanstalk**: $30-60
- **S3 Storage**: $5-15
- **DynamoDB**: $5-10
- **Bedrock**: $10-25
- **Total**: ~$50-110/month

---

**Status**: Ready to implement Phase 2 - Enhanced Backend Services