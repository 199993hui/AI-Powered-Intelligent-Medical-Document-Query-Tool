import boto3
import json
import os
from typing import List, Dict, Any
from datetime import datetime

class BedrockService:
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'ap-southeast-1')
        self.model_id = os.getenv('BEDROCK_MODEL_ID', 'amazon.nova-pro-v1:0')
        self.client = boto3.client('bedrock-runtime', region_name=self.region)
    
    def generate_medical_response(self, query: str, context: List[Dict], history: List[Dict] = None) -> Dict[str, Any]:
        """Generate medical response using Bedrock Nova Pro model"""
        try:
            prompt = self._build_medical_prompt(query, context, history or [])
            
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    'messages': [{'role': 'user', 'content': [{'text': prompt}]}],
                    'inferenceConfig': {
                        'max_new_tokens': 1000,
                        'temperature': 0.1,
                        'top_p': 0.9
                    }
                })
            )
            
            result = json.loads(response['body'].read())
            return self._parse_response(result, context)
            
        except Exception as e:
            print(f"Bedrock error: {str(e)}")
            return {
                'answer': 'I apologize, but I encountered an error processing your request.',
                'confidence': 0.0,
                'sources': [],
                'followUpQuestions': []
            }
    
    def create_embeddings(self, text: str) -> List[float]:
        try:
            resp = self.client.invoke_model(
                modelId="amazon.titan-embed-text-v1",
                body=json.dumps({"inputText": text})
            )
            data = json.loads(resp["body"].read())
            return data.get("embedding", [])  # list[float], len=1536
        except Exception as e:
            print(f"Embedding error: {str(e)}")
            return []
    
    def _build_medical_prompt(self, query: str, context: List[Dict], history: List[Dict]) -> str:
        """Build medical-focused prompt with context"""
        context_text = ""
        if context:
            context_text = "\n\nRelevant medical documents:\n"
            for i, doc in enumerate(context[:3]):  # Top 3 most relevant
                context_text += f"{i+1}. {doc.get('filename', 'Unknown')}: {doc.get('content', '')[:500]}...\n"
        
        history_text = ""
        if history:
            history_text = "\n\nConversation history:\n"
            for msg in history[-3:]:  # Last 3 messages
                role = msg.get('type', 'user')
                content = msg.get('content', '')
                history_text += f"{role}: {content}\n"
        
        prompt = f"""You are a medical AI assistant helping healthcare professionals analyze medical documents. 
        
Provide accurate, evidence-based responses with proper citations. Always include:
1. Clear, structured medical information
2. Source citations from the provided documents
3. Confidence level in your response
4. Follow-up questions that might be relevant

{history_text}

{context_text}

Current question: {query}

Please provide a comprehensive medical response with citations."""
        
        return prompt
    
    def _parse_response(self, result: Dict, context: List[Dict]) -> Dict[str, Any]:
        """Parse Bedrock response into structured format"""
        content = result.get('content', [{}])[0].get('text', '')
        
        return {
            'answer': content,
            'confidence': 0.85,  # Default confidence
            'sources': [
                {
                    'documentId': doc.get('id', ''),
                    'filename': doc.get('filename', ''),
                    'relevanceScore': doc.get('score', 0.0),
                    'excerpt': doc.get('content', '')[:200] + '...'
                }
                for doc in context[:3]
            ],
            'followUpQuestions': [
                "What are the potential side effects?",
                "Are there any contraindications?",
                "What is the recommended dosage?"
            ]
        }
    
    def analyze_medical_document(self, document_text: str) -> Dict[str, Any]:
        """Analyze medical document content using Nova Pro"""
        try:
            analysis_prompt = f"""Analyze this medical document and extract key information:

{document_text[:3000]}...

Please provide:
1. Document type and purpose
2. Key medical findings
3. Medications mentioned
4. Conditions or diagnoses
5. Treatment recommendations
6. Important dates or follow-up requirements

Format your response as structured medical information."""
            
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    'messages': [{'role': 'user', 'content': [{'text': analysis_prompt}]}],
                    'inferenceConfig': {
                        'max_new_tokens': 1500,
                        'temperature': 0.1,
                        'top_p': 0.9
                    }
                })
            )
            
            result = json.loads(response['body'].read())
            content = result.get('content', [{}])[0].get('text', '')
            
            return {
                'analysis': content,
                'confidence': 0.90,
                'analysis_date': datetime.now().isoformat(),
                'model_used': self.model_id
            }
            
        except Exception as e:
            print(f"Medical document analysis error: {str(e)}")
            return {
                'analysis': 'Analysis failed due to service unavailability.',
                'confidence': 0.0,
                'error': str(e)
            }