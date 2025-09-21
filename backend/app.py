from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3, uuid, json, io, unicodedata, urllib.parse
from datetime import datetime
from dotenv import load_dotenv

# PDF Extraction modules
import fitz  # PyMuPDF for text + images
import pdfplumber  # For tables
import pytesseract
from PIL import Image
from sentence_transformers import SentenceTransformer

from services.opensearch_service import get_os_client, create_index, index_chunk, search_similar
from services.bedrock_service import generate_answer

# from services.chat import ChatService
# from services.pdf_processor import PDFProcessor
# from services.embedding_service import EmbeddingService
# from services.opensearch_service import OpenSearchService

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# AWS Configuration
AWS_REGION = "ap-southeast-1"
S3_BUCKET = "echomind-pdf-storage-sg"

# ---- Local Embedding Model (no SageMaker/Bedrock) ----
_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # 384-dim
_embedder = None

s3 = boto3.client("s3", region_name=AWS_REGION)

# ---- OpenSearch client ----
os_client = None

def init_opensearch():
    global os_client
    try:
        os_client = get_os_client()
        create_index(os_client)
        print("✅ OpenSearch ready")
    except Exception as e:
        print(f"⚠️ Failed to initialize OpenSearch: {e}")

# Initialize immediately when the app starts
init_opensearch()

# ===== Utils =====
# Return ASCII-safe string for S3 metadata.
def to_ascii(s: str) -> str:
    if not isinstance(s, str):
        s = str(s)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")

# Sanitize filename for S3 object key.
def make_safe_s3_key(original_filename: str, prefix: str) -> str:
    # Normalize, replace spaces and remove parens
    safe = unicodedata.normalize("NFKC", original_filename).replace(" ", "_").replace("(", "").replace(")", "")
    # Replace anything not alnum or allowed punctuation
    safe = "".join(ch if ch.isalnum() or ch in "._-+" else "_" for ch in safe)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    doc_id = str(uuid.uuid4())[:8]
    return f"{prefix}/{ts}_{doc_id}_{safe}", f"{ts}_{doc_id}"

# PDF Extraction
def extract_pdf_content(pdf_bytes: bytes, ocr_language="eng"):
    """Extract structured content (text, tables, images) from a PDF."""
    structured = {"pages": [], "full_text": ""}

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        seen_xrefs = set()
        for page_num, page in enumerate(doc, start=1):
            page_data = {"page": page_num, "text": "", "tables": [], "images": []}

            # Text extraction
            text = page.get_text("text")
            if text.strip():
                page_data["text"] = text.strip()
                structured["full_text"] += text + "\n"
            else:
                # OCR fallback if page is image-only
                pix = page.get_pixmap(dpi=300)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr_text = pytesseract.image_to_string(img, lang=ocr_language)
                page_data["text"] = ocr_text.strip()
                structured["full_text"] += ocr_text + "\n"

            # Images
            for img in page.get_images(full=True):
                try:
                    xref, smask, width, height, bpc, colorspace, alt, name, filter_ = img
                except ValueError:
                    # Sometimes PyMuPDF returns fewer values depending on version
                    continue

                if smask != 0 or width * height < 50 * 50 or xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                base_image = doc.extract_image(xref)
                page_data["images"].append({
                    "width": width,
                    "height": height,
                    "ext": base_image.get("ext"),
                    "size": len(base_image.get("image", b"")),
                })

            structured["pages"].append(page_data)

    # Tables with pdfplumber (per page)
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            try:
                tables = page.extract_tables()
                if tables:
                    structured["pages"][page_num - 1]["tables"] = tables
            except Exception:
                continue

    return structured

# === Chunking & Embedding helpers ===

def get_local_embedder():
    global _embedder
    if _embedder is None:
        print(f"🔧 Loading local embedding model: {_EMBED_MODEL_NAME}")
        # device="cpu" is safe; if you have GPU, set device="cuda"
        _embedder = SentenceTransformer(_EMBED_MODEL_NAME, device="cpu")
    return _embedder

def _flatten_table_to_text(table):
    """Convert a pdfplumber table (list of rows) into a simple text string."""
    lines = []
    for row in table:
        cells = [str(c).strip() for c in row if c]
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines).strip()

def build_chunks_from_structured(structured, max_chars=1200, overlap=150):
    chunks = []
    for page in structured.get("pages", []):
        text_parts = []

        if page.get("text"):
            text_parts.append(page["text"])

        for tbl in page.get("tables", []):
            tbl_txt = _flatten_table_to_text(tbl)
            if tbl_txt:
                text_parts.append("[TABLE]\n" + tbl_txt)

        page_text = "\n\n".join(text_parts).strip()
        if not page_text:
            continue

        i = 0
        while i < len(page_text):
            chunk_text = page_text[i:i+max_chars]
            if i + max_chars < len(page_text):
                last_space = chunk_text.rfind(" ")
                if last_space > max_chars * 0.6:
                    chunk_text = chunk_text[:last_space]
            start = i
            end = i + len(chunk_text)
            chunks.append({
                "page": page["page"],
                "text": chunk_text,
                "start": start,
                "end": end
            })
            if end >= len(page_text):
                break
            i = max(0, end - overlap)
    return chunks


def embed_chunks_local(chunks, batch_size=64):
    """
    Embed chunks locally using SentenceTransformers.
    Attaches fields: embedding (list[float]), embedding_dim (int)
    """
    if not chunks:
        return chunks

    model = get_local_embedder()
    texts = [c["text"] for c in chunks]

    # Batch encode for speed & memory
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        vecs = model.encode(batch, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        embeddings.extend(vecs)

    # attach
    for c, v in zip(chunks, embeddings):
        c["embedding"] = v.tolist()
        c["embedding_dim"] = len(v)

    return chunks

# ===== Routes =====
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"})

@app.route('/api/categories', methods=['GET'])
def get_categories():
    categories = [
        'patient_records',
        'clinical_guidelines', 
        'research_papers',
        'lab_results',
        'medication_schedules'
    ]
    return jsonify({"categories": categories})

@app.route('/api/documents', methods=['GET'])
def list_documents():
    try:
        response = s3.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix='medical_documents/'
        )
        
        documents = []
        if 'Contents' in response:
            for obj in response['Contents']:
                # Get object metadata
                head_response = s3.head_object(Bucket=S3_BUCKET, Key=obj['Key'])
                metadata = head_response.get('Metadata', {})
                
                # Extract filename from S3 key
                filename = obj['Key'].split('/')[-1]
                
                doc = {
                    'id': obj['Key'],
                    'filename': metadata.get('original_filename', filename),
                    'size': obj['Size'],
                    'upload_date': obj['LastModified'].isoformat(),
                    'categories': metadata.get('categories', '').split(',') if metadata.get('categories') else [],
                    's3_key': obj['Key']
                }
                documents.append(doc)
        
        # Sort by upload date (newest first)
        documents.sort(key=lambda x: x['upload_date'], reverse=True)
        
        return jsonify({
            'documents': documents,
            'total': len(documents)
        })
        
    except Exception as e:
        print(f"❌ Error listing documents: {str(e)}")
        return jsonify({"error": f"Failed to list documents: {str(e)}"}), 500

@app.route('/api/documents/upload', methods=['POST'])
def upload_document():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        categories = request.form.getlist('categories')
        pdf_bytes = file.read()

        # Validate PDF
        if not pdf_bytes.startswith(b'%PDF'):
            return jsonify({"error": "File is not a PDF"}), 400

        # Build a safe S3 key & IDs
        s3_key, short_id = make_safe_s3_key(file.filename, prefix="medical_documents")
        document_id = short_id
        print(f"☁️  S3 Key: {s3_key}")

        # ASCII-only metadata (S3 requirement)
        ascii_original_filename = to_ascii(file.filename)
        ascii_categories = ",".join(to_ascii(c) for c in categories)

        # Preserve the real filename for downloads via Content-Disposition
        content_disposition = f"attachment; filename*=UTF-8''{urllib.parse.quote(file.filename)}"

        # Upload PDF to S3
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
            ContentDisposition=content_disposition,
            Metadata={
                "categories": ascii_categories,
                "upload_date": datetime.now().isoformat(),
                "original_filename": ascii_original_filename,
                "file_size": str(len(pdf_bytes)),
                "document_type": "medical_pdf",
            }
        )
        print("✅ S3 upload successful")

        # 1) Extract PDF content
        extracted = extract_pdf_content(pdf_bytes, ocr_language="eng")

        # 2) Build chunks
        chunks = build_chunks_from_structured(extracted)
        print(f"✂️ Created {len(chunks)} chunks")

        # 3) Local embeddings (no AWS endpoints)
        chunks = embed_chunks_local(chunks, batch_size=64)
        print(f"🧠 Local embeddings added, dim={chunks[0]['embedding_dim'] if chunks else 0}")

        # 4) Index into OpenSearch
        if os_client:
            for chunk in chunks:
                index_chunk(os_client, document_id, s3_key, categories, chunk)

        # Preview only (don’t return full vectors for all chunks)
        return jsonify({
            "success": True,
            "document_id": document_id,
            "message": "Document uploaded, chunked, and embedded locally",
            "s3_key": s3_key,
            "filename": file.filename,
            "size": len(pdf_bytes),
            "categories": categories,
            "upload_date": datetime.now().isoformat(),
            "extracted": {
                "pages": len(extracted.get("pages", [])),
                "full_text_len": len(extracted.get("full_text", "")),
            },
            "chunks": {
                "count": len(chunks),
                "embedding_dim": chunks[0]["embedding_dim"] if chunks else 0,
                "samples": [
                    {
                        "page": c["page"],
                        "text_preview": c["text"][:200],
                        "embedding_sample": c.get("embedding", [])[:8]
                    }
                    for c in chunks[:3]
                ]
            }
        })

    except Exception as e:
        print(f"❌ Upload error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": f"Upload failed: {e}"}), 500

@app.route('/api/query', methods=['POST'])
def query_documents():
    try:
        data = request.get_json()
        query_text = data.get("query")
        top_k = int(data.get("top_k", 5))

        if not query_text:
            return jsonify({"error": "Missing query"}), 400

        # Embed query
        model = get_local_embedder()
        query_vector = model.encode([query_text], normalize_embeddings=True)[0].tolist()

        # Search in OpenSearch
        resp = search_similar(os_client, query_vector, top_k=top_k)

        hits = []
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            hits.append({
                "score": hit["_score"],
                "doc_id": src.get("doc_id"),
                "page": src.get("page"),
                "text": src.get("text")[:300] + "...",
                "categories": src.get("categories"),
                "s3_key": src.get("s3_key"),
            })

        return jsonify({"results": hits})

    except Exception as e:
        print(f"❌ Query error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": f"Query failed: {e}"}), 500
    
@app.route('/api/answer', methods=['POST'])
def answer_with_bedrock():
    """
    Manual RAG endpoint:
    1) embed user query locally
    2) retrieve top-k chunks from OpenSearch
    3) build context snippets + pass to Nova Pro (Bedrock) for grounded answer
    """
    try:
        data = request.get_json() or {}
        question = data.get("query", "").strip()
        top_k = int(data.get("top_k", 5))

        if not question:
            return jsonify({"error": "Missing query"}), 400
        if os_client is None:
            return jsonify({"error": "OpenSearch client not initialized"}), 500

        # 1) Embed query
        model = get_local_embedder()
        qvec = model.encode([question], normalize_embeddings=True)[0].tolist()

        # 2) Retrieve from OpenSearch
        resp = search_similar(os_client, qvec, top_k=top_k)

        # 3) Build snippets + citation mapping
        snippets, citations = [], []  # snippets[i] <-> citations[i]
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            text = (src.get("text") or "").strip()
            if not text:
                continue
            # keep each snippet compact; Nova Pro handles longer context well but we stay safe
            snippets.append(text[:1200])
            citations.append({
                "doc_id": src.get("doc_id"),
                "page": src.get("page"),
                "s3_key": src.get("s3_key"),
                "categories": src.get("categories", [])
            })
            if len(snippets) >= top_k:
                break

        if not snippets:
            return jsonify({"answer": "Insufficient evidence in the provided documents.", "citations": []})

        # 4) Call Bedrock Nova Pro (on-demand)
        answer = generate_answer(question, snippets, temperature=0.2, max_tokens=600)

        # 5) Optional: attach presigned S3 links
        def presign(key):
            try:
                return s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": S3_BUCKET, "Key": key},
                    ExpiresIn=3600
                )
            except Exception:
                return None

        for i, c in enumerate(citations, start=1):
            c["label"] = f"[{i}]"
            c["url"] = presign(c["s3_key"]) if c.get("s3_key") else None

        return jsonify({
            "answer": answer,
            "citations": citations  # your UI can map [1],[2] to these
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": f"Bedrock RAG failed: {e}"}), 500

@app.route('/api/chat/query', methods=['POST'])
def chat_query_compat():
    """
    Wrapper to keep the React app unchanged.
    It performs: embed -> retrieve (OpenSearch) -> Nova Pro generate,
    then maps to { response: { answer, sources, confidence, followUpQuestions } }.
    """
    try:
        data = request.get_json() or {}
        query = (data.get('query') or '').strip()
        session_id = data.get('sessionId')  # optional; not used here
        history = data.get('history', [])   # optional; not used here
        top_k = int(data.get('top_k', 5))

        if not query:
            return jsonify({"error": "Query is required"}), 400
        if os_client is None:
            return jsonify({"error": "Search not ready"}), 503

        # 1) Embed query
        model = get_local_embedder()
        qvec = model.encode([query], normalize_embeddings=True)[0].tolist()

        # 2) Retrieve from OpenSearch
        resp = search_similar(os_client, qvec, top_k=top_k)

        # 3) Prepare snippets + build sources list for UI
        snippets = []
        ui_sources = []

        def presign(key):
            try:
                return s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": S3_BUCKET, "Key": key},
                    ExpiresIn=3600
                )
            except Exception:
                return None

        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            text = (src.get("text") or "").strip()
            if not text:
                continue
            # Keep snippet length manageable
            snippets.append(text[:1200])

            # Try to get original filename from S3 metadata (fallback to key basename)
            s3_key = src.get("s3_key")
            filename = s3_key.rsplit("/", 1)[-1] if s3_key else "document.pdf"
            try:
                if s3_key:
                    head = s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
                    filename = head.get("Metadata", {}).get("original_filename", filename)
            except Exception:
                pass

            ui_sources.append({
                "documentId": src.get("doc_id"),
                "filename": filename,
                "relevanceScore": float(hit.get("_score", 0.0)),
                "excerpt": (text[:300] + "..."),
                # Optionally expose a link your MessageBubble could render later:
                # "url": presign(s3_key)
            })

            if len(snippets) >= top_k:
                break

        if not snippets:
            return jsonify({
                "response": {
                    "answer": "Insufficient evidence in the provided documents.",
                    "sources": [],
                    "confidence": 0.0,
                    "followUpQuestions": []
                }
            })

        # 4) Generate answer with Bedrock (Nova Pro) using manual RAG
        from services.bedrock_service import generate_answer
        answer = generate_answer(query, snippets, temperature=0.2, max_tokens=600)

        # 5) Heuristic confidence (optional): normalize top score into 0..1
        conf = 0.0
        if ui_sources:
            max_score = max(s["relevanceScore"] for s in ui_sources)
            # simple squash; tune as you like
            conf = max(0.0, min(1.0, max_score / 10.0))

        # 6) Some dynamic follow-ups (optional)
        followups = []
        if "contraindication" in query.lower():
            followups = ["What are the dosage adjustments?", "List monitoring parameters."]
        elif "dosage" in query.lower():
            followups = ["Any renal/hepatic adjustments?", "What are common adverse effects?"]

        return jsonify({
            "response": {
                "answer": answer,
                "sources": ui_sources,
                "confidence": conf,
                "followUpQuestions": followups
            }
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": f"Chat processing failed: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)