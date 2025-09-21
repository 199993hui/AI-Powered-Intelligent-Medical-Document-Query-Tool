#!/usr/bin/env python3
"""Comprehensive service checker for the medical query system"""

import os
import sys
import boto3
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_environment():
    """Check environment variables"""
    print("🔍 Environment Variables:")
    env_vars = [
        'AWS_REGION',
        'OPENSEARCH_ENDPOINT', 
        'OPENSEARCH_INDEX',
        'S3_BUCKET',
        'DYNAMODB_CHAT_TABLE',
        'DYNAMODB_DOCUMENTS_TABLE'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        status = "✅" if value else "❌"
        print(f"  {status} {var}: {value or 'Not set'}")
    
    return all(os.getenv(var) for var in env_vars)

def check_aws_credentials():
    """Check AWS credentials and permissions"""
    print("\n🔍 AWS Credentials:")
    try:
        session = boto3.Session()
        credentials = session.get_credentials()
        
        if credentials:
            print("  ✅ AWS credentials found")
            print(f"  📍 Region: {session.region_name or os.getenv('AWS_REGION')}")
            
            # Test STS (basic AWS connectivity)
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            print(f"  👤 Account: {identity.get('Account')}")
            print(f"  🔑 User/Role: {identity.get('Arn', '').split('/')[-1]}")
            
            return True
        else:
            print("  ❌ No AWS credentials found")
            return False
            
    except Exception as e:
        print(f"  ❌ AWS error: {e}")
        return False

def check_s3_service():
    """Check S3 service and bucket"""
    print("\n🔍 S3 Service:")
    try:
        s3 = boto3.client('s3', region_name=os.getenv('AWS_REGION'))
        bucket = os.getenv('S3_BUCKET')
        
        # Check if bucket exists and accessible
        s3.head_bucket(Bucket=bucket)
        print(f"  ✅ Bucket '{bucket}' accessible")
        
        # List objects in medical_documents prefix
        response = s3.list_objects_v2(Bucket=bucket, Prefix='medical_documents/', MaxKeys=5)
        count = response.get('KeyCount', 0)
        print(f"  📄 Documents in bucket: {count}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ S3 error: {e}")
        return False

def check_dynamodb_service():
    """Check DynamoDB tables"""
    print("\n🔍 DynamoDB Service:")
    try:
        dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION'))
        
        tables = [
            os.getenv('DYNAMODB_CHAT_TABLE'),
            os.getenv('DYNAMODB_DOCUMENTS_TABLE')
        ]
        
        results = []
        for table_name in tables:
            try:
                table = dynamodb.Table(table_name)
                table.load()
                print(f"  ✅ Table '{table_name}': {table.table_status}")
                results.append(True)
            except Exception as e:
                print(f"  ❌ Table '{table_name}': {e}")
                results.append(False)
        
        return all(results)
        
    except Exception as e:
        print(f"  ❌ DynamoDB error: {e}")
        return False

def check_opensearch_service():
    """Check OpenSearch service"""
    print("\n🔍 OpenSearch Service:")
    try:
        from opensearchpy import OpenSearch, AWSV4SignerAuth
        
        endpoint = os.getenv('OPENSEARCH_ENDPOINT')
        region = os.getenv('AWS_REGION')
        
        # Create client
        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAuth(credentials, region, 'aoss')
        
        client = OpenSearch(
            hosts=[endpoint],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True
        )
        
        # Test connection
        info = client.info()
        print(f"  ✅ OpenSearch connected")
        print(f"  🏷️  Cluster: {info.get('cluster_name', 'Unknown')}")
        
        # Check index
        index_name = os.getenv('OPENSEARCH_INDEX', 'medical-documents')
        if client.indices.exists(index=index_name):
            count = client.count(index=index_name)
            doc_count = count.get('count', 0)
            print(f"  📊 Index '{index_name}': {doc_count} documents")
        else:
            print(f"  📄 Index '{index_name}': Not created yet")
        
        return True
        
    except Exception as e:
        print(f"  ❌ OpenSearch error: {e}")
        return False

def check_bedrock_service():
    """Check AWS Bedrock service"""
    print("\n🔍 Bedrock Service:")
    try:
        bedrock = boto3.client('bedrock-runtime', region_name=os.getenv('AWS_REGION'))
        
        # Test with a simple embedding request
        response = bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v1",
            body='{"texts": ["test"], "input_type": "search_document"}'
        )
        
        print("  ✅ Bedrock Titan Embeddings: Available")
        
        # Test Nova Pro model
        try:
            response = bedrock.invoke_model(
                modelId="us.amazon.nova-pro-v1:0",
                body='{"messages": [{"role": "user", "content": [{"text": "Hello"}]}], "inferenceConfig": {"max_new_tokens": 10}}'
            )
            print("  ✅ Bedrock Nova Pro: Available")
        except Exception as e:
            print(f"  ⚠️  Bedrock Nova Pro: {e}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Bedrock error: {e}")
        return False

def check_flask_server():
    """Check Flask server"""
    print("\n🔍 Flask Server:")
    try:
        # Check health endpoint
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("  ✅ Server running on port 8000")
            
            # Check system status
            status_response = requests.get("http://localhost:8000/api/system/status")
            if status_response.status_code == 200:
                data = status_response.json()
                print(f"  📊 System status: {data.get('status')}")
                services = data.get('services', {})
                for service, available in services.items():
                    status = "✅" if available else "❌"
                    print(f"    {status} {service}")
                return True
            else:
                print("  ⚠️  System status endpoint failed")
                return False
        else:
            print(f"  ❌ Server not responding: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Flask server error: {e}")
        return False

def check_python_dependencies():
    """Check Python dependencies"""
    print("\n🔍 Python Dependencies:")
    
    dependencies = [
        ('flask', 'Flask'),
        ('flask_cors', 'Flask-CORS'),
        ('boto3', 'AWS SDK'),
        ('opensearchpy', 'OpenSearch'),
        ('PyPDF2', 'PDF Processing'),
        ('fitz', 'PyMuPDF'),
        ('camelot', 'Table Extraction'),
        ('dotenv', 'Environment Loading')
    ]
    
    results = []
    for module, name in dependencies:
        try:
            __import__(module)
            print(f"  ✅ {name}")
            results.append(True)
        except ImportError:
            print(f"  ❌ {name}")
            results.append(False)
    
    return all(results)

def main():
    print("🚀 Comprehensive Service Check")
    print("=" * 50)
    
    checks = [
        ("Environment Variables", check_environment),
        ("Python Dependencies", check_python_dependencies),
        ("AWS Credentials", check_aws_credentials),
        ("S3 Service", check_s3_service),
        ("DynamoDB Service", check_dynamodb_service),
        ("OpenSearch Service", check_opensearch_service),
        ("Bedrock Service", check_bedrock_service),
        ("Flask Server", check_flask_server)
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n❌ {name} check failed: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Service Check Summary:")
    print("-" * 30)
    
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {name}")
    
    passed_count = sum(results.values())
    total_count = len(results)
    
    print(f"\n🎯 Overall: {passed_count}/{total_count} services operational")
    
    if passed_count == total_count:
        print("🎉 All services are working! System is ready for use.")
    else:
        print("🔧 Some services need attention. Check the failed items above.")
        
        # Provide specific guidance
        if not results.get("Flask Server"):
            print("\n💡 To start Flask server:")
            print("   python3 app.py")
        
        if not results.get("OpenSearch Service"):
            print("\n💡 OpenSearch issues are common. Check:")
            print("   - AWS credentials have OpenSearch permissions")
            print("   - Endpoint URL is correct")
            print("   - Network connectivity")

if __name__ == "__main__":
    main()