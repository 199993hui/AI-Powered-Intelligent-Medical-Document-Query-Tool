# services/opensearch_service.py
import os
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")
INDEX_NAME = os.getenv("OPENSEARCH_INDEX", "medical_docs")

def get_os_client():
    endpoint = os.getenv("OPENSEARCH_ENDPOINT")  # must be your *collection* (AOSS) or domain (Managed) endpoint
    if not endpoint:
        raise ValueError("❌ OPENSEARCH_ENDPOINT not set in .env")

    is_aoss = ".aoss." in endpoint  # serverless?
    service = "aoss" if is_aoss else "es"

    session = boto3.Session(region_name=AWS_REGION)
    creds = session.get_credentials()
    auth = AWSV4SignerAuth(creds, AWS_REGION, service=service)

    host = endpoint.replace("https://", "").replace("http://", "")
    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )

    # Only ping for Managed domains; AOSS will 404 on root
    if not is_aoss:
        try:
            _ = client.info()
            print("✅ OpenSearch managed domain reachable")
        except Exception as e:
            print("❌ OS info failed (managed):", e)

    return client

def create_index(os_client):
    body = {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "page": {"type": "integer"},
                "text": {"type": "text"},
                "categories": {"type": "keyword"},
                "s3_key": {"type": "keyword"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 384,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "faiss",
                        "parameters": {"ef_construction": 128, "m": 16}
                    }
                }
            }
        }
    }
    try:
        if not os_client.indices.exists(index=INDEX_NAME):
            os_client.indices.create(index=INDEX_NAME, body=body)
            print("✅ Created index:", INDEX_NAME)
        else:
            print("ℹ️ Index exists:", INDEX_NAME)
    except Exception as e:
        print("⚠️ create_index failed:", e)


def index_chunk(os_client, doc_id, s3_key, categories, chunk):
    body = {
        "doc_id": doc_id,
        "page": chunk["page"],
        "text": chunk["text"],
        "categories": categories,
        "s3_key": s3_key,
        "embedding": chunk["embedding"],
    }
    return os_client.index(index=INDEX_NAME, body=body)

def search_similar(os_client, query_vector, top_k=5):
    """KNN search in OpenSearch Serverless using embedding vector."""
    body = {
        "size": top_k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": query_vector,
                    "k": top_k
                }
            }
        }
    }
    return os_client.search(index=INDEX_NAME, body=body)
