import PyPDF2
import io
import re
import boto3
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from ..ai.bedrock_service import BedrockService
from ..ai.comprehend_service import ComprehendService
from ..storage.opensearch_service import OpenSearchService
from .medical_search_engine import MedicalSearchEngine
from .pdf_embedding_service import PDFEmbeddingService

class DocumentProcessor:
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'ap-southeast-1')
        self.documents_table = os.getenv('DYNAMODB_DOCUMENTS_TABLE', 'medical-documents')
        
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.table = self.dynamodb.Table(self.documents_table)
        
        # Initialize enhanced services - using embedding service for PDF extraction
        self.pdf_extractor = None  # Will use embedding_service for PDF extraction
            
        try:
            self.search_engine = MedicalSearchEngine()
        except Exception as e:
            print(f"Search engine initialization failed: {str(e)}")
            self.search_engine = None
            
        try:
            self.embedding_service = PDFEmbeddingService()
        except Exception as e:
            print(f"Embedding service initialization failed: {str(e)}")
            self.embedding_service = None
        
        # Initialize AI services with error handling
        try:
            self.bedrock_service = BedrockService()
        except Exception as e:
            print(f"Bedrock service initialization failed: {str(e)}")
            self.bedrock_service = None
            
        try:
            self.comprehend_service = ComprehendService()
        except Exception as e:
            print(f"Comprehend service initialization failed: {str(e)}")
            self.comprehend_service = None
            
        try:
            self.opensearch_service = OpenSearchService()
        except Exception as e:
            print(f"OpenSearch service initialization failed: {str(e)}")
            self.opensearch_service = None
    
    def process_pdf_document(self, file_content: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        try:
            document_id = metadata['document_id']
            filename = metadata.get('filename', 'unknown.pdf')
            print(f"🔍 Processing PDF: {filename}")

            # 1) Extract
            if not self.embedding_service:
                extracted_content = self._fallback_pdf_extraction(file_content, filename)
            else:
                processing_result = self.embedding_service.process_pdf_content(file_content, metadata)
                # Expect keys: raw_text, metadata.page_count, (optional) chunks, etc.
                raw_text = processing_result.get("raw_text", "")
                raw_text = self._clean_extracted_text(raw_text)
                extracted_content = {
                    "raw_text": raw_text,
                    "metadata": {
                        "page_count": processing_result.get("metadata", {}).get("page_count", 0)
                    },
                    "medical_entities": {},
                    "key_sections": processing_result.get("key_sections", {})
                }

            # 2) Entities (Comprehend Medical or fallback)
            if self.comprehend_service and extracted_content["raw_text"]:
                try:
                    extracted_content["medical_entities"] = self.comprehend_service.detect_medical_entities(
                        extracted_content["raw_text"]
                    )
                except Exception as e:
                    print(f"Comprehend medical failed: {e}")

            # 3) Create embeddings for the full doc (optional: also for chunks)
            embedding = []
            if self.bedrock_service and extracted_content["raw_text"]:
                embedding = self.bedrock_service.create_embeddings(extracted_content["raw_text"])

            # 4) Ask LLM for analysis (optional)
            if self.bedrock_service and extracted_content["raw_text"]:
                try:
                    ai_analysis = self.bedrock_service.generate_medical_response(
                        f"Analyze this medical document and extract key information.",
                        context=[{"id": document_id, "filename": filename, "content": extracted_content["raw_text"][:2000]}],
                        history=[]
                    )
                    extracted_content["ai_analysis"] = ai_analysis
                except Exception as e:
                    print(f"Nova Pro analysis failed: {e}")
                    extracted_content["ai_analysis"] = None

            # 5) Index (in-memory) medical search engine — add filename for better UX
            if self.search_engine:
                self.search_engine.index_document(document_id, {
                    **extracted_content,
                    "filename": filename
                })

            # 6) Persist to DynamoDB
            processing_results = {
                "document_id": document_id,
                "filename": filename,
                "extracted_content": extracted_content,
                "processing_date": datetime.now().isoformat(),
                "status": "completed",
                "searchable": True,
                "opensearch_indexed": False
            }
            self._store_document_data(document_id, metadata, processing_results)

            # 7) Index to OpenSearch (text + embedding + metadata)
            if self.opensearch_service:
                try:
                    self.opensearch_service.index_document(
                        doc_id=document_id,
                        document={
                            "text": extracted_content["raw_text"],
                            "embedding": embedding,                 # <= IMPORTANT
                            "entities": extracted_content.get("medical_entities", {}),
                            "metadata": {**metadata}                # filename, s3_key, etc.
                        }
                    )
                    processing_results["opensearch_indexed"] = True
                except Exception as e:
                    print(f"OpenSearch indexing failed: {e}")

            print(f"✅ Successfully processed: {filename}")
            return processing_results

        except Exception as e:
            print(f"❌ Document processing failed: {e}")
            return {
                "document_id": metadata.get("document_id", "unknown"),
                "status": "failed",
                "error": str(e),
                "processing_date": datetime.now().isoformat()
            }
    
    def get_document_content(self, document_id: str) -> Dict[str, Any]:
        """Get full document content and analysis"""
        try:
            response = self.table.get_item(
                Key={'document_id': document_id}
            )
            
            if 'Item' in response:
                return response['Item']
            else:
                return {'error': 'Document not found'}
                
        except Exception as e:
            print(f"❌ Failed to get document content: {str(e)}")
            return {'error': str(e)}
    
    def get_search_stats(self) -> Dict[str, Any]:
        """Get search engine statistics"""
        return self.search_engine.get_index_stats()
    
    def _clean_extracted_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep medical symbols
        text = re.sub(r'[^\w\s\-\.\,\;\:\(\)\[\]\%\+\=\<\>\°\µ\α\β\γ]', ' ', text)
        
        # Fix common OCR issues
        text = text.replace(' . ', '. ')
        text = text.replace(' , ', ', ')
        text = text.replace(' ; ', '; ')
        
        # Normalize medical units
        text = re.sub(r'\b(\d+)\s*(mg|ml|g|kg|mcg|µg)\b', r'\1\2', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def _create_text_chunks(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Create overlapping text chunks for better semantic search"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        words = text.split()
        
        start = 0
        while start < len(words):
            # Calculate end position
            end = min(start + chunk_size, len(words))
            
            # Create chunk
            chunk_words = words[start:end]
            chunk_text = ' '.join(chunk_words)
            
            # Try to end at sentence boundary
            if end < len(words):
                # Look for sentence endings in the last part of the chunk
                last_part = ' '.join(chunk_words[-50:]) if len(chunk_words) > 50 else chunk_text
                sentence_end = max(
                    last_part.rfind('. '),
                    last_part.rfind('! '),
                    last_part.rfind('? ')
                )
                
                if sentence_end > 0:
                    # Adjust chunk to end at sentence boundary
                    sentence_end_in_chunk = len(chunk_text) - len(last_part) + sentence_end + 1
                    chunk_text = chunk_text[:sentence_end_in_chunk].strip()
            
            chunks.append(chunk_text)
            
            # Move start position with overlap
            if end >= len(words):
                break
            
            start = end - overlap
        
        return chunks
    
    def _index_document_chunks(self, processed_doc: Dict[str, Any]) -> bool:
        try:
            success_count = 0
            total_chunks = len(processed_doc['chunks'])

            for i, chunk_data in enumerate(processed_doc['chunks']):
                chunk_id = f"{processed_doc['id']}_chunk_{i}"
                ok = self.opensearch_service.index_document(
                    doc_id=chunk_id,
                    document={
                        "text": chunk_data["text"],
                        "embedding": chunk_data.get("embeddings", []),
                        "entities": processed_doc.get("entities", {}),
                        "metadata": {
                            **processed_doc.get("metadata", {}),
                            "chunk_index": i,
                            "total_chunks": total_chunks,
                            "parent_document_id": processed_doc["id"]
                        }
                    }
                )
                if ok: success_count += 1

            # Also index the full document
            full_doc_ok = self.opensearch_service.index_document(
                doc_id=processed_doc["id"],
                document={
                    "text": processed_doc.get("content", ""),
                    "embedding": (processed_doc["chunks"][0].get("embeddings", [])
                                if processed_doc.get("chunks") else []),
                    "entities": processed_doc.get("entities", {}),
                    "metadata": {
                        **processed_doc.get("metadata", {}),
                        "is_full_document": True,
                        "total_chunks": total_chunks
                    }
                }
            )
            return success_count > 0 and full_doc_ok
        except Exception as e:
            print(f"Document indexing error: {e}")
            return False
    
    def search_documents(self, query: str, filters: Dict = None, limit: int = 10) -> Dict[str, Any]:
        """Search documents using natural language query"""
        try:
            print(f"🔍 Searching for: {query}")
            
            # Use the medical search engine
            search_results = self.search_engine.search(query, filters, limit)
            
            # Enhance results with document metadata from DynamoDB
            enhanced_results = []
            for result in search_results['results']:
                try:
                    # Get document metadata from DynamoDB
                    doc_response = self.table.get_item(
                        Key={'document_id': result['document_id']}
                    )
                    
                    if 'Item' in doc_response:
                        doc_metadata = doc_response['Item']
                        result['upload_date'] = doc_metadata.get('upload_date')
                        result['categories'] = doc_metadata.get('categories', [])
                        result['file_size'] = doc_metadata.get('size')
                    
                    enhanced_results.append(result)
                    
                except Exception as e:
                    print(f"Failed to enhance result for {result['document_id']}: {str(e)}")
                    enhanced_results.append(result)
            
            search_results['results'] = enhanced_results
            print(f"✅ Found {len(enhanced_results)} results")
            
            return search_results
            
        except Exception as e:
            print(f"❌ Search failed: {str(e)}")
            return {
                'query': query,
                'total_results': 0,
                'results': [],
                'error': str(e)
            }
    
    def get_search_suggestions(self, partial_query: str) -> List[str]:
        """Get search suggestions for autocomplete"""
        return self.search_engine.get_search_suggestions(partial_query)
    
    def get_processing_status(self, document_id: str) -> Dict[str, Any]:
        """Get enhanced processing status for a document"""
        try:
            response = self.table.get_item(
                Key={'document_id': document_id}
            )
            
            if 'Item' in response:
                item = response['Item']
                return {
                    'document_id': document_id,
                    'filename': item.get('filename', ''),
                    'status': item.get('processing_status', 'unknown'),
                    'processing_date': item.get('processing_date', ''),
                    'text_length': item.get('text_length', 0),
                    'page_count': item.get('page_count', 0),
                    'medical_entities': item.get('medical_entities', {}),
                    'key_sections': list(item.get('key_sections', {}).keys()),
                    'searchable': item.get('searchable', False),
                    'opensearch_indexed': item.get('opensearch_indexed', False)
                }
            else:
                return {
                    'document_id': document_id,
                    'status': 'not_found'
                }
                
        except Exception as e:
            print(f"❌ Failed to get processing status: {str(e)}")
            return {
                'document_id': document_id,
                'status': 'error',
                'error': str(e)
            }
    
    def _store_document_data(self, document_id: str, metadata: Dict[str, Any], processing_results: Dict[str, Any]):
        """Store enhanced document data in DynamoDB"""
        try:
            extracted_content = processing_results.get('extracted_content', {})
            
            item = {
                'document_id': document_id,
                'filename': metadata.get('filename', ''),
                'original_filename': metadata.get('original_filename', ''),
                's3_key': metadata.get('s3_key', ''),
                'size': metadata.get('size', 0),
                'upload_date': metadata.get('upload_date', ''),
                'categories': metadata.get('categories', []),
                'processing_status': processing_results.get('status', 'unknown'),
                'processing_date': processing_results.get('processing_date', ''),
                'text_length': len(extracted_content.get('raw_text', '')),
                'page_count': extracted_content.get('metadata', {}).get('page_count', 0),
                'medical_entities': extracted_content.get('medical_entities', {}),
                'key_sections': extracted_content.get('key_sections', {}),
                'searchable': processing_results.get('searchable', False),
                'opensearch_indexed': processing_results.get('opensearch_indexed', False)
            }
            
            self.table.put_item(Item=item)
            print(f"✅ Stored enhanced document data for {document_id}")
            
        except Exception as e:
            print(f"❌ Failed to store document data: {str(e)}")