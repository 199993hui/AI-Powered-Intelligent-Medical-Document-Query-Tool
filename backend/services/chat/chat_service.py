import boto3
import json
import uuid
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..ai.bedrock_service import BedrockService
from ..storage.opensearch_service import OpenSearchService
from ..document.document_processor import DocumentProcessor

class ChatService:
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'ap-southeast-1')
        self.chat_table = os.getenv('DYNAMODB_CHAT_TABLE', 'chat-history')
        
        try:
            self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
            self.table = self.dynamodb.Table(self.chat_table)
        except Exception as e:
            print(f"DynamoDB connection failed: {str(e)}")
            self.table = None
        
        try:
            self.bedrock_service = BedrockService()
        except Exception as e:
            print(f"Bedrock service failed: {str(e)}")
            self.bedrock_service = None
            
        try:
            self.opensearch_service = OpenSearchService()
        except Exception as e:
            print(f"OpenSearch service failed: {str(e)}")
            self.opensearch_service = None
            
        try:
            self.document_processor = DocumentProcessor()
        except Exception as e:
            print(f"Document processor failed: {str(e)}")
            self.document_processor = None
    
    def process_query(self, query: str, session_id: str = None, history: List[Dict] = None) -> Dict[str, Any]:
        """Process a chat query and return structured response"""
        try:
            # Generate session ID if not provided
            if not session_id:
                session_id = str(uuid.uuid4())
            
            # Check if OpenSearch has data
            if self.opensearch_service:
                stats = self.opensearch_service.get_index_stats()
                if stats.get('total_documents', 0) == 0:
                    return {
                        'sessionId': session_id,
                        'messageId': str(uuid.uuid4()),
                        'query': query,
                        'response': {
                            'answer': 'No medical documents are currently available in the system. Please upload some PDF documents first to enable AI-powered medical queries.',
                            'confidence': 1.0,
                            'sources': [],
                            'followUpQuestions': ['How do I upload medical documents?', 'What types of documents are supported?']
                        },
                        'timestamp': datetime.now().isoformat(),
                        'relevantDocuments': 0
                    }
            
            # Check if services are available
            if not self.bedrock_service or not self.opensearch_service:
                return self._fallback_response(query, session_id)
            
            # Get query embeddings for semantic search
            query_embeddings = self.bedrock_service.create_embeddings(query)
            
            if not query_embeddings:
                # Fallback to text-based search
                relevant_docs = self._text_based_search(query)
            else:
                # Search for relevant documents using embeddings
                relevant_docs = self.opensearch_service.semantic_search(
                    query=query,
                    embeddings=query_embeddings,
                    size=5
                )
            
            # Generate AI response
            ai_response = self.bedrock_service.generate_medical_response(
                query=query,
                context=relevant_docs,
                history=history or []
            )
            
            # Save conversation to DynamoDB if available
            message_id = str(uuid.uuid4())
            if self.table:
                try:
                    self._save_conversation(session_id, message_id, query, ai_response)
                except Exception as e:
                    print(f"Failed to save conversation: {str(e)}")
            
            # Return structured response
            return {
                'sessionId': session_id,
                'messageId': message_id,
                'query': query,
                'response': ai_response,
                'timestamp': datetime.now().isoformat(),
                'relevantDocuments': len(relevant_docs),
                'searchMethod': 'semantic' if query_embeddings else 'text'
            }
            
        except Exception as e:
            print(f"Chat processing error: {str(e)}")
            return self._fallback_response(query, session_id, str(e))
    
    def get_chat_history(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve chat history for a session"""
        try:
            response = self.table.query(
                KeyConditionExpression='session_id = :sid',
                ExpressionAttributeValues={':sid': session_id},
                ScanIndexForward=False,  # Most recent first
                Limit=limit
            )
            
            messages = []
            for item in response.get('Items', []):
                messages.append({
                    'messageId': item.get('message_id'),
                    'type': item.get('message_type'),
                    'content': item.get('content'),
                    'timestamp': item.get('timestamp'),
                    'sources': json.loads(item.get('sources', '[]')),
                    'confidence': item.get('confidence', 0.0)
                })
            
            return list(reversed(messages))  # Return chronological order
            
        except Exception as e:
            print(f"Chat history error: {str(e)}")
            return []
    
    def save_feedback(self, session_id: str, message_id: str, feedback: str, rating: int = None) -> bool:
        """Save user feedback for a response"""
        try:
            self.table.update_item(
                Key={
                    'session_id': session_id,
                    'message_id': message_id
                },
                UpdateExpression='SET feedback = :feedback, rating = :rating, feedback_date = :date',
                ExpressionAttributeValues={
                    ':feedback': feedback,
                    ':rating': rating,
                    ':date': datetime.now().isoformat()
                }
            )
            return True
            
        except Exception as e:
            print(f"Feedback save error: {str(e)}")
            return False
    
    def _save_conversation(self, session_id: str, message_id: str, query: str, response: Dict[str, Any]):
        """Save conversation to DynamoDB"""
        if not self.table:
            print("DynamoDB table not available, skipping conversation save")
            return
            
        try:
            timestamp = datetime.now().isoformat()
            
            # Save user message
            self.table.put_item(
                Item={
                    'session_id': session_id,
                    'message_id': f"{message_id}_user",
                    'message_type': 'user',
                    'content': query,
                    'timestamp': timestamp,
                    'ttl': int(datetime.now().timestamp()) + (30 * 24 * 60 * 60)  # 30 days TTL
                }
            )
            
            # Save assistant response
            self.table.put_item(
                Item={
                    'session_id': session_id,
                    'message_id': f"{message_id}_assistant",
                    'message_type': 'assistant',
                    'content': response.get('answer', ''),
                    'sources': json.dumps(response.get('sources', [])),
                    'confidence': response.get('confidence', 0.0),
                    'follow_up_questions': json.dumps(response.get('followUpQuestions', [])),
                    'timestamp': timestamp,
                    'ttl': int(datetime.now().timestamp()) + (30 * 24 * 60 * 60)  # 30 days TTL
                }
            )
            
        except Exception as e:
            print(f"Conversation save error: {str(e)}")
    
    def _fallback_response(self, query: str, session_id: str, error: str = None) -> Dict[str, Any]:
        """Provide fallback response when AI services are unavailable"""
        return {
            'sessionId': session_id,
            'messageId': str(uuid.uuid4()),
            'query': query,
            'response': {
                'answer': f'I apologize, but the AI services are currently unavailable. {error or "Please ensure AWS Bedrock and OpenSearch are properly configured."}',
                'confidence': 0.0,
                'sources': [],
                'followUpQuestions': ['How can I check system status?', 'When will services be available?']
            },
            'timestamp': datetime.now().isoformat(),
            'relevantDocuments': 0,
            'error': error
        }
    
    def _text_based_search(self, query: str) -> List[Dict[str, Any]]:
        """Fallback text-based search when embeddings are not available"""
        try:
            # Simple text search in OpenSearch
            search_body = {
                'query': {
                    'multi_match': {
                        'query': query,
                        'fields': ['content^2', 'metadata.filename'],
                        'type': 'best_fields'
                    }
                },
                'size': 5,
                '_source': ['content', 'metadata', 'entities']
            }
            
            response = self.opensearch_service.client.search(
                index=self.opensearch_service.index_name, 
                body=search_body
            )
            
            results = []
            for hit in response.get('hits', {}).get('hits', []):
                results.append({
                    'id': hit['_id'],
                    'score': hit['_score'],
                    'content': hit['_source'].get('content', ''),
                    'filename': hit['_source'].get('metadata', {}).get('filename', ''),
                    'categories': hit['_source'].get('metadata', {}).get('categories', []),
                    'entities': hit['_source'].get('entities', {})
                })
            
            return results
            
        except Exception as e:
            print(f"Text search error: {str(e)}")
            return []
    
    def create_session(self) -> str:
        """Create a new chat session"""
        return str(uuid.uuid4())
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get status of all AI services"""
        status = {
            'bedrock': bool(self.bedrock_service),
            'opensearch': bool(self.opensearch_service),
            'dynamodb': bool(self.table),
            'document_processor': bool(self.document_processor)
        }
        
        if self.opensearch_service:
            stats = self.opensearch_service.get_index_stats()
            status['documents_available'] = stats.get('total_documents', 0)
            status['opensearch_status'] = stats.get('status', 'unknown')
        
        return status
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summary information about a chat session"""
        try:
            response = self.table.query(
                KeyConditionExpression='session_id = :sid',
                ExpressionAttributeValues={':sid': session_id},
                Select='COUNT'
            )
            
            return {
                'sessionId': session_id,
                'messageCount': response.get('Count', 0),
                'lastActivity': datetime.now().isoformat()  # Would need to track this properly
            }
            
        except Exception as e:
            print(f"Session summary error: {str(e)}")
            return {'sessionId': session_id, 'messageCount': 0}