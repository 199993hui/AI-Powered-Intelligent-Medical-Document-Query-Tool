import boto3
import json
import uuid
import hashlib
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
    
try:
    import camelot  # for tables
except ImportError:
    camelot = None
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from ..ai.bedrock_service import BedrockService
from ..storage.opensearch_service import OpenSearchService

logger = logging.getLogger(__name__)

class PDFEmbeddingService:
    """Complete service for PDF extraction, chunking, and embedding creation"""
    
    def __init__(self):
        self.s3_client = boto3.client('s3', region_name='ap-southeast-1')
        self.bedrock_service = BedrockService()
        self.opensearch_service = OpenSearchService()
        
        # Configuration
        self.chunk_size = 1000  # Characters per chunk
        self.chunk_overlap = 200  # Overlap between chunks
        self.max_chunks_per_doc = 50  # Limit chunks per document
    
    def process_pdf_content(self, pdf_content: bytes, document_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process PDF content directly: Extract → Chunk → Embed → Store"""
        try:
            logger.info(f"Starting PDF processing for {document_metadata.get('filename')}")
            
            # Step 1: Extract content from PDF bytes
            extracted_content = self._extract_pdf_from_bytes(pdf_content, document_metadata.get('filename'))
            
            # Step 2: Create text chunks
            chunks = self._create_text_chunks(extracted_content, document_metadata)
            
            # Step 3: Generate embeddings
            embedded_chunks = self._generate_embeddings_for_chunks(chunks)
            
            # Step 4: Store in OpenSearch
            indexing_result = self._store_embeddings_in_opensearch(embedded_chunks, document_metadata)
            
            # Step 5: Store metadata in DynamoDB
            metadata_result = self._store_document_metadata(document_metadata, extracted_content, indexing_result)
            
            return {
                'status': 'success',
                'document_id': document_metadata.get('document_id'),
                'chunks_created': len(chunks),
                'chunks_embedded': len(embedded_chunks),
                'chunks_indexed': indexing_result.get('indexed_count', 0),
                'extraction_summary': {
                    'text_length': len(extracted_content.get('raw_text', '')),
                    'tables_found': len(extracted_content.get('tables', [])),
                    'images_found': len(extracted_content.get('images', [])),
                    'page_count': extracted_content.get('metadata', {}).get('page_count', 0)
                },
                'processing_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"PDF processing failed: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'document_id': document_metadata.get('document_id'),
                'processing_time': datetime.now().isoformat()
            }
    

    
    def _extract_pdf_from_bytes(self, pdf_content: bytes, filename: str) -> Dict[str, Any]:
        """Extract PDF content from bytes using PyMuPDF and Camelot"""
        if not fitz:
            logger.warning("PyMuPDF not available, using fallback extraction")
            return self._fallback_pdf_extraction(pdf_content, filename)
            
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(pdf_content)
            temp_path = temp_file.name
        
        try:
            return self._extract_pdf(temp_path, filename)
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def _extract_pdf(self, local_path: str, filename: str) -> Dict[str, Any]:
        """Extract PDF using your provided code"""
        try:
            # Extract text using PyMuPDF
            doc = fitz.open(local_path)
            text = "\n".join([page.get_text() for page in doc])
            page_count = len(doc)
            
            # Extract tables using Camelot
            tables = []
            if camelot:
                try:
                    extracted_tables = camelot.read_pdf(local_path, pages="all")
                    for t in extracted_tables:
                        tables.append(t.df.to_csv(index=False))
                except Exception as e:
                    logger.warning(f"No tables found: {e}")
            
            # Extract images
            images = []
            for page_index, page in enumerate(doc):
                for img in page.get_images(full=True):
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    if pix.alpha:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    img_path = f"/tmp/page{page_index}-{xref}.png"
                    pix.save(img_path)
                    images.append(img_path)
            
            doc.close()
            
            return {
                'filename': filename,
                'raw_text': text,
                'tables': tables,
                'images': images,
                'metadata': {'page_count': page_count}
            }
            
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return self._fallback_pdf_extraction(None, filename)
    
    def _fallback_pdf_extraction(self, pdf_content: bytes, filename: str) -> Dict[str, Any]:
        """Fallback PDF extraction using PyPDF2"""
        try:
            import PyPDF2
            from io import BytesIO
            
            pdf_file = BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            return {
                'filename': filename,
                'raw_text': text,
                'tables': [],
                'images': [],
                'metadata': {'page_count': len(pdf_reader.pages)}
            }
        except Exception as e:
            logger.error(f"Fallback PDF extraction failed: {e}")
            return {
                'filename': filename,
                'raw_text': '',
                'tables': [],
                'images': [],
                'metadata': {'page_count': 0}
            }
    

    

    

    
    def _create_text_chunks(self, extracted_content: Dict[str, Any], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create overlapping text chunks for embedding"""
        chunks = []
        raw_text = extracted_content.get('raw_text', '')
        
        if not raw_text:
            logger.warning(f"No text content found for document {metadata.get('document_id')}")
            return chunks
        
        # Clean and prepare text
        cleaned_text = self._clean_text_for_chunking(raw_text)
        
        # Create overlapping chunks
        text_chunks = self._split_text_into_chunks(cleaned_text)
        
        # Create chunk objects with metadata
        for i, chunk_text in enumerate(text_chunks):
            if len(chunk_text.strip()) < 50:  # Skip very short chunks
                continue
                
            chunk_id = f"{metadata.get('document_id', 'unknown')}_{i:03d}"
            
            chunk = {
                'chunk_id': chunk_id,
                'document_id': metadata.get('document_id'),
                'filename': metadata.get('filename'),
                'chunk_index': i,
                'text': chunk_text,
                'text_length': len(chunk_text),
                'categories': metadata.get('categories', []),
                'upload_date': metadata.get('upload_date'),
                's3_key': metadata.get('s3_key'),
                'chunk_hash': hashlib.md5(chunk_text.encode()).hexdigest(),
                'metadata': {
                    'tables_in_chunk': self._check_tables_in_chunk(chunk_text, extracted_content.get('tables', [])),
                    'images_in_chunk': len(extracted_content.get('images', []))
                }
            }
            chunks.append(chunk)
            
            # Limit chunks per document
            if len(chunks) >= self.max_chunks_per_doc:
                logger.warning(f"Reached maximum chunks limit for document {metadata.get('document_id')}")
                break
        
        logger.info(f"Created {len(chunks)} chunks for document {metadata.get('document_id')}")
        return chunks
    
    def _clean_text_for_chunking(self, text: str) -> str:
        """Clean text for better chunking"""
        import re
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page headers/footers patterns
        text = re.sub(r'--- Page \d+ ---', '', text)
        
        # Normalize line breaks
        text = re.sub(r'\n+', '\n', text)
        
        return text.strip()
    
    def _split_text_into_chunks(self, text: str) -> List[str]:
        """Split text into overlapping chunks"""
        chunks = []
        
        # Split by sentences first for better chunk boundaries
        sentences = self._split_into_sentences(text)
        
        current_chunk = ""
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            # If adding this sentence would exceed chunk size
            if current_length + sentence_length > self.chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk)
                current_chunk = overlap_text + " " + sentence
                current_length = len(current_chunk)
            else:
                current_chunk += " " + sentence
                current_length += sentence_length + 1
        
        # Add the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        import re
        
        # Simple sentence splitting (can be improved with NLTK)
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _get_overlap_text(self, chunk: str) -> str:
        """Get overlap text from the end of current chunk"""
        if len(chunk) <= self.chunk_overlap:
            return chunk
        
        # Get last N characters, but try to break at word boundary
        overlap = chunk[-self.chunk_overlap:]
        space_index = overlap.find(' ')
        
        if space_index > 0:
            return overlap[space_index:].strip()
        
        return overlap
    
    def _check_tables_in_chunk(self, chunk_text: str, tables: List[str]) -> int:
        """Check how many tables are referenced in this chunk"""
        table_count = 0
        for table_csv in tables:
            table_lines = table_csv.split('\n')[:3]
            for line in table_lines:
                if line.strip() and line.strip() in chunk_text:
                    table_count += 1
                    break
        return table_count
    
    def _generate_embeddings_for_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate embeddings for all chunks"""
        embedded_chunks = []
        
        for chunk in chunks:
            try:
                # Create embedding for chunk text
                embedding = self.bedrock_service.create_embeddings(chunk['text'])
                
                if embedding:
                    chunk['embedding'] = embedding
                    chunk['embedding_model'] = 'cohere.embed-english-v3'
                    chunk['embedding_date'] = datetime.now().isoformat()
                    embedded_chunks.append(chunk)
                else:
                    logger.warning(f"Failed to create embedding for chunk {chunk['chunk_id']}")
                    
            except Exception as e:
                logger.error(f"Embedding generation failed for chunk {chunk['chunk_id']}: {str(e)}")
                continue
        
        logger.info(f"Generated embeddings for {len(embedded_chunks)}/{len(chunks)} chunks")
        return embedded_chunks
    
    def _store_embeddings_in_opensearch(self, embedded_chunks: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Store embedded chunks in OpenSearch"""
        try:
            indexed_count = 0
            failed_count = 0
            
            for chunk in embedded_chunks:
                try:
                    # Prepare document for OpenSearch
                    opensearch_doc = {
                        'chunk_id': chunk['chunk_id'],
                        'document_id': chunk['document_id'],
                        'filename': chunk['filename'],
                        'text': chunk['text'],
                        'embedding': chunk['embedding'],
                        'categories': chunk['categories'],
                        'chunk_metadata': chunk['metadata'],
                        'upload_date': chunk['upload_date'],
                        'embedding_date': chunk['embedding_date'],
                        'text_length': chunk['text_length'],
                        'chunk_index': chunk['chunk_index']
                    }
                    
                    # Index in OpenSearch
                    success = self.opensearch_service.index_document(
                        chunk['chunk_id'],
                        opensearch_doc
                    )
                    
                    if success:
                        indexed_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Failed to index chunk {chunk['chunk_id']}: {str(e)}")
                    failed_count += 1
            
            return {
                'indexed_count': indexed_count,
                'failed_count': failed_count,
                'total_chunks': len(embedded_chunks),
                'index_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"OpenSearch indexing failed: {str(e)}")
            return {
                'indexed_count': 0,
                'failed_count': len(embedded_chunks),
                'error': str(e)
            }
    
    def _store_document_metadata(self, metadata: Dict[str, Any], extracted_content: Dict[str, Any], indexing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Store document metadata in DynamoDB"""
        try:
            dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
            table = dynamodb.Table('medical-documents-metadata')
            
            # Prepare metadata document
            metadata_doc = {
                'document_id': metadata['document_id'],
                'filename': metadata['filename'],
                'original_filename': metadata.get('original_filename', metadata['filename']),
                's3_key': metadata['s3_key'],
                'categories': metadata['categories'],
                'upload_date': metadata['upload_date'],
                'file_size': metadata.get('size', 0),
                'processing_status': 'completed',
                'processing_date': datetime.now().isoformat(),
                'extraction_summary': {
                    'text_length': len(extracted_content.get('raw_text', '')),
                    'page_count': extracted_content.get('metadata', {}).get('page_count', 0),
                    'tables_count': len(extracted_content.get('tables', [])),
                    'images_count': len(extracted_content.get('images', []))
                },
                'indexing_summary': indexing_result,
                'searchable': indexing_result.get('indexed_count', 0) > 0,
                'ttl': int(datetime.now().timestamp()) + (365 * 24 * 60 * 60)  # 1 year TTL
            }
            
            # Store in DynamoDB
            table.put_item(Item=metadata_doc)
            
            return {
                'status': 'success',
                'metadata_stored': True
            }
            
        except Exception as e:
            logger.error(f"Failed to store document metadata: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def query_similar_chunks(self, query: str, filters: Dict[str, Any] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Query for similar chunks using semantic search"""
        try:
            # Generate query embedding
            query_embedding = self.bedrock_service.create_embeddings(query)
            
            if not query_embedding:
                return []
            
            # Search in OpenSearch
            search_results = self.opensearch_service.semantic_search(
                query=query,
                embeddings=query_embedding,
                filters=filters,
                size=limit
            )
            
            return search_results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {str(e)}")
            return []
    
    def get_document_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document"""
        try:
            return self.opensearch_service.get_document_chunks(document_id)
        except Exception as e:
            logger.error(f"Failed to get document chunks: {str(e)}")
            return []
    
    def delete_document_embeddings(self, document_id: str) -> bool:
        """Delete all embeddings for a document"""
        try:
            # Delete from OpenSearch
            chunks_deleted = self.opensearch_service.delete_document_chunks(document_id)
            
            # Delete metadata from DynamoDB
            dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
            table = dynamodb.Table('medical-documents-metadata')
            table.delete_item(Key={'document_id': document_id})
            
            logger.info(f"Deleted {chunks_deleted} chunks for document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document embeddings: {str(e)}")
            return False