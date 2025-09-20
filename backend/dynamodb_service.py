import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from typing import Dict, List, Optional

class DynamoDBService:
    """Service for DynamoDB operations"""
    
    def __init__(self, table_name: str = "medical-documents"):
        self.dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-5')
        self.table_name = table_name
        self.table = None
        self.partition_key = 'id'  # Use 'id' as partition key (actual schema)
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Use existing table with 'pdf' partition key"""
        try:
            # Use existing table
            self.table = self.dynamodb.Table(self.table_name)
            self.table.load()
            print(f"✅ Using existing DynamoDB table: {self.table_name} (partition key: {self.partition_key})")
        except ClientError as e:
            print(f"❌ Error accessing table: {e}")
            raise e
    

    
    def save_document(self, document_metadata: Dict) -> bool:
        """Save document metadata to DynamoDB"""
        try:
            # Add timestamp
            document_metadata['created_at'] = datetime.utcnow().isoformat()
            document_metadata['updated_at'] = datetime.utcnow().isoformat()
            
            # Add pdf field for compatibility
            document_metadata['pdf'] = document_metadata['filename']
            
            self.table.put_item(Item=document_metadata)
            print(f"✅ Saved document metadata: {document_metadata['id']}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving document: {e}")
            return False
    
    def get_document(self, document_id: str) -> Optional[Dict]:
        """Get document metadata by ID"""
        try:
            response = self.table.get_item(Key={self.partition_key: document_id})
            return response.get('Item')
            
        except Exception as e:
            print(f"❌ Error getting document: {e}")
            return None
    
    def get_document_by_filename(self, filename: str) -> Optional[Dict]:
        """Get document metadata by filename (scan operation)"""
        try:
            response = self.table.scan(
                FilterExpression='filename = :filename',
                ExpressionAttributeValues={':filename': filename}
            )
            items = response.get('Items', [])
            return items[0] if items else None
            
        except Exception as e:
            print(f"❌ Error getting document by filename: {e}")
            return None
    
    def list_documents(self) -> List[Dict]:
        """List all documents"""
        try:
            response = self.table.scan()
            return response.get('Items', [])
            
        except Exception as e:
            print(f"❌ Error listing documents: {e}")
            return []
    
    def update_document(self, document_id: str, updates: Dict) -> bool:
        """Update document metadata by ID"""
        try:
            # Build update expression with attribute names
            update_expression = "SET "
            expression_values = {}
            expression_names = {}
            
            for key, value in updates.items():
                attr_name = f"#attr_{key}"
                attr_value = f":val_{key}"
                update_expression += f"{attr_name} = {attr_value}, "
                expression_values[attr_value] = value
                expression_names[attr_name] = key
            
            # Add updated timestamp
            update_expression += "#updated_at = :updated_at"
            expression_values[":updated_at"] = datetime.utcnow().isoformat()
            expression_names["#updated_at"] = "updated_at"
            
            self.table.update_item(
                Key={self.partition_key: document_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
                ExpressionAttributeNames=expression_names
            )
            
            print(f"✅ Updated document: {document_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating document: {e}")
            return False
    
    def delete_document(self, document_id: str) -> bool:
        """Delete document metadata by ID"""
        try:
            self.table.delete_item(Key={self.partition_key: document_id})
            print(f"✅ Deleted document: {document_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error deleting document: {e}")
            return False