import json
import re
import math
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MedicalSearchEngine:
    """Advanced search engine for medical documents with natural language processing"""
    
    def __init__(self):
        self.document_index = {}  # In-memory search index
        self.medical_terms = self._load_medical_terminology()
        self.stop_words = set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'])
        
    def index_document(self, document_id: str, content: Dict[str, Any]) -> bool:
        """Index a document for searching"""
        try:
            # Extract searchable text
            searchable_text = self._prepare_searchable_text(content)
            
            # Create document index entry
            doc_index = {
                'id': document_id,
                'filename': content.get('filename', ''),
                'raw_text': content.get('raw_text', ''),
                'medical_entities': content.get('medical_entities', {}),
                'key_sections': content.get('key_sections', {}),
                'searchable_text': searchable_text,
                'tokens': self._tokenize_and_normalize(searchable_text),
                'medical_keywords': self._extract_medical_keywords(searchable_text),
                'indexed_date': datetime.now().isoformat()
            }
            
            self.document_index[document_id] = doc_index
            logger.info(f"Indexed document {document_id}: {content.get('filename', 'Unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to index document {document_id}: {str(e)}")
            return False
    
    def search(self, query: str, filters: Optional[Dict] = None, limit: int = 10) -> Dict[str, Any]:
        """Perform natural language search across indexed documents"""
        try:
            # Normalize and expand query
            normalized_query = self._normalize_query(query)
            expanded_query = self._expand_medical_query(normalized_query)
            
            # Score all documents
            scored_results = []
            for doc_id, doc_data in self.document_index.items():
                score = self._calculate_relevance_score(expanded_query, doc_data)
                if score > 0:
                    result = {
                        'document_id': doc_id,
                        'filename': doc_data['filename'],
                        'relevance_score': score,
                        'matched_content': self._extract_matched_content(expanded_query, doc_data),
                        'medical_entities': doc_data['medical_entities'],
                        'key_sections': doc_data['key_sections']
                    }
                    scored_results.append(result)
            
            # Sort by relevance and apply filters
            scored_results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            if filters:
                scored_results = self._apply_filters(scored_results, filters)
            
            # Limit results
            final_results = scored_results[:limit]
            
            return {
                'query': query,
                'expanded_query': expanded_query,
                'total_results': len(scored_results),
                'results': final_results,
                'search_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {str(e)}")
            return {
                'query': query,
                'total_results': 0,
                'results': [],
                'error': str(e)
            }
    
    def get_search_suggestions(self, partial_query: str) -> List[str]:
        """Get search suggestions based on medical terminology"""
        suggestions = []
        partial_lower = partial_query.lower()
        
        # Find matching medical terms
        for term in self.medical_terms:
            if term.lower().startswith(partial_lower):
                suggestions.append(term)
        
        # Find matching terms from indexed documents
        for doc_data in self.document_index.values():
            for keyword in doc_data['medical_keywords']:
                if keyword.lower().startswith(partial_lower) and keyword not in suggestions:
                    suggestions.append(keyword)
        
        return sorted(suggestions)[:10]
    
    def _prepare_searchable_text(self, content: Dict[str, Any]) -> str:
        """Prepare comprehensive searchable text from document content"""
        text_parts = []
        
        # Add raw text
        if content.get('raw_text'):
            text_parts.append(content['raw_text'])
        
        # Add medical entities
        medical_entities = content.get('medical_entities', {})
        for entity_type, entities in medical_entities.items():
            for entity in entities:
                if isinstance(entity, dict):
                    text_parts.append(entity.get('name', ''))
                    text_parts.append(entity.get('context', ''))
        
        # Add key sections
        key_sections = content.get('key_sections', {})
        for section_name, section_content in key_sections.items():
            text_parts.append(f"{section_name}: {section_content}")
        
        # Add structured data
        structured_data = content.get('structured_data', {})
        if structured_data.get('tables'):
            for table in structured_data['tables']:
                text_parts.append(str(table))
        
        return ' '.join(filter(None, text_parts))
    
    def _tokenize_and_normalize(self, text: str) -> List[str]:
        """Tokenize and normalize text for searching"""
        # Convert to lowercase and remove special characters
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        
        # Split into tokens
        tokens = text.split()
        
        # Remove stop words and short tokens
        tokens = [token for token in tokens if token not in self.stop_words and len(token) > 2]
        
        return tokens
    
    def _extract_medical_keywords(self, text: str) -> List[str]:
        """Extract medical keywords from text"""
        keywords = []
        text_lower = text.lower()
        
        for term in self.medical_terms:
            if term.lower() in text_lower:
                keywords.append(term)
        
        return list(set(keywords))
    
    def _normalize_query(self, query: str) -> str:
        """Normalize search query"""
        # Convert to lowercase
        query = query.lower()
        
        # Handle common medical abbreviations
        abbreviations = {
            'bp': 'blood pressure',
            'hr': 'heart rate',
            'temp': 'temperature',
            'wt': 'weight',
            'ht': 'height',
            'dx': 'diagnosis',
            'tx': 'treatment',
            'rx': 'prescription',
            'hx': 'history',
            'sx': 'symptoms'
        }
        
        for abbr, full_form in abbreviations.items():
            query = re.sub(rf'\b{abbr}\b', full_form, query)
        
        return query
    
    def _expand_medical_query(self, query: str) -> List[str]:
        """Expand query with medical synonyms and related terms"""
        expanded_terms = query.split()
        
        # Medical term expansions
        medical_expansions = {
            'diabetes': ['diabetes mellitus', 'diabetic', 'blood sugar', 'glucose'],
            'hypertension': ['high blood pressure', 'elevated bp', 'htn'],
            'medication': ['drug', 'medicine', 'prescription', 'treatment'],
            'pain': ['ache', 'discomfort', 'soreness', 'hurt'],
            'infection': ['bacterial', 'viral', 'sepsis', 'inflammatory'],
            'heart': ['cardiac', 'cardiovascular', 'coronary'],
            'lung': ['pulmonary', 'respiratory', 'breathing'],
            'kidney': ['renal', 'nephro'],
            'liver': ['hepatic', 'hepato']
        }
        
        for term in query.split():
            if term in medical_expansions:
                expanded_terms.extend(medical_expansions[term])
        
        return list(set(expanded_terms))
    
    def _calculate_relevance_score(self, query_terms: List[str], doc_data: Dict) -> float:
        """Calculate relevance score for a document"""
        score = 0.0
        doc_tokens = doc_data['tokens']
        doc_text = doc_data['searchable_text'].lower()
        
        # Term frequency scoring
        for term in query_terms:
            term_lower = term.lower()
            
            # Exact matches in tokens (higher weight)
            exact_matches = doc_tokens.count(term_lower)
            score += exact_matches * 2.0
            
            # Partial matches in text
            partial_matches = doc_text.count(term_lower)
            score += partial_matches * 1.0
            
            # Medical entity matches (highest weight)
            medical_entities = doc_data.get('medical_entities', {})
            for entity_type, entities in medical_entities.items():
                for entity in entities:
                    if isinstance(entity, dict):
                        entity_name = entity.get('name', '').lower()
                        if term_lower in entity_name:
                            score += 5.0 * entity.get('confidence', 0.5)
        
        # Boost score for medical keywords
        medical_keywords = doc_data.get('medical_keywords', [])
        for term in query_terms:
            if any(term.lower() in keyword.lower() for keyword in medical_keywords):
                score += 3.0
        
        # Normalize score by document length
        doc_length = len(doc_tokens)
        if doc_length > 0:
            score = score / math.log(doc_length + 1)
        
        return round(score, 3)
    
    def _extract_matched_content(self, query_terms: List[str], doc_data: Dict) -> str:
        """Extract relevant content snippets that match the query"""
        text = doc_data['raw_text']
        snippets = []
        
        for term in query_terms:
            # Find sentences containing the term
            sentences = re.split(r'[.!?]+', text)
            for sentence in sentences:
                if term.lower() in sentence.lower():
                    # Clean and truncate sentence
                    clean_sentence = sentence.strip()
                    if len(clean_sentence) > 200:
                        clean_sentence = clean_sentence[:200] + "..."
                    snippets.append(clean_sentence)
                    break  # One snippet per term
        
        return ' ... '.join(snippets[:3])  # Max 3 snippets
    
    def _apply_filters(self, results: List[Dict], filters: Dict) -> List[Dict]:
        """Apply filters to search results"""
        filtered_results = results
        
        # Filter by categories
        if 'categories' in filters:
            categories = filters['categories']
            # This would need document metadata to filter by categories
            pass
        
        # Filter by date range
        if 'date_range' in filters:
            date_range = filters['date_range']
            # This would need document dates to filter
            pass
        
        # Filter by confidence threshold
        if 'min_confidence' in filters:
            min_confidence = filters['min_confidence']
            filtered_results = [r for r in filtered_results if r['relevance_score'] >= min_confidence]
        
        return filtered_results
    
    def _load_medical_terminology(self) -> List[str]:
        """Load medical terminology for enhanced search"""
        # Basic medical terms - in production, this would be loaded from a comprehensive database
        medical_terms = [
            # Common conditions
            'diabetes', 'hypertension', 'asthma', 'copd', 'pneumonia', 'bronchitis',
            'arthritis', 'osteoporosis', 'cancer', 'tumor', 'infection', 'sepsis',
            'heart disease', 'coronary artery disease', 'myocardial infarction',
            'stroke', 'depression', 'anxiety', 'dementia', 'alzheimer',
            
            # Medications
            'metformin', 'insulin', 'lisinopril', 'amlodipine', 'atorvastatin',
            'omeprazole', 'levothyroxine', 'albuterol', 'prednisone', 'warfarin',
            'aspirin', 'ibuprofen', 'acetaminophen', 'amoxicillin', 'azithromycin',
            
            # Procedures
            'surgery', 'biopsy', 'endoscopy', 'colonoscopy', 'mammography',
            'ct scan', 'mri', 'x-ray', 'ultrasound', 'echocardiogram',
            'blood test', 'urinalysis', 'pathology', 'laboratory',
            
            # Body systems
            'cardiovascular', 'respiratory', 'gastrointestinal', 'neurological',
            'musculoskeletal', 'endocrine', 'renal', 'hepatic', 'dermatological',
            
            # Symptoms
            'chest pain', 'shortness of breath', 'nausea', 'vomiting', 'diarrhea',
            'constipation', 'headache', 'dizziness', 'fatigue', 'fever',
            'cough', 'sore throat', 'abdominal pain', 'back pain', 'joint pain'
        ]
        
        return medical_terms
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the search index"""
        total_docs = len(self.document_index)
        total_tokens = sum(len(doc['tokens']) for doc in self.document_index.values())
        
        return {
            'total_documents': total_docs,
            'total_tokens': total_tokens,
            'average_tokens_per_doc': total_tokens / total_docs if total_docs > 0 else 0,
            'medical_terms_count': len(self.medical_terms),
            'last_updated': datetime.now().isoformat()
        }