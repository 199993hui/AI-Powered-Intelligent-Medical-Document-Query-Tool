from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3, uuid, json, io, unicodedata, urllib.parse
from datetime import datetime
from dotenv import load_dotenv
import threading
from functools import lru_cache
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


# PDF Extraction modules
import fitz  # PyMuPDF for text + images
try:
    import pdfplumber  # For tables
except ImportError:
    print("⚠️ pdfplumber not installed, table extraction disabled")
    pdfplumber = None
import pytesseract
from PIL import Image
from sentence_transformers import SentenceTransformer
import nltk
import re
from typing import List, Dict, Tuple
from enum import Enum
from collections import Counter

class ContentType(Enum):
    HEADER = "header"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    PROCEDURE = "procedure"
    MEDICATION = "medication"
    DIAGNOSIS = "diagnosis"

from services.opensearch_service import get_os_client, create_index, index_chunk, search_similar, INDEX_NAME
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

# ---- Optimized Embedding Models with Caching ----
_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # 384-dim
_embedder = None
_embedding_cache = {}  # Simple in-memory cache
_cache_lock = threading.Lock()

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

# NLTK initialization function
def _ensure_nltk_data():
    """Ensure NLTK punkt tokenizer is downloaded"""
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        print("📥 Downloading NLTK punkt tokenizer...")
        nltk.download('punkt', quiet=True)

# Initialize immediately when the app starts
init_opensearch()

# Initialize NLTK data
try:
    _ensure_nltk_data()
except Exception as e:
    print(f"⚠️ NLTK initialization warning: {e}")

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
    if pdfplumber:
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    try:
                        tables = page.extract_tables()
                        if tables:
                            structured["pages"][page_num - 1]["tables"] = tables
                    except Exception:
                        continue
        except Exception as e:
            print(f"⚠️ Table extraction failed: {e}")

    return structured

# === Chunking & Embedding helpers ===

# Lightweight medical embeddings
_medical_embedder = None
_MEDICAL_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # Keep 384-dim for compatibility

@lru_cache(maxsize=1)
def get_local_embedder():
    print(f"🔧 Loading local embedding model: {_EMBED_MODEL_NAME}")
    return SentenceTransformer(_EMBED_MODEL_NAME, device="cpu")

def get_cached_embedding(text: str, model_type="general"):
    """Get embedding with caching for O(1) repeated queries"""
    cache_key = f"{model_type}:{hash(text)}"
    
    with _cache_lock:
        if cache_key in _embedding_cache:
            return _embedding_cache[cache_key]
    
    # Generate embedding
    model = get_local_embedder() if model_type == "general" else get_medical_embedder()
    embedding = model.encode([text], normalize_embeddings=True)[0].tolist()
    
    # Cache with size limit
    with _cache_lock:
        if len(_embedding_cache) > 1000:  # Limit cache size
            _embedding_cache.clear()
        _embedding_cache[cache_key] = embedding
    
    return embedding

@lru_cache(maxsize=1)
def get_medical_embedder():
    print(f"🔧 Loading medical model: {_MEDICAL_MODEL_NAME}")
    return SentenceTransformer(_MEDICAL_MODEL_NAME, device="cpu")

@lru_cache(maxsize=200)
def enhance_query(query: str) -> str:
    """Cached query enhancement for O(1) repeated queries"""
    enhanced = query.lower().strip()
    
    # Pre-compiled patterns for faster matching
    if not hasattr(enhance_query, 'patterns'):
        enhance_query.patterns = {
            'heart attack': 'heart attack myocardial infarction MI',
            'high blood pressure': 'high blood pressure hypertension',
            'diabetes': 'diabetes mellitus DM blood sugar',
            'medication': 'medication drug medicine prescription',
            'dosage': 'dosage dose amount mg ml'
        }
    
    # Fast string replacement
    for term, expansion in enhance_query.patterns.items():
        if term in enhanced:
            enhanced = enhanced.replace(term, expansion)
    
    return enhanced

def embed_chunks_optimized(chunks, batch_size=64):
    """Optimized embeddings with parallel processing"""
    if not chunks:
        return chunks

    model = get_medical_embedder()
    print(f"🧠 Generating optimized embeddings for {len(chunks)} chunks...")
    
    # Pre-process texts once - O(n) instead of O(n*m)
    texts = []
    for chunk in chunks:
        text = chunk["text"]
        # Minimal enhancement for speed
        if len(text) > 500:  # Only enhance longer texts
            text = enhance_text_for_embedding(text)
        texts.append(text)
    
    # Larger batch size for better GPU/CPU utilization
    embeddings = []
    start_time = time.time()
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        vecs = model.encode(
            batch, 
            normalize_embeddings=True, 
            convert_to_numpy=True, 
            show_progress_bar=False,
            batch_size=min(len(batch), 32)  # Optimal batch size for model
        )
        embeddings.extend(vecs)
    
    # Vectorized assignment - faster than loop
    for i, chunk in enumerate(chunks):
        chunk["embedding"] = embeddings[i].tolist()
        chunk["embedding_dim"] = len(embeddings[i])
    
    elapsed = time.time() - start_time
    print(f"✅ Embeddings complete: {len(embeddings)} vectors in {elapsed:.2f}s")
    return chunks

@lru_cache(maxsize=500)
def enhance_text_for_embedding(text: str) -> str:
    """Cached text enhancement for O(1) repeated enhancements"""
    # Compile regex patterns once for better performance
    if not hasattr(enhance_text_for_embedding, 'dosage_pattern'):
        enhance_text_for_embedding.dosage_pattern = re.compile(r'(\d+\s*(?:mg|ml|mcg))', re.IGNORECASE)
        enhance_text_for_embedding.condition_pattern = re.compile(r'\b(diabetes|hypertension|pneumonia|asthma)\b', re.IGNORECASE)
    
    # Fast pattern matching
    enhanced = enhance_text_for_embedding.dosage_pattern.sub(r'[DOSAGE] \1', text)
    enhanced = enhance_text_for_embedding.condition_pattern.sub(r'[CONDITION] \1', enhanced)
    
    return enhanced

def _create_sparse_vector(text: str, medical_entities: List[str]) -> Dict[str, float]:
    """Create sparse vector for keyword-based matching"""
    text_lower = text.lower()
    sparse_vector = {
        "medical_terms": 0.0,
        "drug_names": 0.0,
        "procedures": 0.0,
        "conditions": 0.0,
        "dosages": 0.0
    }
    
    # Medical terms weight
    medical_keywords = ['treatment', 'therapy', 'medication', 'diagnosis', 'symptom', 'condition']
    medical_count = sum(1 for keyword in medical_keywords if keyword in text_lower)
    sparse_vector["medical_terms"] = min(medical_count / 10.0, 1.0)
    
    # Drug names weight
    drug_patterns = ['mg', 'ml', 'tablet', 'capsule', 'injection', 'dose']
    drug_count = sum(1 for pattern in drug_patterns if pattern in text_lower)
    sparse_vector["drug_names"] = min(drug_count / 5.0, 1.0)
    
    # Procedures weight
    procedure_keywords = ['surgery', 'operation', 'procedure', 'intervention', 'treatment']
    procedure_count = sum(1 for keyword in procedure_keywords if keyword in text_lower)
    sparse_vector["procedures"] = min(procedure_count / 3.0, 1.0)
    
    # Conditions weight
    condition_keywords = ['disease', 'disorder', 'syndrome', 'condition', 'diagnosis']
    condition_count = sum(1 for keyword in condition_keywords if keyword in text_lower)
    sparse_vector["conditions"] = min(condition_count / 3.0, 1.0)
    
    # Dosages weight
    dosage_count = len([entity for entity in medical_entities if any(unit in entity for unit in ['mg', 'ml', 'mcg'])])
    sparse_vector["dosages"] = min(dosage_count / 3.0, 1.0)
    
    return sparse_vector

def _enhance_medical_text(text: str) -> str:
    """Enhance text for medical-specific embedding"""
    # Add medical context markers
    enhanced_text = text
    
    # Mark medical entities
    medical_markers = {
        r'\b\d+\s*mg\b': '[DOSAGE]',
        r'\b\d+\s*ml\b': '[VOLUME]',
        r'\b(?:diabetes|hypertension|asthma)\b': '[CONDITION]',
        r'\b(?:surgery|procedure|operation)\b': '[PROCEDURE]'
    }
    
    for pattern, marker in medical_markers.items():
        enhanced_text = re.sub(pattern, f'{marker} \\g<0>', enhanced_text, flags=re.IGNORECASE)
    
    return enhanced_text

def _flatten_table_to_text(table):
    """Convert a pdfplumber table (list of rows) into a simple text string."""
    lines = []
    for row in table:
        cells = [str(c).strip() for c in row if c]
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines).strip()

# Enhanced chunking utilities
def _detect_content_type(text: str) -> ContentType:
    """Detect the type of content in a text block"""
    text_lower = text.lower().strip()
    
    # Header patterns
    if re.match(r'^[A-Z][A-Z\s]{3,}:?$', text.strip()) or \
       re.match(r'^\d+\.\s+[A-Z]', text.strip()) or \
       len(text.strip()) < 100 and text.strip().isupper():
        return ContentType.HEADER
    
    # List patterns
    if re.match(r'^\s*[•\-\*]\s+', text) or \
       re.match(r'^\s*\d+[.)\s]', text) or \
       re.match(r'^\s*[a-z][.)\s]', text):
        return ContentType.LIST
    
    # Medical content patterns
    medication_keywords = ['dosage', 'mg', 'ml', 'tablet', 'capsule', 'medication', 'drug', 'prescription']
    procedure_keywords = ['procedure', 'surgery', 'operation', 'treatment', 'therapy', 'intervention']
    diagnosis_keywords = ['diagnosis', 'condition', 'disease', 'syndrome', 'disorder', 'symptoms']
    
    if any(keyword in text_lower for keyword in medication_keywords):
        return ContentType.MEDICATION
    elif any(keyword in text_lower for keyword in procedure_keywords):
        return ContentType.PROCEDURE
    elif any(keyword in text_lower for keyword in diagnosis_keywords):
        return ContentType.DIAGNOSIS
    
    return ContentType.PARAGRAPH

def _detect_section_headers(text: str) -> List[Tuple[int, str]]:
    """Detect section headers and their positions in text"""
    headers = []
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
        # Header patterns
        if (re.match(r'^[A-Z][A-Z\s]{3,}:?$', line_stripped) or  # ALL CAPS
            re.match(r'^\d+\.\s+[A-Z]', line_stripped) or        # Numbered sections
            (len(line_stripped) < 80 and                         # Short lines
             line_stripped.count(' ') < 8 and                   # Few words
             line_stripped[0].isupper())):
            
            # Calculate character position
            char_pos = sum(len(lines[j]) + 1 for j in range(i))
            headers.append((char_pos, line_stripped))
    
    return headers

def _extract_medical_entities_nested(text: str) -> List[Dict[str, any]]:
    """Extract medical entities as nested objects with metadata"""
    entities = []
    text_lower = text.lower()
    
    # Drug patterns with confidence scoring
    drug_patterns = [
        (r'\b[A-Z][a-z]+(?:in|ol|ide|ine|ate|ium)\b', 'drug', 0.8),
        (r'\b(?:acetaminophen|ibuprofen|aspirin|metformin|insulin|warfarin|lisinopril)\b', 'drug', 0.9)
    ]
    
    # Dosage patterns
    dosage_patterns = [
        (r'\d+\s*(?:mg|ml|mcg|g|units?)\b', 'dosage', 0.9),
        (r'\d+\.\d+\s*(?:mg|ml|mcg|g)\b', 'dosage', 0.9)
    ]
    
    # Condition patterns
    condition_patterns = [
        (r'\b(?:diabetes|hypertension|pneumonia|asthma|copd|covid|influenza)\b', 'condition', 0.9),
        (r'\b(?:heart failure|kidney disease|liver disease)\b', 'condition', 0.8)
    ]
    
    all_patterns = drug_patterns + dosage_patterns + condition_patterns
    
    for pattern, entity_type, confidence in all_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            entities.append({
                'entity': match.group().lower(),
                'type': entity_type,
                'confidence': confidence
            })
    
    return entities

def _extract_medical_entities(text: str) -> List[str]:
    """Extract medical entities from text"""
    entities = []
    text_lower = text.lower()
    
    # Drug name patterns
    drug_patterns = [
        r'\b[A-Z][a-z]+(?:in|ol|ide|ine|ate|ium)\b',  # Common drug suffixes
        r'\b(?:acetaminophen|ibuprofen|aspirin|metformin|insulin|warfarin|lisinopril)\b'
    ]
    
    # Dosage patterns
    dosage_patterns = [
        r'\d+\s*(?:mg|ml|mcg|g|units?)\b',
        r'\d+\.\d+\s*(?:mg|ml|mcg|g)\b'
    ]
    
    # Medical condition patterns
    condition_patterns = [
        r'\b(?:diabetes|hypertension|pneumonia|asthma|copd|covid|influenza)\b',
        r'\b(?:heart failure|kidney disease|liver disease)\b'
    ]
    
    all_patterns = drug_patterns + dosage_patterns + condition_patterns
    
    for pattern in all_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        entities.extend([match.lower() for match in matches])
    
    return list(set(entities))  # Remove duplicates

def _calculate_importance_score(text: str, content_type: ContentType) -> float:
    """Calculate importance score based on content characteristics"""
    score = 0.5  # Base score
    text_lower = text.lower()
    
    # Content type weights
    type_weights = {
        ContentType.HEADER: 0.9,
        ContentType.MEDICATION: 0.8,
        ContentType.DIAGNOSIS: 0.8,
        ContentType.PROCEDURE: 0.7,
        ContentType.LIST: 0.6,
        ContentType.TABLE: 0.7,
        ContentType.PARAGRAPH: 0.5
    }
    
    score = type_weights.get(content_type, 0.5)
    
    # Boost for medical keywords
    medical_keywords = ['treatment', 'diagnosis', 'medication', 'dosage', 'procedure', 'symptoms']
    keyword_count = sum(1 for keyword in medical_keywords if keyword in text_lower)
    score += min(keyword_count * 0.1, 0.3)
    
    # Boost for specific medical terms
    if any(term in text_lower for term in ['contraindication', 'adverse', 'warning', 'caution']):
        score += 0.2
    
    return min(score, 1.0)

def _detect_medical_specialty(text: str) -> str:
    """Detect medical specialty from document content"""
    text_lower = text.lower()
    
    specialties = {
        'cardiology': ['heart', 'cardiac', 'cardiovascular', 'ecg', 'ekg', 'coronary'],
        'endocrinology': ['diabetes', 'insulin', 'glucose', 'thyroid', 'hormone'],
        'pulmonology': ['lung', 'respiratory', 'asthma', 'copd', 'pneumonia'],
        'nephrology': ['kidney', 'renal', 'dialysis', 'creatinine', 'urea'],
        'gastroenterology': ['stomach', 'intestinal', 'liver', 'hepatic', 'gastric'],
        'neurology': ['brain', 'neurological', 'seizure', 'stroke', 'migraine'],
        'oncology': ['cancer', 'tumor', 'chemotherapy', 'radiation', 'malignant']
    }
    
    specialty_scores = {}
    for specialty, keywords in specialties.items():
        score = sum(1 for keyword in keywords if keyword in text_lower)
        if score > 0:
            specialty_scores[specialty] = score
    
    if specialty_scores:
        return max(specialty_scores, key=specialty_scores.get)
    return 'general'

def _categorize_hierarchically(categories: List[str], text: str) -> Dict[str, str]:
    """Create hierarchical category structure"""
    hierarchy = {
        'primary_category': categories[0] if categories else 'general',
        'subcategory': '',
        'medical_domain': _detect_medical_specialty(text),
        'urgency_level': 'routine'
    }
    
    # Detect urgency
    text_lower = text.lower()
    urgent_keywords = ['emergency', 'urgent', 'critical', 'immediate', 'stat', 'acute']
    if any(keyword in text_lower for keyword in urgent_keywords):
        hierarchy['urgency_level'] = 'urgent'
    elif any(keyword in text_lower for keyword in ['chronic', 'maintenance', 'routine']):
        hierarchy['urgency_level'] = 'routine'
    
    # Subcategories based on primary category
    subcategory_map = {
        'patient_records': ['admission', 'discharge', 'progress_notes', 'consultation'],
        'clinical_guidelines': ['treatment_protocol', 'diagnostic_criteria', 'best_practices'],
        'research_papers': ['clinical_trial', 'case_study', 'systematic_review'],
        'lab_results': ['blood_work', 'imaging', 'pathology', 'microbiology'],
        'medication_schedules': ['prescription', 'administration', 'monitoring']
    }
    
    primary = hierarchy['primary_category']
    if primary in subcategory_map:
        for sub in subcategory_map[primary]:
            if sub.replace('_', ' ') in text_lower:
                hierarchy['subcategory'] = sub
                break
    
    return hierarchy

def _calculate_boost_factors(chunk: Dict, content_type: ContentType, importance_score: float) -> Dict[str, float]:
    """Calculate boost factors for advanced search scoring"""
    boost_factors = {
        'content_boost': 1.0,
        'recency_boost': 1.0,
        'importance_boost': importance_score
    }
    
    # Content type boosting
    content_boosts = {
        ContentType.HEADER: 1.5,
        ContentType.MEDICATION: 1.4,
        ContentType.DIAGNOSIS: 1.3,
        ContentType.PROCEDURE: 1.2,
        ContentType.LIST: 1.1,
        ContentType.TABLE: 1.2
    }
    boost_factors['content_boost'] = content_boosts.get(content_type, 1.0)
    
    return boost_factors

def _extract_search_keywords(text: str, medical_entities: List[Dict]) -> str:
    """Extract important keywords for boosted searching"""
    keywords = []
    
    # Add high-confidence medical entities
    for entity in medical_entities:
        if entity.get('confidence', 0) > 0.8:
            keywords.append(entity['entity'])
    
    # Add important medical terms
    important_terms = [
        'contraindication', 'adverse', 'warning', 'caution', 'emergency',
        'dosage', 'administration', 'monitoring', 'treatment', 'diagnosis'
    ]
    
    text_lower = text.lower()
    for term in important_terms:
        if term in text_lower:
            keywords.append(term)
    
    return ' '.join(set(keywords))

def _calculate_readability_score(text: str) -> float:
    """Simple readability score based on sentence and word complexity"""
    sentences = nltk.sent_tokenize(text)
    words = text.split()
    
    if not sentences or not words:
        return 0.5
    
    avg_sentence_length = len(words) / len(sentences)
    avg_word_length = sum(len(word) for word in words) / len(words)
    
    # Simple scoring (lower is more readable)
    score = 1.0 - min((avg_sentence_length / 20 + avg_word_length / 10) / 2, 0.8)
    return max(score, 0.1)

def _preserve_list_structure(text: str) -> str:
    """Preserve list formatting and structure"""
    lines = text.split('\n')
    processed_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            processed_lines.append(line)
            continue
            
        # Enhance list markers
        if re.match(r'^\s*[•\-\*]\s+', line):
            processed_lines.append(f"• {stripped[2:].strip()}")
        elif re.match(r'^\s*\d+[.)\s]', line):
            match = re.match(r'^\s*(\d+)[.)\s]+(.*)$', line)
            if match:
                num, content = match.groups()
                processed_lines.append(f"{num}. {content.strip()}")
            else:
                processed_lines.append(line)
        elif re.match(r'^\s*[a-z][.)\s]', line):
            match = re.match(r'^\s*([a-z])[.)\s]+(.*)$', line)
            if match:
                letter, content = match.groups()
                processed_lines.append(f"{letter}) {content.strip()}")
            else:
                processed_lines.append(line)
        else:
            processed_lines.append(line)
    
    return '\n'.join(processed_lines)

def _is_medical_term_boundary(text: str, pos: int) -> bool:
    """Check if position is safe to split (not breaking medical terms)"""
    if pos >= len(text) or pos <= 0:
        return True
    
    # Medical patterns that shouldn't be split
    medical_patterns = [
        r'\d+\s*mg\b',  # dosages
        r'\d+\s*ml\b',  # volumes  
        r'\d+\s*mcg\b', # micrograms
        r'\b\d+\.\d+\b', # decimal numbers
        r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b'  # drug names like "Tylenol Extra"
    ]
    
    # Check 50 chars before and after split point
    window_start = max(0, pos - 50)
    window_end = min(len(text), pos + 50)
    window = text[window_start:window_end]
    
    for pattern in medical_patterns:
        matches = list(re.finditer(pattern, window, re.IGNORECASE))
        for match in matches:
            match_start = window_start + match.start()
            match_end = window_start + match.end()
            if match_start <= pos <= match_end:
                return False
    return True

def _find_best_split_point(text: str, target_pos: int, max_search: int = 200) -> int:
    """Find the best position to split text near target_pos"""
    if target_pos >= len(text):
        return len(text)
    
    # Try sentence boundaries first
    sentences = nltk.sent_tokenize(text[:target_pos + max_search])
    if len(sentences) > 1:
        # Find sentence end closest to target
        sentence_ends = []
        pos = 0
        for sent in sentences[:-1]:  # exclude last incomplete sentence
            pos += len(sent)
            # Account for spaces between sentences
            while pos < len(text) and text[pos] in ' \n\t':
                pos += 1
            sentence_ends.append(pos)
        
        # Find closest sentence end to target
        best_end = min(sentence_ends, key=lambda x: abs(x - target_pos))
        if abs(best_end - target_pos) <= max_search and _is_medical_term_boundary(text, best_end):
            return best_end
    
    # Fallback: find paragraph or line break
    for offset in range(0, max_search):
        for pos in [target_pos - offset, target_pos + offset]:
            if 0 <= pos < len(text):
                if text[pos] in '\n\r' and _is_medical_term_boundary(text, pos):
                    return pos
    
    # Last resort: word boundary
    for offset in range(0, max_search):
        for pos in [target_pos - offset, target_pos + offset]:
            if 0 <= pos < len(text):
                if text[pos] == ' ' and _is_medical_term_boundary(text, pos):
                    return pos
    
    return target_pos

def build_chunks_from_structured(structured, max_chars=1200, overlap=150):
    """Enhanced chunking with document structure awareness"""
    _ensure_nltk_data()
    chunks = []
    
    for page in structured.get("pages", []):
        text_parts = []
        section_info = []

        if page.get("text"):
            # Preserve list structure
            processed_text = _preserve_list_structure(page["text"])
            text_parts.append(processed_text)
            
            # Detect sections for better chunking
            headers = _detect_section_headers(processed_text)
            section_info.extend(headers)

        for tbl in page.get("tables", []):
            tbl_txt = _flatten_table_to_text(tbl)
            if tbl_txt:
                text_parts.append("[TABLE]\n" + tbl_txt)

        page_text = "\n\n".join(text_parts).strip()
        if not page_text:
            continue

        # Structure-aware chunking
        chunks.extend(_create_structure_aware_chunks(
            page_text, page["page"], section_info, max_chars, overlap
        ))
    
    print(f"✂️ Structure-aware chunking: {len(chunks)} chunks created")
    return chunks

def _create_structure_aware_chunks(page_text: str, page_num: int, 
                                 section_info: List[Tuple[int, str]], 
                                 max_chars: int, overlap: int) -> List[Dict]:
    """Create chunks that respect document structure"""
    chunks = []
    
    # If no sections detected, fall back to enhanced chunking
    if not section_info:
        return _create_enhanced_chunks(page_text, page_num, max_chars, overlap)
    
    # Create section-based chunks
    section_positions = [pos for pos, _ in section_info] + [len(page_text)]
    
    for i in range(len(section_positions) - 1):
        section_start = section_positions[i]
        section_end = section_positions[i + 1]
        section_text = page_text[section_start:section_end].strip()
        
        if not section_text:
            continue
            
        # Get section header if available
        section_header = section_info[i][1] if i < len(section_info) else ""
        
        # If section is small enough, keep as single chunk
        if len(section_text) <= max_chars:
            content_type = _detect_content_type(section_text)
            medical_entities_nested = _extract_medical_entities_nested(section_text)
            medical_entities = [e['entity'] for e in medical_entities_nested]
            importance_score = _calculate_importance_score(section_text, content_type)
            readability_score = _calculate_readability_score(section_text)
            boost_factors = _calculate_boost_factors({}, content_type, importance_score)
            search_keywords = _extract_search_keywords(section_text, medical_entities_nested)
            
            chunks.append({
                "page": page_num,
                "text": section_text,
                "start": section_start,
                "end": section_end,
                "chunk_type": "section",
                "section_header": section_header,
                "content_type": content_type.value,
                "chunk_metadata": {
                    "word_count": len(section_text.split()),
                    "sentence_count": len(nltk.sent_tokenize(section_text)),
                    "importance_score": importance_score,
                    "medical_entities": medical_entities_nested,
                    "contains_dosage": any('mg' in entity or 'ml' in entity for entity in medical_entities),
                    "contains_procedure": content_type == ContentType.PROCEDURE,
                    "contains_diagnosis": content_type == ContentType.DIAGNOSIS,
                    "readability_score": readability_score
                },
                "boost_factors": boost_factors,
                "search_keywords": search_keywords
            })
        else:
            # Split large sections while preserving context
            section_chunks = _split_large_section(
                section_text, section_start, page_num, 
                section_header, max_chars, overlap
            )
            chunks.extend(section_chunks)
    
    return chunks

def _create_enhanced_chunks(page_text: str, page_num: int, max_chars: int, overlap: int) -> List[Dict]:
    """Fallback to enhanced chunking when no structure detected"""
    chunks = []
    i = 0
    
    while i < len(page_text):
        target_end = i + max_chars
        if target_end >= len(page_text):
            chunk_text = page_text[i:]
            end_pos = len(page_text)
        else:
            end_pos = _find_best_split_point(page_text, target_end)
            chunk_text = page_text[i:end_pos].strip()
        
        if chunk_text:
            content_type = _detect_content_type(chunk_text)
            medical_entities_nested = _extract_medical_entities_nested(chunk_text)
            medical_entities = [e['entity'] for e in medical_entities_nested]  # Legacy format
            importance_score = _calculate_importance_score(chunk_text, content_type)
            readability_score = _calculate_readability_score(chunk_text)
            boost_factors = _calculate_boost_factors({}, content_type, importance_score)
            search_keywords = _extract_search_keywords(chunk_text, medical_entities_nested)
            
            chunks.append({
                "page": page_num,
                "text": chunk_text,
                "start": i,
                "end": end_pos,
                "chunk_type": "enhanced",
                "content_type": content_type.value,
                "chunk_metadata": {
                    "word_count": len(chunk_text.split()),
                    "sentence_count": len(nltk.sent_tokenize(chunk_text)),
                    "importance_score": importance_score,
                    "medical_entities": medical_entities_nested,
                    "contains_dosage": any('mg' in entity or 'ml' in entity for entity in medical_entities),
                    "contains_procedure": content_type == ContentType.PROCEDURE,
                    "contains_diagnosis": content_type == ContentType.DIAGNOSIS,
                    "readability_score": readability_score
                },
                "boost_factors": boost_factors,
                "search_keywords": search_keywords
            })
        
        if end_pos >= len(page_text):
            break
            
        next_start = max(i + 1, end_pos - overlap)
        if overlap > 0 and next_start < end_pos:
            next_start = _find_best_split_point(page_text, next_start, 50)
        
        i = next_start
    
    return chunks

def _split_large_section(section_text: str, section_start: int, page_num: int,
                        section_header: str, max_chars: int, overlap: int) -> List[Dict]:
    """Split large sections while maintaining context"""
    chunks = []
    i = 0
    
    while i < len(section_text):
        target_end = i + max_chars
        if target_end >= len(section_text):
            chunk_text = section_text[i:]
            end_pos = len(section_text)
        else:
            end_pos = _find_best_split_point(section_text, target_end)
            chunk_text = section_text[i:end_pos].strip()
        
        if chunk_text:
            # Add section context to chunk
            if section_header and i == 0:
                # First chunk includes header
                contextual_text = chunk_text
            elif section_header:
                # Subsequent chunks reference header
                contextual_text = f"[Section: {section_header}]\n{chunk_text}"
            else:
                contextual_text = chunk_text
                
            content_type = _detect_content_type(chunk_text)
            medical_entities_nested = _extract_medical_entities_nested(chunk_text)
            medical_entities = [e['entity'] for e in medical_entities_nested]
            importance_score = _calculate_importance_score(chunk_text, content_type)
            readability_score = _calculate_readability_score(chunk_text)
            boost_factors = _calculate_boost_factors({}, content_type, importance_score)
            search_keywords = _extract_search_keywords(chunk_text, medical_entities_nested)
            
            chunks.append({
                "page": page_num,
                "text": contextual_text,
                "start": section_start + i,
                "end": section_start + end_pos,
                "chunk_type": "section_part",
                "section_header": section_header,
                "content_type": content_type.value,
                "chunk_metadata": {
                    "word_count": len(chunk_text.split()),
                    "sentence_count": len(nltk.sent_tokenize(chunk_text)),
                    "importance_score": importance_score,
                    "medical_entities": medical_entities_nested,
                    "contains_dosage": any('mg' in entity or 'ml' in entity for entity in medical_entities),
                    "contains_procedure": content_type == ContentType.PROCEDURE,
                    "contains_diagnosis": content_type == ContentType.DIAGNOSIS,
                    "readability_score": readability_score
                },
                "boost_factors": boost_factors,
                "search_keywords": search_keywords
            })
        
        if end_pos >= len(section_text):
            break
            
        next_start = max(i + 1, end_pos - overlap)
        if overlap > 0 and next_start < end_pos:
            next_start = _find_best_split_point(section_text, next_start, 50)
        
        i = next_start
    
    return chunks

def build_smart_chunks(structured, max_chars=800, overlap=100):
    """Optimized chunking with O(n) complexity"""
    chunks = []
    
    for page in structured.get("pages", []):
        text_parts = []
        if page.get("text"):
            # Skip normalization for speed - do it during embedding
            text_parts.append(page["text"])
        
        for tbl in page.get("tables", []):
            tbl_txt = _flatten_table_to_text(tbl)
            if tbl_txt:
                text_parts.append("[TABLE]\n" + tbl_txt)
        
        page_text = "\n\n".join(text_parts).strip()
        if not page_text:
            continue
        
        # Fast chunking without sentence boundary search
        i = 0
        while i < len(page_text):
            end_pos = min(i + max_chars, len(page_text))
            chunk_text = page_text[i:end_pos].strip()
            
            if chunk_text and len(chunk_text) > 50:
                chunks.append({
                    "page": page["page"],
                    "text": chunk_text,
                    "chunk_type": "fast"
                })
            
            if end_pos >= len(page_text):
                break
            i = end_pos - overlap if overlap < end_pos - i else i + 1
    
    return chunks

def normalize_medical_text(text: str) -> str:
    """Light medical text normalization"""
    # Basic medical abbreviation expansion
    text = re.sub(r'\bMI\b', 'myocardial infarction', text, flags=re.IGNORECASE)
    text = re.sub(r'\bHTN\b', 'hypertension', text, flags=re.IGNORECASE)
    text = re.sub(r'\bDM\b', 'diabetes mellitus', text, flags=re.IGNORECASE)
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()



def build_chunks_from_structured_old(structured, max_chars=1200, overlap=150):
    """Enhanced chunking with smart text boundaries"""
    _ensure_nltk_data()
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

        # Enhanced chunking with smart boundaries
        i = 0
        while i < len(page_text):
            # Find optimal end position
            target_end = i + max_chars
            if target_end >= len(page_text):
                chunk_text = page_text[i:]
                end_pos = len(page_text)
            else:
                end_pos = _find_best_split_point(page_text, target_end)
                chunk_text = page_text[i:end_pos].strip()
            
            if chunk_text:  # Only add non-empty chunks
                chunks.append({
                    "page": page["page"],
                    "text": chunk_text,
                    "start": i,
                    "end": end_pos,
                    "chunk_type": "enhanced"
                })
            
            if end_pos >= len(page_text):
                break
                
            # Smart overlap: find sentence boundary for overlap start
            next_start = max(i + 1, end_pos - overlap)
            if overlap > 0 and next_start < end_pos:
                next_start = _find_best_split_point(page_text, next_start, 50)
            
            i = next_start
    
    print(f"✂️ Enhanced chunking: {len(chunks)} chunks created")
    return chunks


def embed_chunks_multi_vector(chunks, batch_size=32):
    """Generate multiple embeddings for each chunk"""
    if not chunks:
        return chunks

    # Get both embedding models
    general_model = get_local_embedder()
    medical_model = get_medical_embedder()
    
    # Prepare texts
    general_texts = [c["text"] for c in chunks]
    medical_texts = [_enhance_medical_text(c["text"]) for c in chunks]
    
    print(f"🧠 Generating multi-vector embeddings for {len(chunks)} chunks...")
    
    # Generate general embeddings
    general_embeddings = []
    for i in range(0, len(general_texts), batch_size):
        batch = general_texts[i:i+batch_size]
        vecs = general_model.encode(batch, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        general_embeddings.extend(vecs)
    
    # Generate medical-specific embeddings
    medical_embeddings = []
    for i in range(0, len(medical_texts), batch_size):
        batch = medical_texts[i:i+batch_size]
        vecs = medical_model.encode(batch, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        medical_embeddings.extend(vecs)
    
    # Attach all embeddings to chunks
    for i, chunk in enumerate(chunks):
        chunk["embedding"] = general_embeddings[i].tolist()
        chunk["medical_embedding"] = medical_embeddings[i].tolist()
        chunk["embedding_dim"] = len(general_embeddings[i])
        
        # Generate sparse vector
        medical_entities = chunk.get("chunk_metadata", {}).get("medical_entities", [])
        chunk["sparse_vector"] = _create_sparse_vector(chunk["text"], medical_entities)
    
    print(f"✅ Multi-vector embeddings complete: general + medical + sparse")
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
    """Single document upload - existing functionality"""
    return _process_single_upload()

@app.route('/api/documents/batch-upload', methods=['POST'])
def batch_upload_documents():
    """Optimized batch upload for multiple files"""
    try:
        files = request.files.getlist('files')
        categories = request.form.getlist('categories')
        
        if not files:
            return jsonify({"error": "No files provided"}), 400
        
        print(f"📦 Starting batch upload of {len(files)} files")
        start_time = time.time()
        
        # Process files in parallel
        results = process_files_parallel(files, categories)
        
        elapsed = time.time() - start_time
        successful = sum(1 for r in results if r.get('success'))
        
        return jsonify({
            "success": True,
            "message": f"Batch upload completed: {successful}/{len(files)} files processed",
            "results": results,
            "processing_time": f"{elapsed:.2f}s",
            "files_per_second": f"{len(files)/elapsed:.2f}"
        })
        
    except Exception as e:
        print(f"❌ Batch upload error: {e}")
        return jsonify({"error": f"Batch upload failed: {e}"}), 500

def _process_single_upload():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        categories = request.form.getlist('categories')
        
        # Process single file
        result = process_single_file(file, categories)
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return jsonify({"error": f"Upload failed: {e}"}), 500

def process_single_file(file, categories):
    """Process a single file - extracted for reuse in batch processing"""
    try:
        pdf_bytes = file.read()

        # Validate PDF
        if not pdf_bytes.startswith(b'%PDF'):
            return {"error": f"File {file.filename} is not a PDF", "success": False}

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

        # 2) Smart chunking with medical preprocessing
        chunks = build_smart_chunks(extracted)
        print(f"✂️ Created {len(chunks)} smart chunks")

        # 3) Optimized embeddings
        chunks = embed_chunks_optimized(chunks, batch_size=32)
        print(f"🧠 Embeddings added, dim={chunks[0]['embedding_dim'] if chunks else 0}")

        # 4) Create document-level metadata
        document_metadata = {
            "filename": file.filename,
            "upload_date": datetime.now().isoformat(),
            "file_size": len(pdf_bytes),
            "total_pages": len(extracted.get("pages", [])),
            "document_type": "medical_pdf",
            "medical_specialty": _detect_medical_specialty(extracted.get("full_text", "")),
            "language": "en"  # Could be enhanced with language detection
        }
        
        # 5) Add hierarchical categories to chunks
        full_text_sample = extracted.get("full_text", "")[:2000]  # Sample for analysis
        category_hierarchy = _categorize_hierarchically(categories, full_text_sample)
        
        for chunk in chunks:
            chunk["category_hierarchy"] = category_hierarchy
        
        # 6) Bulk index into OpenSearch
        if os_client:
            bulk_index_chunks(os_client, document_id, s3_key, categories, chunks, document_metadata)

        # Preview only (don’t return full vectors for all chunks)
        return {
            "success": True,
            "document_id": document_id,
            "filename": file.filename,
            "size": len(pdf_bytes),
            "chunks_count": len(chunks),
            "embedding_dim": chunks[0]["embedding_dim"] if chunks else 0
        }

    except Exception as e:
        print(f"❌ Processing error for {file.filename}: {e}")
        return {"error": f"Processing failed: {e}", "success": False, "filename": file.filename}

def bulk_index_chunks(os_client, document_id, s3_key, categories, chunks, document_metadata):
    """Bulk index chunks for better performance"""
    if not chunks:
        return
    
    # Prepare bulk operations
    bulk_body = []
    for chunk in chunks:
        # Add minimal metadata
        chunk["chunk_metadata"] = {"word_count": len(chunk["text"].split())}
        chunk["content_type"] = "paragraph"
        
        # Index operation
        bulk_body.append({"index": {"_index": INDEX_NAME}})
        bulk_body.append({
            "doc_id": document_id,
            "page": chunk["page"],
            "text": chunk["text"],
            "categories": categories,
            "s3_key": s3_key,
            "embedding": chunk["embedding"],
            "chunk_type": chunk.get("chunk_type", "fast"),
            "content_type": chunk["content_type"],
            "chunk_metadata": chunk["chunk_metadata"],
            "document_metadata": document_metadata or {}
        })
    
    # Bulk index with batching
    batch_size = 100
    for i in range(0, len(bulk_body), batch_size * 2):
        batch = bulk_body[i:i + batch_size * 2]
        try:
            response = os_client.bulk(body=batch)
            if response.get('errors'):
                print(f"⚠️ Some bulk indexing errors in batch {i//batch_size//2 + 1}")
        except Exception as e:
            print(f"❌ Bulk batch failed: {e}")
    
    print(f"✅ Bulk indexed {len(chunks)} chunks")

def process_files_parallel(files, categories, max_workers=3):
    """Process multiple files in parallel"""
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(process_single_file, file, categories): file.filename 
            for file in files
        }
        
        for future in as_completed(future_to_file):
            filename = future_to_file[future]
            try:
                result = future.result()
                result['filename'] = filename
                results.append(result)
                print(f"✅ Completed: {filename}")
            except Exception as e:
                print(f"❌ Failed: {filename} - {e}")
                results.append({
                    "filename": filename,
                    "error": str(e),
                    "success": False
                })
    
    return results

@app.route('/api/query', methods=['POST'])
def query_documents():
    try:
        data = request.get_json()
        query_text = data.get("query")
        top_k = int(data.get("top_k", 5))

        if not query_text:
            return jsonify({"error": "Missing query"}), 400

        # Multi-vector query embedding
        general_model = get_local_embedder()
        medical_model = get_medical_embedder()
        
        query_vector = general_model.encode([query_text], normalize_embeddings=True)[0].tolist()
        medical_vector = medical_model.encode([_enhance_medical_text(query_text)], normalize_embeddings=True)[0].tolist()
        
        # Create sparse vector for query
        query_entities = _extract_medical_entities(query_text)
        sparse_vector = _create_sparse_vector(query_text, query_entities)
        
        # Simple search (hybrid function not imported)
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

        # 1) Optimized query processing with caching
        enhanced_query = enhance_query(query)
        print(f"🔍 Enhanced query: '{enhanced_query}'")
        
        # Use cached embedding for O(1) repeated queries
        qvec = get_cached_embedding(enhanced_query, "medical")
        
        # 2) Optimized vector search
        start_time = time.time()
        resp = search_similar(os_client, qvec, top_k=top_k)
        search_time = time.time() - start_time
        print(f"🔍 Search completed in {search_time:.3f}s, hits: {len(resp.get('hits', {}).get('hits', []))}")

        # 3) Prepare snippets + build sources list for UI
        snippets = []
        ui_sources = []
        seen_files = set()  # Track seen filenames to avoid duplicates

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
            
            # Clean filename and check for duplicates first
            s3_key = src.get("s3_key")
            filename = s3_key.rsplit("/", 1)[-1] if s3_key else "document.pdf"
            # Remove document ID prefix - find the actual filename after underscore
            if "_" in filename:
                parts = filename.split("_")
                # Find the part that starts with actual document name (WHO, CDC, etc.)
                for i, part in enumerate(parts):
                    if part.startswith(("WHO", "CDC", "NIH", "FDA")) or part.endswith(".pdf"):
                        filename = "_".join(parts[i:])
                        break
                else:
                    # If no recognizable prefix found, take everything after first underscore
                    filename = "_".join(parts[1:])
            
            # Skip duplicates based on cleaned filename
            if filename in seen_files:
                continue
            seen_files.add(filename)
            
            text = (src.get("text") or "").strip()
            if not text:
                continue
            
            # Keep snippet length manageable
            snippets.append(text[:1200])

            # Filename already cleaned above

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

        # 4) Return OpenSearch results as formatted answer (no Bedrock)
        if not snippets:
            answer = "No relevant documents found for your query. This could be due to: 1) No documents uploaded yet, 2) Query doesn't match document content, or 3) Index needs time to refresh."
        else:
            # Format top results as answer
            answer_parts = []
            for i, snippet in enumerate(snippets[:3], 1):
                answer_parts.append(f"[{i}] {snippet[:400]}...")
            answer = "\n\n".join(answer_parts)

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