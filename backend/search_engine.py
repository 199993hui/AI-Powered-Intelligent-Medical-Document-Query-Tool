import boto3
import json
from typing import List, Dict, Any
import re
from flask import Flask, request, jsonify

class MedicalSearchEngine:
    def __init__(self):
        # AWS clients
        self.bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        self.comprehend_medical = boto3.client('comprehendmedical', region_name='us-east-1')
        self.opensearch = boto3.client('opensearch', region_name='us-east-1')
        self.s3 = boto3.client('s3')
        
        # Medical abbreviations mapping
        self.medical_abbreviations = {
            'bp': 'blood pressure',
            'hr': 'heart rate',
            'cbc': 'complete blood count',
            'ecg': 'electrocardiogram',
            'mri': 'magnetic resonance imaging',
            'ct': 'computed tomography',
            'bmi': 'body mass index',
            'copd': 'chronic obstructive pulmonary disease',
            'mi': 'myocardial infarction',
            'dvt': 'deep vein thrombosis'
        }
    
    def process_query(self, query: str, user_context: Dict = None) -> Dict[str, Any]:
        """Main query processing pipeline"""
        try:
            # Step 1: Expand medical abbreviations
            expanded_query = self._expand_abbreviations(query)
            
            # Step 2: Extract medical entities
            medical_entities = self._extract_medical_entities(expanded_query)
            
            # Step 3: Generate search embeddings
            search_terms = self._generate_search_terms(expanded_query, medical_entities)
            
            # Step 4: Classify query intent
            intent = self._classify_intent(expanded_query)
            
            return {
                'original_query': query,
                'expanded_query': expanded_query,
                'medical_entities': medical_entities,
                'search_terms': search_terms,
                'intent': intent,
                'status': 'success'
            }
        except Exception as e:
            return {'error': str(e), 'status': 'error'}
    
    def _expand_abbreviations(self, query: str) -> str:
        """Expand medical abbreviations in the query"""
        words = query.lower().split()
        expanded_words = []
        
        for word in words:
            # Remove punctuation for matching
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word in self.medical_abbreviations:
                expanded_words.append(self.medical_abbreviations[clean_word])
            else:
                expanded_words.append(word)
        
        return ' '.join(expanded_words)
    
    def _extract_medical_entities(self, query: str) -> Dict[str, List[str]]:
        """Extract medical entities using Amazon Comprehend Medical"""
        try:
            response = self.comprehend_medical.detect_entities_v2(Text=query)
            
            entities = {
                'medications': [],
                'conditions': [],
                'anatomy': [],
                'procedures': [],
                'test_results': []
            }
            
            for entity in response.get('Entities', []):
                entity_type = entity.get('Category', '').lower()
                entity_text = entity.get('Text', '')
                
                if entity_type == 'medication':
                    entities['medications'].append(entity_text)
                elif entity_type == 'medical_condition':
                    entities['conditions'].append(entity_text)
                elif entity_type == 'anatomy':
                    entities['anatomy'].append(entity_text)
                elif entity_type == 'test_treatment_procedure':
                    entities['procedures'].append(entity_text)
                elif entity_type == 'test_result':
                    entities['test_results'].append(entity_text)
            
            return entities
        except Exception as e:
            print(f"Error extracting medical entities: {e}")
            return {}
    
    def _generate_search_terms(self, query: str, entities: Dict) -> List[str]:
        """Generate optimized search terms"""
        search_terms = [query]
        
        # Add individual entities as search terms
        for entity_list in entities.values():
            search_terms.extend(entity_list)
        
        # Add medical synonyms using Bedrock
        try:
            prompt = f"Generate medical synonyms and related terms for: {query}"
            response = self._call_bedrock(prompt)
            if response:
                # Parse synonyms from response (simplified)
                synonyms = response.split(',')[:5]  # Limit to 5 synonyms
                search_terms.extend([s.strip() for s in synonyms])
        except Exception as e:
            print(f"Error generating synonyms: {e}")
        
        return list(set(search_terms))  # Remove duplicates
    
    def _classify_intent(self, query: str) -> str:
        """Classify the intent of the query"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['patient', 'record', 'history']):
            return 'patient_query'
        elif any(word in query_lower for word in ['protocol', 'guideline', 'treatment']):
            return 'clinical_guideline'
        elif any(word in query_lower for word in ['research', 'study', 'trial']):
            return 'research_query'
        elif any(word in query_lower for word in ['medication', 'drug', 'prescription']):
            return 'medication_query'
        else:
            return 'general_medical'
    
    def _call_bedrock(self, prompt: str) -> str:
        """Call Amazon Bedrock for AI processing"""
        try:
            body = json.dumps({
                "prompt": prompt,
                "max_tokens": 100,
                "temperature": 0.3
            })
            
            response = self.bedrock.invoke_model(
                body=body,
                modelId="anthropic.claude-v2",
                accept="application/json",
                contentType="application/json"
            )
            
            response_body = json.loads(response.get('body').read())
            return response_body.get('completion', '')
        except Exception as e:
            print(f"Bedrock error: {e}")
            return ""
    
    def search_documents(self, processed_query: Dict, limit: int = 10) -> List[Dict]:
        """Search documents using processed query (placeholder for OpenSearch integration)"""
        # This would integrate with Amazon OpenSearch Service
        # For now, return mock results
        return [
            {
                'document_id': 'doc_001',
                'filename': 'patient_record_john_doe.pdf',
                'relevance_score': 0.95,
                'matched_terms': processed_query['search_terms'][:3],
                'excerpt': 'Patient John Doe, age 45, diagnosed with hypertension...'
            }
        ]

# Flask API endpoints
app = Flask(__name__)
search_engine = MedicalSearchEngine()

@app.route('/api/search/query', methods=['POST'])
def process_search_query():
    """Process natural language query"""
    data = request.get_json()
    query = data.get('query', '')
    user_context = data.get('user_context', {})
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    result = search_engine.process_query(query, user_context)
    return jsonify(result)

@app.route('/api/search/documents', methods=['POST'])
def search_documents():
    """Search documents using processed query"""
    data = request.get_json()
    processed_query = data.get('processed_query', {})
    limit = data.get('limit', 10)
    
    results = search_engine.search_documents(processed_query, limit)
    return jsonify({'results': results, 'count': len(results)})

@app.route('/api/search/suggestions', methods=['GET'])
def get_query_suggestions():
    """Get query suggestions"""
    partial_query = request.args.get('q', '')
    
    # Mock suggestions - would be enhanced with ML
    suggestions = [
        f"What medications is {partial_query}",
        f"Show me {partial_query} treatment protocols",
        f"Find {partial_query} lab results",
        f"Patient records for {partial_query}"
    ]
    
    return jsonify({'suggestions': suggestions[:5]})

if __name__ == '__main__':
    app.run(debug=True, port=8001)