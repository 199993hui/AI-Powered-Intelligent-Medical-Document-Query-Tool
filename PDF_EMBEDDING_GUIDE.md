# PDF Extraction and Embedding for Chatbot Queries

This guide explains how PDFs in S3 are extracted and embedded for intelligent chatbot queries in the Medical Document Query Tool.

## Overview

The system processes medical PDFs through a comprehensive pipeline that extracts content, creates embeddings, and enables semantic search for chatbot queries.

## Architecture

```
S3 PDF → Extract Content → Create Chunks → Generate Embeddings → Store in OpenSearch → Query for Chat
```

## Components

### 1. PDF Extraction (`pdf_extractor.py`)

**Purpose**: Extract comprehensive content from PDF files

**Features**:
- Text extraction using PyPDF2
- Table/form extraction using AWS Textract
- Medical entity recognition (medications, conditions, procedures, vital signs, lab results)
- Document section identification (chief complaint, history, assessment, plan)
- Metadata extraction

**Key Methods**:
```python
def extract_comprehensive_content(pdf_content: bytes, filename: str) -> Dict[str, Any]:
    # Returns structured content with:
    # - raw_text: Full text content
    # - structured_data: Tables and forms from Textract
    # - medical_entities: Extracted medical information
    # - key_sections: Identified document sections
    # - metadata: PDF metadata
```

### 2. PDF Embedding Service (`pdf_embedding_service.py`)

**Purpose**: Complete workflow for PDF processing and embedding creation

**Workflow**:
1. **Download from S3**: Retrieve PDF content
2. **Extract Content**: Use PDFExtractor for comprehensive extraction
3. **Create Chunks**: Split text into overlapping chunks (1000 chars with 200 char overlap)
4. **Generate Embeddings**: Create vector embeddings using Bedrock Cohere
5. **Store in OpenSearch**: Index chunks with embeddings for semantic search
6. **Store Metadata**: Save document metadata in DynamoDB

**Key Configuration**:
```python
self.chunk_size = 1000      # Characters per chunk
self.chunk_overlap = 200    # Overlap between chunks
self.max_chunks_per_doc = 50 # Limit chunks per document
```

### 3. Chunking Strategy

**Why Chunking?**
- Large documents exceed embedding model limits
- Smaller chunks provide more precise semantic matching
- Overlapping chunks ensure context continuity

**Chunking Process**:
```python
def _create_text_chunks(self, extracted_content, metadata):
    # 1. Clean text (remove excessive whitespace, normalize)
    # 2. Split into sentences for better boundaries
    # 3. Create overlapping chunks
    # 4. Add metadata to each chunk
    # 5. Extract chunk-specific medical entities
```

**Chunk Structure**:
```json
{
    "chunk_id": "doc123_001",
    "document_id": "doc123",
    "filename": "diabetes_guide.pdf",
    "text": "Metformin is the first-line medication...",
    "embedding": [0.1, -0.2, 0.3, ...],
    "medical_entities": {
        "medications": [{"name": "metformin", "confidence": 0.9}],
        "conditions": [{"name": "diabetes", "confidence": 0.8}]
    },
    "metadata": {
        "section_type": "medications",
        "page_info": {"page_number": 3}
    }
}
```

### 4. Embedding Generation

**Model**: Cohere Embed English v3 via AWS Bedrock
**Dimensions**: 1024 (typical for Cohere)
**Input Type**: `search_document` for optimal retrieval performance

**Process**:
```python
def _generate_embeddings_for_chunks(self, chunks):
    for chunk in chunks:
        embedding = self.bedrock_service.create_embeddings(chunk['text'])
        chunk['embedding'] = embedding
        chunk['embedding_model'] = 'cohere.embed-english-v3'
```

### 5. OpenSearch Storage

**Index Structure**:
- Each chunk is stored as a separate document
- Embeddings stored as dense vectors
- Metadata and entities stored as searchable fields
- Support for both semantic and keyword search

**Document Structure in OpenSearch**:
```json
{
    "chunk_id": "doc123_001",
    "document_id": "doc123",
    "text": "Full chunk text...",
    "embedding": [vector array],
    "categories": ["clinical_guidelines"],
    "medical_entities": {...},
    "upload_date": "2024-01-01T00:00:00Z",
    "filename": "diabetes_guide.pdf"
}
```

## Usage Examples

### 1. Process PDF from S3

```python
from services.pdf_embedding_service import PDFEmbeddingService

embedding_service = PDFEmbeddingService()

# Document metadata
metadata = {
    'document_id': 'doc_123',
    'filename': 'diabetes_guide.pdf',
    'categories': ['clinical_guidelines'],
    's3_key': 'medical_documents/diabetes_guide.pdf'
}

# Process PDF
result = embedding_service.process_pdf_from_s3(
    bucket_name='medical-docs-bucket',
    s3_key='medical_documents/diabetes_guide.pdf',
    document_metadata=metadata
)

print(f"Chunks created: {result['chunks_created']}")
print(f"Chunks embedded: {result['chunks_embedded']}")
```

### 2. Query Similar Chunks

```python
# Semantic search for chatbot context
query = "What are the side effects of metformin?"

similar_chunks = embedding_service.query_similar_chunks(
    query=query,
    filters={'categories': ['clinical_guidelines']},
    limit=5
)

# Use chunks as context for chatbot response
for chunk in similar_chunks:
    print(f"Relevance: {chunk['score']}")
    print(f"Content: {chunk['text'][:200]}...")
```

### 3. Integration with Chat Service

```python
def process_chat_query(self, query: str, session_id: str):
    # 1. Get relevant chunks using semantic search
    relevant_chunks = self.embedding_service.query_similar_chunks(
        query=query,
        limit=3
    )
    
    # 2. Prepare context from chunks
    context = []
    for chunk in relevant_chunks:
        context.append({
            'filename': chunk['filename'],
            'content': chunk['text'],
            'relevance_score': chunk['score']
        })
    
    # 3. Generate AI response with context
    response = self.bedrock_service.generate_medical_response(
        query=query,
        context=context,
        history=[]
    )
    
    return response
```

## Configuration

### Environment Variables

```bash
AWS_REGION=ap-southeast-1
BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
OPENSEARCH_ENDPOINT=https://your-opensearch-domain.region.es.amazonaws.com
OPENSEARCH_INDEX=medical-documents
DYNAMODB_DOCUMENTS_TABLE=medical-documents-metadata
S3_BUCKET=echomind-pdf-storage-sg
```

### AWS Services Required

1. **S3**: PDF storage
2. **Bedrock**: Embeddings (Cohere) and text generation (Nova Pro)
3. **OpenSearch Serverless**: Vector storage and search
4. **DynamoDB**: Document metadata
5. **Textract**: Enhanced PDF extraction (optional)

## Performance Considerations

### Chunking Optimization
- **Chunk Size**: 1000 characters balances context and precision
- **Overlap**: 200 characters ensures context continuity
- **Max Chunks**: 50 per document prevents index bloat

### Embedding Efficiency
- Batch processing for multiple chunks
- Async processing for large documents
- Caching for repeated queries

### Search Performance
- Use filters to narrow search scope
- Limit results to top 5-10 most relevant chunks
- Combine semantic and keyword search when needed

## Monitoring and Debugging

### Processing Status
```python
# Check document processing status
status = document_processor.get_processing_status(document_id)
print(f"Status: {status['status']}")
print(f"Chunks indexed: {status.get('chunks_indexed', 0)}")
```

### Search Statistics
```python
# Get search engine statistics
stats = document_processor.get_search_stats()
print(f"Total documents: {stats['total_documents_processed']}")
print(f"Searchable documents: {stats['searchable_documents']}")
```

### Error Handling
- Graceful fallback to keyword search if embeddings fail
- Retry logic for transient AWS service errors
- Comprehensive logging for debugging

## Best Practices

### Document Preparation
1. Ensure PDFs are text-based (not scanned images)
2. Use consistent naming conventions
3. Add appropriate categories and metadata

### Query Optimization
1. Use specific medical terminology
2. Include context in queries
3. Filter by document categories when possible

### Maintenance
1. Monitor embedding quality and adjust chunk sizes
2. Regularly update medical entity patterns
3. Clean up old or irrelevant documents

## Troubleshooting

### Common Issues

1. **No embeddings generated**
   - Check Bedrock service access
   - Verify model availability in region
   - Check text content extraction

2. **Poor search results**
   - Verify chunk quality and size
   - Check embedding model configuration
   - Review query formulation

3. **OpenSearch indexing failures**
   - Check index configuration
   - Verify network connectivity
   - Monitor index capacity

### Debug Commands

```python
# Test individual components
python backend/example_pdf_embedding_workflow.py

# Check service initialization
from services.pdf_embedding_service import PDFEmbeddingService
service = PDFEmbeddingService()  # Should not raise exceptions

# Test embedding generation
from services.bedrock_service import BedrockService
bedrock = BedrockService()
embedding = bedrock.create_embeddings("test text")
print(f"Embedding dimensions: {len(embedding)}")
```

This comprehensive system enables intelligent chatbot queries by converting static PDF documents into searchable, semantically-aware content that can provide relevant context for medical questions.