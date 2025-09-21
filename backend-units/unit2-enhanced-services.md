# Unit 2: Enhanced Backend Services

## Overview
Organize backend with proper configuration, services layer, data models, and enhanced validation.

## User Stories
- **US-B2.1**: As a developer, I want centralized configuration so that I can manage environments easily
- **US-B2.2**: As a system, I want organized S3 operations so that file management is consistent
- **US-B2.3**: As a system, I want document metadata storage so that I can track uploaded files
- **US-B2.4**: As a developer, I want data models so that document structure is validated
- **US-B2.5**: As a system, I want enhanced file validation so that security is maintained

## Files to Create

### Configuration Management
```
config.py                       # Environment-based configuration
.env.example                    # Environment variables template
```

### Services Layer
```
services/
├── __init__.py
├── s3_service.py              # Centralized S3 operations
└── dynamodb_service.py        # Document metadata storage
```

### Data Models
```
models/
├── __init__.py
└── document.py                # Document data model and validation
```

### Utilities
```
utils/
├── __init__.py
└── validators.py              # Enhanced file validation
```

## Implementation Tasks

### Task 2.1: Configuration Management
**Acceptance Criteria:**
- Environment-based configuration (dev, staging, prod)
- Secure handling of AWS credentials
- Configurable file size limits and allowed extensions
- Database connection settings

**Files:**
- `config.py` - Configuration classes for different environments
- `.env.example` - Template for environment variables

### Task 2.2: S3 Service Layer
**Acceptance Criteria:**
- Centralized S3 upload/download operations
- Proper error handling and logging
- File metadata extraction
- Secure URL generation for downloads

**Files:**
- `services/s3_service.py` - S3Service class with CRUD operations

### Task 2.3: DynamoDB Integration
**Acceptance Criteria:**
- DynamoDB table creation and management
- Document metadata CRUD operations
- Query and filtering capabilities
- Proper indexing for search

**Files:**
- `services/dynamodb_service.py` - DynamoDBService class

### Task 2.4: Document Data Model
**Acceptance Criteria:**
- Document schema definition
- Data validation and serialization
- Type hints and documentation
- Error handling for invalid data

**Files:**
- `models/document.py` - Document class with validation

### Task 2.5: Enhanced Validation
**Acceptance Criteria:**
- File type validation beyond header check
- File size limits enforcement
- Security scanning for malicious content
- MIME type verification

**Files:**
- `utils/validators.py` - Validation functions

## API Enhancements

### Updated Upload Endpoint
```python
POST /api/documents/upload
# Enhanced with:
# - Metadata storage in DynamoDB
# - Improved validation
# - Better error responses
# - File categorization
```

### New Endpoints
```python
GET /api/documents              # List documents with metadata
GET /api/documents/{id}         # Get specific document details
```

## Database Schema

### DynamoDB Table: medical-documents
```json
{
  "id": "uuid",                    # Partition key
  "filename": "string",
  "original_filename": "string",
  "s3_key": "string",
  "size": "number",
  "upload_date": "string",
  "categories": ["string"],
  "content_type": "string",
  "checksum": "string",
  "processed": "boolean",
  "metadata": "object"
}
```

## Environment Variables
```bash
# AWS Configuration
AWS_REGION=ap-southeast-1
S3_BUCKET=echomind-pdf-storage-sg
DYNAMODB_TABLE=medical-documents

# Application Configuration
FLASK_ENV=development
SECRET_KEY=your-secret-key
MAX_FILE_SIZE=52428800  # 50MB
ALLOWED_EXTENSIONS=pdf

# Security
ENABLE_FILE_SCANNING=true
MAX_UPLOAD_RATE=10  # files per minute
```

## Testing Requirements
- Unit tests for all service classes
- Integration tests for DynamoDB operations
- Validation tests for edge cases
- Performance tests for file uploads

## Dependencies
- boto3 (AWS SDK)
- python-magic (file type detection)
- pydantic (data validation)
- pytest (testing framework)

## Estimated Effort: 2-3 days

## Definition of Done
- [ ] All service classes implemented with proper error handling
- [ ] DynamoDB table created and operational
- [ ] Document model with comprehensive validation
- [ ] Enhanced file validation with security checks
- [ ] Unit tests with >80% coverage
- [ ] Integration with existing upload endpoint
- [ ] Documentation updated