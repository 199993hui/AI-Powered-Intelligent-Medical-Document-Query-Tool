import streamlit as st
import requests
import json
from pathlib import Path

# Backend API configuration
BACKEND_URL = "http://localhost:8000"

# 🌐 Page setup
st.set_page_config(page_title="AI Medical Document Query Tool", layout="wide")

def upload_to_backend(file_content, filename, categories):
    """Upload file to Flask backend"""
    try:
        files = {'file': (filename, file_content, 'application/pdf')}
        data = {'categories': json.dumps(categories)}
        
        response = requests.post(f"{BACKEND_URL}/api/documents/upload", files=files, data=data)
        return response.json(), response.status_code == 200
    except Exception as e:
        return {"error": str(e)}, False

def get_categories():
    """Get available categories from backend"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/categories")
        if response.status_code == 200:
            return response.json().get("categories", [])
    except:
        pass
    return ["patient_records", "clinical_guidelines", "research_papers", "lab_results", "medication_schedules"]

def get_documents():
    """Get document list from backend"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/documents")
        if response.status_code == 200:
            return response.json().get("documents", [])
    except:
        pass
    return []

def search_documents(query):
    """Search documents using natural language query"""
    try:
        response = requests.post(f"{BACKEND_URL}/api/search/query", json={"query": query})
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Search error: {e}")
    return None

# --- SIDEBAR ---
with st.sidebar:
    st.header("📤 Document Management")
    
    # Check backend connection
    try:
        health_response = requests.get(f"{BACKEND_URL}/health", timeout=2)
        if health_response.status_code == 200:
            st.success("✅ Backend Connected")
        else:
            st.error("❌ Backend Error")
    except:
        st.error("❌ Backend Offline")
        st.info("Start backend: `cd backend && python app.py`")
    
    # PDF Upload Form
    with st.expander("📤 Upload PDF(s)"):
        uploaded_pdfs = st.file_uploader(
            "Upload PDF files", 
            type=["pdf"], 
            accept_multiple_files=True
        )
        
        if uploaded_pdfs:
            st.write(f"Selected {len(uploaded_pdfs)} file(s):")
            for pdf in uploaded_pdfs:
                st.write(f"• {pdf.name}")
            
            # Category selection
            available_categories = get_categories()
            selected_categories = st.multiselect(
                "Select Categories:",
                available_categories,
                default=["patient_records"]
            )
            
            if st.button("Upload All Documents"):
                if selected_categories:
                    success_count = 0
                    total_files = len(uploaded_pdfs)
                    
                    # Progress bar
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i, pdf in enumerate(uploaded_pdfs):
                        status_text.text(f"Uploading {pdf.name}...")
                        
                        file_content = pdf.read()
                        result, success = upload_to_backend(file_content, pdf.name, selected_categories)
                        
                        if success:
                            success_count += 1
                            st.success(f"✅ {pdf.name} uploaded successfully")
                        else:
                            st.error(f"❌ {pdf.name}: {result.get('error', 'Upload failed')}")
                        
                        # Update progress
                        progress_bar.progress((i + 1) / total_files)
                    
                    status_text.text(f"Completed: {success_count}/{total_files} files uploaded successfully")
                    
                    if success_count == total_files:
                        st.balloons()
                else:
                    st.warning("Please select at least one category")
    
    # Document List
    with st.expander("📋 Document Inventory"):
        documents = get_documents()
        if documents:
            # Search filter
            search_term = st.text_input("🔍 Search documents:", key="doc_search")
            
            # Filter documents
            filtered_docs = documents
            if search_term:
                filtered_docs = [doc for doc in documents if search_term.lower() in doc['filename'].lower()]
            
            # Pagination
            docs_per_page = 5
            total_docs = len(filtered_docs)
            total_pages = (total_docs - 1) // docs_per_page + 1 if total_docs > 0 else 1
            
            if total_docs > docs_per_page:
                page = st.selectbox("Page:", range(1, total_pages + 1), key="doc_page")
                start_idx = (page - 1) * docs_per_page
                end_idx = min(start_idx + docs_per_page, total_docs)
                page_docs = filtered_docs[start_idx:end_idx]
                st.caption(f"Showing {start_idx + 1}-{end_idx} of {total_docs} documents")
            else:
                page_docs = filtered_docs
            
            # Display documents
            for doc in page_docs:
                st.write(f"📄 **{doc['filename']}**")
                st.write(f"Categories: {', '.join(doc['categories'])}")
                st.write(f"Size: {doc['size']} bytes")
                st.write("---")
        else:
            st.info("No documents uploaded yet")

# --- MAIN CONTENT ---
st.title("🏥 AI Medical Document Query Tool")
st.markdown("Upload medical PDFs and query them using natural language")

# Search examples
with st.expander("💡 Search Examples"):
    st.write("Try asking:")
    example_queries = [
        "What medications is the patient taking?",
        "Show me diabetes treatment protocols",
        "Find lab results for blood pressure",
        "Patient records with heart conditions"
    ]
    for query in example_queries:
        if st.button(query, key=f"example_{query[:20]}"):
            st.session_state.messages.append({"role": "user", "content": query})
            st.rerun()

# Chat Interface
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about your medical documents..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Search documents using the query
        search_results = search_documents(prompt)
        
        if search_results and search_results.get('results'):
            query_analysis = search_results.get('query_analysis', {})
            
            response = f"**Query Analysis:**\n"
            response += f"- **Expanded Query:** {query_analysis.get('expanded_query', prompt)}\n"
            response += f"- **Intent:** {query_analysis.get('intent', 'general_medical')}\n"
            
            entities = query_analysis.get('medical_entities', {})
            if any(entities.values()):
                response += f"\n**Medical Entities:**\n"
                for entity_type, entity_list in entities.items():
                    if entity_list:
                        response += f"- **{entity_type.title()}:** {', '.join(entity_list)}\n"
            
            results = search_results.get('results', [])
            response += f"\n**Found {len(results)} document(s):**\n\n"
            
            for i, result in enumerate(results[:3], 1):
                response += f"**{i}. {result.get('filename', 'Unknown')}**\n"
                response += f"- Relevance: {result.get('relevance_score', 0):.2f}\n"
                response += f"- Excerpt: {result.get('excerpt', 'No excerpt')}\n\n"
        else:
            response = f"I searched for: '{prompt}' but couldn't find matching documents. Try uploading relevant PDFs first."
        
        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})