import os
import json
from datetime import datetime
from typing import List, Dict, Any

import boto3

try:
    # opensearch-py client
    from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
except ImportError:
    # Minimal mock (dev fallback)
    class OpenSearch:
        def __init__(self, *args, **kwargs): pass
        def index(self, *args, **kwargs): return {'result': 'created'}
        def search(self, *args, **kwargs): return {'hits': {'hits': []}}
        def delete(self, *args, **kwargs): return {'result': 'deleted'}
        class indices:
            @staticmethod
            def exists(*args, **kwargs): return False
            @staticmethod
            def create(*args, **kwargs): return None
        def exists(self, *args, **kwargs): return False
        def count(self, *args, **kwargs): return {'count': 0}
    class RequestsHttpConnection: pass
    AWSV4SignerAuth = None


class OpenSearchService:
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'ap-southeast-1')
        # Example AOSS endpoint (no protocol, just host)
        # e.g. h4el4a2jw7d092zxn564.ap-southeast-1.aoss.amazonaws.com
        endpoint = os.getenv(
            'OPENSEARCH_ENDPOINT_HOST',
            'h4el4a2jw7d092zxn564.ap-southeast-1.aoss.amazonaws.com'
        )
        self.host = endpoint
        self.index_name = os.getenv('OPENSEARCH_INDEX', 'medical-documents')

        # Initialize OpenSearch client with SigV4 for AOSS
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            if credentials is None:
                raise RuntimeError("No AWS credentials found for SigV4.")

            auth = AWSV4SignerAuth(credentials, self.region, 'aoss')

            self.client = OpenSearch(
                hosts=[{'host': self.host, 'port': 443}],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection
            )
            print(f"✅ OpenSearch connected to https://{self.host}")
        except Exception as e:
            print(f"OpenSearch auth/init error: {e}")
            self.client = OpenSearch()  # fall back to mock

        self._create_index_if_not_exists()

    def _create_index_if_not_exists(self):
        """Create index with k-NN vector mapping for embeddings (AOSS/OpenSearch 2.x)."""
        try:
            exists = self.client.indices.exists(index=self.index_name)
        except Exception as e:
            print(f"Index exists check failed: {e}")
            exists = False

        if not exists:
            mapping = {
                "settings": {
                    "index": {
                        # Enable k-NN for vector search
                        "knn": True
                    }
                },
                "mappings": {
                    "properties": {
                        "content": {"type": "text", "analyzer": "standard"},
                        # Use knn_vector, not dense_vector, for OpenSearch
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": 1536  # Titan embed dimension
                            # Optional: "method": {"name": "hnsw", "engine": "nmslib", "space_type": "cosinesimil"}
                        },
                        "entities": {"type": "object"},  # JSON blob of entities
                        "metadata": {
                            "properties": {
                                "filename": {"type": "keyword"},
                                "categories": {"type": "keyword"},
                                "upload_date": {"type": "date"},
                                "file_size": {"type": "integer"}
                            }
                        },
                        "processed_date": {"type": "date"}
                    }
                }
            }

            try:
                self.client.indices.create(index=self.index_name, body=mapping)
                print(f"✅ Created OpenSearch index: {self.index_name}")
            except Exception as e:
                # If concurrent creation or already exists after all
                print(f"Index create skipped/failed: {e}")

    def index_document(self, doc_id: str, document: Dict[str, Any]) -> bool:
        """Index a processed document with embedding + metadata."""
        try:
            # Keep field names consistent with mapping
            doc_body = {
                "content": document.get("text", document.get("content", "")),
                "embedding": document.get("embedding") or document.get("embeddings", []),
                "entities": document.get("entities", {}),
                "metadata": document.get("metadata", {}),
                "processed_date": datetime.utcnow().isoformat()
            }

            # Basic validation
            vec = document.get("embedding") or document.get("embeddings", [])
            if vec and len(vec) != 1536:
                raise ValueError(f"Embedding length {len(vec)} != 1536")

            response = self.client.index(
                index=self.index_name,
                id=doc_id,
                body=doc_body
            )
            return response.get("result") in {"created", "updated"}
        except Exception as e:
            print(f"OpenSearch indexing error: {e}")
            return False

    def semantic_search(self, query: str, embeddings: List[float], size: int = 5) -> List[Dict[str, Any]]:
        """Hybrid search: vector k-NN + text query (multi_match)."""
        try:
            search_body = {
                "size": size,
                "query": {
                    "bool": {
                        "should": [
                            {
                                "knn": {
                                    "embedding": {
                                        "vector": embeddings,
                                        "k": size
                                    }
                                }
                            },
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["content^2", "metadata.filename"],
                                    "type": "best_fields",
                                    "boost": 0.3
                                }
                            }
                        ]
                    }
                },
                "_source": ["content", "metadata", "entities"]
            }

            response = self.client.search(index=self.index_name, body=search_body)
            hits = response.get("hits", {}).get("hits", [])

            results = []
            for hit in hits:
                src = hit.get("_source", {}) or {}
                md = src.get("metadata", {}) or {}
                results.append({
                    "id": hit.get("_id"),
                    "score": hit.get("_score"),
                    "content": src.get("content", ""),
                    "filename": md.get("filename", ""),
                    "categories": md.get("categories", []),
                    "entities": src.get("entities", {})
                })
            return results

        except Exception as e:
            print(f"OpenSearch search error: {e}")
            return []

    def search_by_category(self, categories: List[str], size: int = 10) -> List[Dict[str, Any]]:
        """Filter by metadata.categories."""
        try:
            search_body = {
                "size": size,
                "query": {
                    "terms": {
                        "metadata.categories": categories
                    }
                },
                "_source": ["content", "metadata", "entities"]
            }

            response = self.client.search(index=self.index_name, body=search_body)
            hits = response.get("hits", {}).get("hits", [])

            results = []
            for hit in hits:
                src = hit.get("_source", {}) or {}
                md = src.get("metadata", {}) or {}
                results.append({
                    "id": hit.get("_id"),
                    "score": hit.get("_score"),
                    "content": src.get("content", ""),
                    "filename": md.get("filename", ""),
                    "categories": md.get("categories", []),
                    "entities": src.get("entities", {})
                })
            return results

        except Exception as e:
            print(f"OpenSearch category search error: {e}")
            return []

    def check_document_exists(self, doc_id: str) -> bool:
        """Check if a document exists in the index."""
        try:
            return bool(self.client.exists(index=self.index_name, id=doc_id))
        except Exception as e:
            print(f"Error checking document existence: {e}")
            return False

    def get_index_stats(self) -> Dict[str, Any]:
        """Return a simple count + status."""
        try:
            response = self.client.count(index=self.index_name)
            return {
                "total_documents": response.get("count", 0),
                "status": "healthy"
            }
        except Exception as e:
            print(f"Error getting index stats: {e}")
            return {"total_documents": 0, "status": "error", "error": str(e)}

    def verify_upload(self, filename: str) -> Dict[str, Any]:
        """Verify if a PDF (by filename) is indexed with embedding."""
        try:
            search_body = {
                "size": 1,
                "query": {
                    "term": {
                        "metadata.filename": filename
                    }
                }
            }
            response = self.client.search(index=self.index_name, body=search_body)
            hits = response.get("hits", {}).get("hits", [])

            if hits:
                hit = hits[0]
                src = hit.get("_source", {}) or {}
                md = src.get("metadata", {}) or {}
                return {
                    "exists": True,
                    "document_id": hit.get("_id"),
                    "processed_date": src.get("processed_date"),
                    "content_length": len(src.get("content", "")),
                    "has_embeddings": bool(src.get("embedding")),
                    "categories": md.get("categories", []),
                    "entities_count": len(src.get("entities", {}))
                }
            return {"exists": False}

        except Exception as e:
            print(f"Error verifying upload: {e}")
            return {"exists": False, "error": str(e)}
