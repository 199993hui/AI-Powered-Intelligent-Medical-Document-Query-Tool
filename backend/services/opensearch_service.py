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

def recreate_index(os_client):
    """Delete and recreate index with new mapping"""
    try:
        if os_client.indices.exists(index=INDEX_NAME):
            os_client.indices.delete(index=INDEX_NAME)
            print(f"🗑️ Deleted existing index: {INDEX_NAME}")
        create_index(os_client)
    except Exception as e:
        print(f"⚠️ recreate_index failed: {e}")

def create_index(os_client):
    body = {
        "settings": {
            "index": {"knn": True},
            "analysis": {
                "analyzer": {
                    "medical_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": [
                            "lowercase",
                            "medical_synonyms",
                            "medical_stemmer",
                            "stop"
                        ]
                    },
                    "dosage_analyzer": {
                        "type": "custom",
                        "tokenizer": "keyword",
                        "filter": ["lowercase"]
                    }
                },
                "filter": {
                    "medical_synonyms": {
                        "type": "synonym",
                        "synonyms": [
                            "mg,milligram,milligrams",
                            "ml,milliliter,milliliters",
                            "mcg,microgram,micrograms",
                            "hypertension,high blood pressure",
                            "diabetes,diabetes mellitus,dm",
                            "myocardial infarction,heart attack,mi",
                            "copd,chronic obstructive pulmonary disease"
                        ]
                    },
                    "medical_stemmer": {
                        "type": "stemmer",
                        "language": "english"
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "page": {"type": "integer"},
                "text": {
                    "type": "text",
                    "analyzer": "medical_analyzer",
                    "fields": {
                        "exact": {
                            "type": "keyword"
                        },
                        "dosage": {
                            "type": "text",
                            "analyzer": "dosage_analyzer"
                        }
                    }
                },
                "categories": {"type": "keyword"},
                "s3_key": {"type": "keyword"},
                "chunk_type": {"type": "keyword"},
                "content_type": {"type": "keyword"},
                "section_header": {
                    "type": "text",
                    "analyzer": "medical_analyzer",
                    "boost": 2.0
                },
                # Document-level metadata
                "document_metadata": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "keyword"},
                        "upload_date": {"type": "date"},
                        "file_size": {"type": "long"},
                        "total_pages": {"type": "integer"},
                        "document_type": {"type": "keyword"},
                        "medical_specialty": {"type": "keyword"},
                        "language": {"type": "keyword"}
                    }
                },
                # Chunk-level metadata
                "chunk_metadata": {
                    "type": "object",
                    "properties": {
                        "word_count": {"type": "integer"},
                        "sentence_count": {"type": "integer"},
                        "importance_score": {"type": "float"},
                        "medical_entities": {
                            "type": "nested",
                            "properties": {
                                "entity": {"type": "keyword"},
                                "type": {"type": "keyword"},
                                "confidence": {"type": "float"}
                            }
                        },
                        "medical_entities_text": {"type": "keyword"},
                        "contains_dosage": {"type": "boolean"},
                        "contains_procedure": {"type": "boolean"},
                        "contains_diagnosis": {"type": "boolean"},
                        "readability_score": {"type": "float"}
                    }
                },
                # Hierarchical categories
                "category_hierarchy": {
                    "type": "object",
                    "properties": {
                        "primary_category": {"type": "keyword"},
                        "subcategory": {"type": "keyword"},
                        "medical_domain": {"type": "keyword"},
                        "urgency_level": {"type": "keyword"}
                    }
                },
                # Multi-vector embeddings
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 384,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "faiss",
                        "parameters": {"ef_construction": 128, "m": 16}
                    }
                },
                "medical_embedding": {
                    "type": "knn_vector",
                    "dimension": 384,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "faiss",
                        "parameters": {"ef_construction": 128, "m": 16}
                    }
                },
                "sparse_vector": {
                    "type": "object",
                    "properties": {
                        "medical_terms": {"type": "float"},
                        "drug_names": {"type": "float"},
                        "procedures": {"type": "float"},
                        "conditions": {"type": "float"},
                        "dosages": {"type": "float"}
                    }
                },
                # Advanced search fields
                "boost_factors": {
                    "type": "object",
                    "properties": {
                        "content_boost": {"type": "float"},
                        "recency_boost": {"type": "float"},
                        "importance_boost": {"type": "float"}
                    }
                },
                "search_keywords": {
                    "type": "text",
                    "analyzer": "keyword",
                    "boost": 1.5
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


def index_chunk(os_client, doc_id, s3_key, categories, chunk, document_metadata=None):
    # Handle medical entities - convert nested objects to proper format
    chunk_metadata = chunk.get("chunk_metadata", {})
    medical_entities = chunk_metadata.get("medical_entities", [])
    
    # Create both nested and text versions
    if medical_entities and isinstance(medical_entities[0], dict):
        # Already in nested format
        medical_entities_nested = medical_entities
        medical_entities_text = [entity['entity'] for entity in medical_entities]
    else:
        # Convert simple strings to nested format
        medical_entities_nested = [{'entity': entity, 'type': 'unknown', 'confidence': 0.5} for entity in medical_entities]
        medical_entities_text = medical_entities
    
    # Update chunk metadata with both formats
    updated_chunk_metadata = chunk_metadata.copy()
    updated_chunk_metadata['medical_entities'] = medical_entities_nested
    updated_chunk_metadata['medical_entities_text'] = medical_entities_text
    
    body = {
        "doc_id": doc_id,
        "page": chunk["page"],
        "text": chunk["text"],
        "categories": categories,
        "s3_key": s3_key,
        "embedding": chunk["embedding"],
        "medical_embedding": chunk.get("medical_embedding", chunk["embedding"]),
        "sparse_vector": chunk.get("sparse_vector", {}),
        "chunk_type": chunk.get("chunk_type", "basic"),
        "content_type": chunk.get("content_type", "paragraph"),
        "section_header": chunk.get("section_header", ""),
        "chunk_metadata": updated_chunk_metadata,
        "document_metadata": document_metadata or {},
        "category_hierarchy": chunk.get("category_hierarchy", {}),
        "boost_factors": chunk.get("boost_factors", {}),
        "search_keywords": chunk.get("search_keywords", "")
    }
    return os_client.index(index=INDEX_NAME, body=body)

def search_advanced(os_client, query_text, query_vector=None, medical_vector=None, 
                   filters=None, boost_important=True, top_k=5):
    """Advanced search with custom scoring, filtering, and boosting"""
    
    # Build multi-match query with custom scoring
    text_query = {
        "multi_match": {
            "query": query_text,
            "fields": [
                "text^1.0",
                "text.dosage^2.0",
                "section_header^3.0",
                "search_keywords^2.5"
            ],
            "type": "best_fields",
            "fuzziness": "AUTO"
        }
    }
    
    # Vector queries
    vector_queries = []
    if query_vector:
        vector_queries.append({
            "knn": {
                "embedding": {
                    "vector": query_vector,
                    "k": top_k * 2
                }
            }
        })
    
    if medical_vector:
        vector_queries.append({
            "knn": {
                "medical_embedding": {
                    "vector": medical_vector,
                    "k": top_k * 2
                }
            }
        })
    
    # Combine text and vector queries
    should_queries = [text_query] + vector_queries
    
    # Apply filters
    filter_conditions = []
    if filters:
        if filters.get("content_type"):
            filter_conditions.append({"term": {"content_type": filters["content_type"]}})
        if filters.get("medical_specialty"):
            filter_conditions.append({"term": {"document_metadata.medical_specialty": filters["medical_specialty"]}})
        if filters.get("urgency_level"):
            filter_conditions.append({"term": {"category_hierarchy.urgency_level": filters["urgency_level"]}})
        if filters.get("contains_dosage"):
            filter_conditions.append({"term": {"chunk_metadata.contains_dosage": True}})
    
    # Build query with custom scoring
    query = {
        "bool": {
            "should": should_queries,
            "minimum_should_match": 1
        }
    }
    
    if filter_conditions:
        query["bool"]["filter"] = filter_conditions
    
    # Custom scoring with function_score
    if boost_important:
        query = {
            "function_score": {
                "query": query,
                "functions": [
                    {
                        "field_value_factor": {
                            "field": "chunk_metadata.importance_score",
                            "factor": 2.0,
                            "modifier": "log1p",
                            "missing": 0.5
                        }
                    },
                    {
                        "filter": {"term": {"content_type": "medication"}},
                        "weight": 1.5
                    },
                    {
                        "filter": {"term": {"content_type": "diagnosis"}},
                        "weight": 1.3
                    },
                    {
                        "filter": {"term": {"chunk_type": "section"}},
                        "weight": 1.2
                    }
                ],
                "score_mode": "multiply",
                "boost_mode": "multiply"
            }
        }
    
    body = {
        "size": top_k,
        "query": query,
        "highlight": {
            "fields": {
                "text": {
                    "fragment_size": 150,
                    "number_of_fragments": 3
                },
                "section_header": {}
            }
        },
        "sort": [
            "_score",
            {"chunk_metadata.importance_score": {"order": "desc"}}
        ]
    }
    
    return os_client.search(index=INDEX_NAME, body=body)

def search_similar_hybrid(os_client, query_vector, medical_vector=None, sparse_vector=None, top_k=5, hybrid_weight=0.7):
    """Hybrid search combining dense and sparse vectors"""
    queries = []
    
    # Dense semantic search
    queries.append({
        "knn": {
            "embedding": {
                "vector": query_vector,
                "k": top_k
            }
        }
    })
    
    # Medical-specific embedding search
    if medical_vector:
        queries.append({
            "knn": {
                "medical_embedding": {
                    "vector": medical_vector,
                    "k": top_k
                }
            }
        })
    
    # Sparse vector search for exact medical term matching
    if sparse_vector:
        sparse_conditions = []
        for field, weight in sparse_vector.items():
            if weight > 0:
                sparse_conditions.append({
                    "range": {
                        f"sparse_vector.{field}": {"gte": weight * 0.5}
                    }
                })
        
        if sparse_conditions:
            queries.append({
                "bool": {
                    "should": sparse_conditions,
                    "minimum_should_match": 1
                }
            })
    
    # Combine queries
    if len(queries) == 1:
        body = {
            "size": top_k,
            "query": queries[0]
        }
    else:
        body = {
            "size": top_k,
            "query": {
                "bool": {
                    "should": queries,
                    "minimum_should_match": 1
                }
            }
        }
    
    return os_client.search(index=INDEX_NAME, body=body)

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
