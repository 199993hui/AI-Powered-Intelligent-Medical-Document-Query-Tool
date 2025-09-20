import boto3
import PyPDF2
from io import BytesIO
from typing import List, Dict, Any
import re
import json
from datetime import datetime

class DocumentSearchService:
    """Service for searching through all documents in S3 bucket"""
    
    def __init__(self, bucket_name: str = "echomind-pdf-storage"):
        self.s3 = boto3.client('s3')
        self.bucket_name = bucket_name
        self.document_index = {}  # In-memory index for fast searching
        self.medical_terms = self._load_medical_terms()
        self._build_document_index()
    
    def _load_medical_terms(self) -> Dict[str, List[str]]:
        """Load medical terminology mappings"""
        return {
            'abbreviations': {
                'bp': 'blood pressure', 'hr': 'heart rate', 'cbc': 'complete blood count',
                'ecg': 'electrocardiogram', 'ekg': 'electrocardiogram', 'mri': 'magnetic resonance imaging',
                'ct': 'computed tomography', 'rbc': 'red blood cell', 'wbc': 'white blood cell',
                'hgb': 'hemoglobin', 'hct': 'hematocrit', 'bun': 'blood urea nitrogen',
                'crp': 'c-reactive protein', 'esr': 'erythrocyte sedimentation rate'
            },
            'synonyms': {
                'heart attack': ['myocardial infarction', 'mi', 'cardiac arrest'],
                'stroke': ['cerebrovascular accident', 'cva', 'brain attack'],
                'diabetes': ['diabetes mellitus', 'dm', 'diabetic'],
                'high blood pressure': ['hypertension', 'htn', 'elevated bp'],
                'kidney disease': ['renal disease', 'nephropathy', 'kidney failure']
            },
            'drug_classes': {
                'ace inhibitor': ['lisinopril', 'enalapril', 'captopril'],
                'beta blocker': ['metoprolol', 'atenolol', 'propranolol'],
                'statin': ['atorvastatin', 'simvastatin', 'rosuvastatin']
            }
        }
    
    def _build_document_index(self):
        """Build searchable index of all documents in S3"""
        try:
            # List all objects in bucket
            response = self.s3.list_objects_v2(Bucket=self.bucket_name)
            
            if 'Contents' not in response:
                print("No documents found in S3 bucket")
                return
            
            for obj in response['Contents']:
                key = obj['Key']
                if key.endswith('.pdf'):
                    try:
                        # Extract text from PDF
                        text_content = self._extract_text_from_s3_pdf(key)
                        
                        # Store in index
                        self.document_index[key] = {
                            'filename': key.split('/')[-1],
                            'content': text_content,
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat(),
                            'key': key
                        }
                        print(f"✅ Indexed: {key}")
                        
                    except Exception as e:
                        print(f"❌ Failed to index {key}: {e}")
            
            print(f"📚 Document index built with {len(self.document_index)} documents")
            
        except Exception as e:
            print(f"❌ Error building document index: {e}")
    
    def _extract_text_from_s3_pdf(self, s3_key: str) -> str:
        """Extract text content from PDF in S3"""
        try:
            # Download PDF from S3
            response = self.s3.get_object(Bucket=self.bucket_name, Key=s3_key)
            pdf_content = response['Body'].read()
            
            # Extract text using PyPDF2
            pdf_file = BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text_content = ""
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
            
            return text_content.strip()
            
        except Exception as e:
            print(f"Error extracting text from {s3_key}: {e}")
            return ""
    
    def _expand_medical_terms(self, query: str) -> List[str]:
        """Expand medical terms and abbreviations"""
        expanded_terms = [query]
        query_lower = query.lower()
        
        # Expand abbreviations
        for abbr, full_term in self.medical_terms['abbreviations'].items():
            if abbr in query_lower:
                expanded_terms.append(query_lower.replace(abbr, full_term))
                expanded_terms.append(full_term)
        
        # Add synonyms
        for term, synonyms in self.medical_terms['synonyms'].items():
            if term in query_lower:
                expanded_terms.extend(synonyms)
        
        # Add drug class matches
        for drug_class, drugs in self.medical_terms['drug_classes'].items():
            if drug_class in query_lower:
                expanded_terms.extend(drugs)
        
        return list(set(expanded_terms))
    
    def search_documents(self, query_terms: List[str], expanded_query: str = "", medical_entities: Dict = None) -> List[Dict]:
        """Search through all indexed documents with medical term expansion"""
        results = []
        
        # Expand medical terms for better matching
        all_terms = []
        for term in query_terms:
            all_terms.extend(self._expand_medical_terms(term))
        
        if expanded_query:
            all_terms.extend(self._expand_medical_terms(expanded_query))
        
        # Add medical entities
        if medical_entities:
            for entity_list in medical_entities.values():
                all_terms.extend(entity_list)
        
        # Clean and deduplicate terms
        search_terms = list(set([term.lower().strip() for term in all_terms if term.strip()]))
        
        # Search through each document
        for s3_key, doc_data in self.document_index.items():
            content_lower = doc_data['content'].lower()
            matched_terms = []
            total_matches = 0
            phrase_matches = 0
            
            # Exact phrase matching (higher weight)
            for original_term in query_terms:
                if original_term.lower() in content_lower:
                    phrase_matches += len(re.findall(re.escape(original_term.lower()), content_lower))
            
            # Individual term matching
            for term in search_terms:
                if len(term) > 2:  # Skip very short terms
                    matches = len(re.findall(r'\b' + re.escape(term) + r'\b', content_lower))
                    if matches > 0:
                        matched_terms.append(term)
                        total_matches += matches
            
            # Calculate enhanced relevance score
            if matched_terms or phrase_matches > 0:
                term_coverage = len(matched_terms) / len(search_terms) if search_terms else 0
                match_density = min(1.0, total_matches / 10)  # Normalize match count
                phrase_bonus = min(0.3, phrase_matches * 0.1)  # Bonus for phrase matches
                
                relevance_score = min(0.99, term_coverage * 0.5 + match_density * 0.3 + phrase_bonus)
                
                # Extract best excerpt
                excerpt = self._extract_best_excerpt(doc_data['content'], query_terms + matched_terms[:3])
                
                results.append({
                    'document_id': s3_key.replace('/', '_'),
                    'filename': doc_data['filename'],
                    'relevance_score': relevance_score,
                    'matched_terms': matched_terms[:5],  # Limit displayed terms
                    'excerpt': excerpt,
                    's3_key': s3_key,
                    'total_matches': total_matches,
                    'phrase_matches': phrase_matches
                })
        
        # Sort by relevance score (highest first)
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return results[:20]  # Limit to top 20 results
    
    def _extract_best_excerpt(self, content: str, search_terms: List[str], context_length: int = 300) -> str:
        """Extract the best excerpt containing multiple search terms"""
        content_lower = content.lower()
        best_excerpt = ""
        best_score = 0
        
        # Try to find excerpt with most search terms
        for term in search_terms:
            term_lower = term.lower()
            index = content_lower.find(term_lower)
            
            if index != -1:
                # Extract context around this term
                start = max(0, index - context_length // 2)
                end = min(len(content), index + len(term) + context_length // 2)
                excerpt = content[start:end]
                
                # Score this excerpt by counting term matches
                excerpt_lower = excerpt.lower()
                score = sum(1 for t in search_terms if t.lower() in excerpt_lower)
                
                if score > best_score:
                    best_score = score
                    best_excerpt = excerpt
        
        # Fallback to beginning of document
        if not best_excerpt:
            best_excerpt = content[:context_length]
        
        # Clean up excerpt
        if len(content) > len(best_excerpt) + 50:
            if not best_excerpt.startswith(content[:10]):
                best_excerpt = "..." + best_excerpt
            if not best_excerpt.endswith(content[-10:]):
                best_excerpt = best_excerpt + "..."
        
        return best_excerpt.strip()
    
    def refresh_index(self):
        """Refresh the document index (call when new documents are uploaded)"""
        print("🔄 Refreshing document index...")
        self.document_index.clear()
        self._build_document_index()
    
    def get_document_content(self, s3_key: str) -> str:
        """Get full content of a specific document"""
        if s3_key in self.document_index:
            return self.document_index[s3_key]['content']
        return ""
    
    def get_index_stats(self) -> Dict:
        """Get statistics about the document index"""
        total_docs = len(self.document_index)
        total_content_length = sum(len(doc['content']) for doc in self.document_index.values())
        
        return {
            'total_documents': total_docs,
            'total_content_length': total_content_length,
            'average_document_size': total_content_length // total_docs if total_docs > 0 else 0,
            'last_updated': datetime.utcnow().isoformat()
        }