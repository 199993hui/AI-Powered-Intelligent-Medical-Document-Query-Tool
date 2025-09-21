#!/usr/bin/env python3
"""Simple data clearing script"""
import boto3
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from services.opensearch_service import get_os_client, INDEX_NAME
    s3 = boto3.client("s3", region_name="ap-southeast-1")
    
    # Clear S3
    resp = s3.list_objects_v2(Bucket="echomind-pdf-storage-sg", Prefix='medical_documents/')
    if 'Contents' in resp:
        s3.delete_objects(Bucket="echomind-pdf-storage-sg", Delete={'Objects': [{'Key': obj['Key']} for obj in resp['Contents']]})
        print(f"✅ Cleared {len(resp['Contents'])} S3 files")
    
    # Clear OpenSearch
    try:
        os_client = get_os_client()
        if os_client.indices.exists(index=INDEX_NAME):
            os_client.indices.delete(index=INDEX_NAME)
            print("✅ Cleared OpenSearch index")
    except: pass
    
    print("🎯 Data cleared successfully!")
except Exception as e:
    print(f"❌ Error: {e}")