import streamlit as st
from ollama import Client
from pathlib import Path

# 🧠 Set up Ollama client
client = Client(host='http://localhost:11434')  # default Ollama host

# 🌐 Page setup
st.set_page_config(page_title="LLaMA2 Chatbot", layout="wide")

# --- FORM in SIDEBAR ---
with st.sidebar:
    with st.expander("📤 Submit PDF Form"):
        uploaded_pdf = st.file_uploader("Upload a PDF", type=["pdf"], key="pdf_file")

        with st.form("pdf_form"):
            submitted = st.form_submit_button("Submit PDF")

            if submitted:
                if uploaded_pdf is None:
                    st.warning("Please upload a PDF.")
                else:
                    #### PDF SUBMISSION ####
                    save_dir = Path("uploaded_pdfs")
                    save_dir.mkdir(exist_ok=True)

                    filepath = save_dir / uploaded_pdf.name
                    with open(filepath, "wb") as f:
                        f.write(uploaded_pdf.read())

                    st.success(f"PDF '{uploaded_pdf.name}' saved.")

st.title("🤖 Chat with LLaMA2")

if "messages" not in st.session_state:
  st.session_state.messages = []

for message in st.session_state.messages:
  with st.chat_message(message["role"]):
    st.markdown(message["content"])

if prompt := st.chat_input("What is up?"):
  st.session_state.messages.append({"role": "user", "content": prompt})
  with st.chat_message("user"):
    st.markdown(prompt)

  with st.chat_message("assistant"):
    message_placeholder = st.empty()

    ###### LLM ######
    full_response = client.chat(
                model='llama2',
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    *[
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.messages
                    ]
                ]
            )
    full_response = full_response.message.content

    message_placeholder.markdown(full_response)
  st.session_state.messages.append({"role": "assistant", "content": full_response})