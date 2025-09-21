# Unit 4: API Expansion

## Overview
Complete REST API with full CRUD operations, advanced filtering, bulk operations, and comprehensive document management.

## User Stories
- **US-B4.1**: As a user, I want to list documents so that I can see my uploaded files
- **US-B4.2**: As a user, I want to filter documents so that I can find specific files
- **US-B4.3**: As a user, I want to download documents so that I can access my files
- **US-B4.4**: As a user, I want to search documents so that I can query content
- **US-B4.5**: As a user, I want bulk operations so that I can manage multiple files

## API Endpoints to Implement

### Document Management
```python
GET    /api/documents              # List with filtering and pagination
GET    /api/documents/{id}         # Get specific document details
PUT    /api/documents/{id}         # Update document metadata
DELETE /api/documents/{id}         # Delete document and S3 file
GET    /api/documents/{id}/download # Download original file
```

### Search and Query
```python
POST   /api/search                 # Full-text search with filters
GET    /api/search/recent          # Recent search queries
GET    /api/search/suggestions     # Search term suggestions
```

### Bulk Operations
```python
POST   /api/documents/bulk-delete  # Delete multiple documents
POST   /api/documents/bulk-update  # Update multiple documents
POST   /api/documents/bulk-export  # Export document metadata
```

### Categories and Metadata
```python
GET    /api/categories             # Get available categories
PUT    /api/documents/{id}/categories # Update document categories
GET    /api/stats                  # System statistics
```

## Implementation Tasks

### Task 4.1: Document Listing and Filtering
**Acceptance Criteria:**
- Pagination support (page, limit parameters)
- Sorting by multiple fields (filename, date, size, confidence)
- Filtering by categories, date range, file size, processing status
- Search within filenames and metadata
- Response time <200ms for typical queries

**Query Parameters:**
```
GET /api/documents?
  page=1&
  limit=20&
  sort_by=upload_date&
  sort_order=desc&
  categories=patient_records,lab_results&
  date_from=2024-01-01&
  date_to=2024-12-31&
  size_min=1024&
  size_max=10485760&
  processed=true&
  search=diabetes
```

### Task 4.2: Document Retrieval and Download
**Acceptance Criteria:**
- Secure document access with proper authorization
- Efficient file streaming for large documents
- Proper HTTP headers for file downloads
- Access logging for audit purposes

**Features:**
- Presigned S3 URLs for secure downloads
- Content-Type and Content-Disposition headers
- Range request support for partial downloads
- Download tracking and analytics

### Task 4.3: Document Updates and Deletion
**Acceptance Criteria:**
- Safe document deletion with confirmation
- Metadata updates without file re-upload
- Cascade deletion (S3 file + DynamoDB record)
- Soft delete option for data recovery

**Features:**
- Document metadata updates (categories, tags)
- Soft delete with recovery option
- Permanent deletion with confirmation
- Audit trail for all modifications

### Task 4.4: Advanced Search Implementation
**Acceptance Criteria:**
- Full-text search across document content
- Medical terminology matching
- Faceted search with filters
- Search result ranking and relevance scoring
- Search analytics and suggestions

**Search Features:**
- Boolean search operators (AND, OR, NOT)
- Phrase matching with quotes
- Wildcard and fuzzy matching
- Medical synonym matching
- Search result highlighting

### Task 4.5: Bulk Operations
**Acceptance Criteria:**
- Batch processing with progress tracking
- Error handling for partial failures
- Asynchronous processing for large operations
- Detailed operation results and logs

**Bulk Features:**
- Multi-document selection and operations
- Progress tracking with WebSocket updates
- Rollback capability for failed operations
- Export functionality (CSV, JSON formats)

## Request/Response Formats

### Document List Response
```json
{
  "documents": [
    {
      "id": "uuid",
      "filename": "patient_record_001.pdf",
      "categories": ["patient_records"],
      "upload_date": "2024-01-15T10:30:00Z",
      "size": 2048576,
      "processed": true,
      "extraction_confidence": 0.92,
      "s3_key": "documents/uuid/filename.pdf"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "pages": 8
  },
  "filters_applied": {
    "categories": ["patient_records"],
    "date_range": "2024-01-01 to 2024-12-31"
  }
}
```

### Search Request/Response
```json
// Request
{
  "query": "diabetes treatment protocol",
  "filters": {
    "categories": ["clinical_guidelines"],
    "date_from": "2024-01-01"
  },
  "options": {
    "highlight": true,
    "limit": 10,
    "offset": 0
  }
}

// Response
{
  "query": "diabetes treatment protocol",
  "total_results": 25,
  "results": [
    {
      "document_id": "uuid",
      "filename": "diabetes_protocol_v2.pdf",
      "relevance_score": 0.95,
      "matched_content": "...diabetes treatment protocol...",
      "highlights": ["diabetes", "treatment", "protocol"],
      "categories": ["clinical_guidelines"],
      "upload_date": "2024-01-15T10:30:00Z"
    }
  ],
  "facets": {
    "categories": {
      "clinical_guidelines": 15,
      "patient_records": 8,
      "research_papers": 2
    },
    "upload_year": {
      "2024": 20,
      "2023": 5
    }
  }
}
```

### Bulk Operation Response
```json
{
  "operation_id": "bulk_delete_uuid",
  "status": "completed",
  "total_items": 10,
  "processed": 8,
  "successful": 7,
  "failed": 1,
  "results": [
    {
      "document_id": "uuid1",
      "status": "success",
      "message": "Document deleted successfully"
    },
    {
      "document_id": "uuid2",
      "status": "error",
      "message": "Document not found"
    }
  ],
  "started_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:32:15Z"
}
```

## Error Handling

### Standard Error Response
```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document with ID 'uuid' not found",
    "details": {
      "document_id": "uuid",
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
}
```

### Error Codes
- `DOCUMENT_NOT_FOUND` (404)
- `INVALID_PARAMETERS` (400)
- `UNAUTHORIZED_ACCESS` (403)
- `FILE_TOO_LARGE` (413)
- `PROCESSING_ERROR` (500)
- `RATE_LIMIT_EXCEEDED` (429)

## Performance Requirements
- Document listing: <200ms response time
- Search queries: <500ms response time
- File downloads: Stream initiation <100ms
- Bulk operations: Progress updates every 5 seconds

## Security Considerations
- Input validation and sanitization
- Rate limiting per user/IP
- Access logging and monitoring
- Secure file access with presigned URLs
- SQL injection prevention

## Testing Requirements
- Unit tests for all API endpoints
- Integration tests with database operations
- Performance tests for large datasets
- Security tests for input validation
- Load tests for concurrent operations

## Dependencies
- Unit 2 completion (Enhanced services)
- Unit 3 completion (AI integration for search)
- Frontend integration for testing

## Estimated Effort: 3-4 days

## Definition of Done
- [ ] All CRUD operations implemented and tested
- [ ] Advanced filtering and pagination working
- [ ] Search functionality with relevance scoring
- [ ] Bulk operations with progress tracking
- [ ] Comprehensive error handling
- [ ] Performance requirements met
- [ ] Security measures implemented
- [ ] API documentation complete
- [ ] Integration tests passing