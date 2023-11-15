# Importing required packages
import streamlit as st
import OpenAI
import uuid
import time
import tempfile

# Model information
MODEL = "gpt-4-1106-preview"

# OpenAI client setup
from openai import OpenAI
client = OpenAI()

# Session state initialization
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "run" not in st.session_state:
    st.session_state.run = {"status": None}

if "messages" not in st.session_state:
    st.session_state.messages = []

if "retry_error" not in st.session_state:
    st.session_state.retry_error = 0

# Page configuration
st.set_page_config(page_title="Google Guidelines Chat", page_icon=":books:")

# Page header
st.header("Google Guidelines Chat :books:")

# API key and assistant setup
if "assistant" not in st.session_state:
    openai.api_key = st.secrets["OPENAI_API_KEY"]
    st.session_state.assistant = openai.beta.assistants.retrieve(st.secrets["OPENAI_ASSISTANT"])

    # Create a new thread for this session
    st.session_state.thread = client.beta.threads.create(
        metadata={
            'session_id': st.session_state.session_id,
        }
    )

# Function to upload file to OpenAI and return file ID
def upload_file_to_openai(uploaded_file):
    try:
        response = client.files.create(
            file=uploaded_file,  # Directly using the uploaded file
            purpose='assistants'
        )
        return response.id
    except Exception as e:
        st.error(f"Error uploading file to OpenAI: {e}")
        return None

# Sidebar for PDF uploads and keyword entry
with st.sidebar:
    st.header("Upload PDFs and Keyword")
    your_site_pdf = st.file_uploader("1\. Upload Your Site PDF", type=["pdf"])
    # Updated to accept multiple files
    competitor_pdfs = st.file_uploader("2\. Upload Upto 3 Competitor PDFs", type=["pdf"], accept_multiple_files=True)
    keyword = st.text_input("3\. Enter Main Keyword")
    process_button = st.button("Get Report")

# Processing logic when the button is pressed
if process_button:

    # Introduce a 10-second delay
    time.sleep(10)

    file_ids = []
    your_site_pdf_name = your_site_pdf.name if your_site_pdf is not None else "No file"
    competitor_pdf_names = [pdf.name for pdf in competitor_pdfs] if competitor_pdfs else ["No files"]

    if your_site_pdf is not None:
        file_id = upload_file_to_openai(your_site_pdf)
        if file_id:
            file_ids.append(file_id)

    # Handling multiple competitor PDFs
    if competitor_pdfs is not None:
        for competitor_pdf in competitor_pdfs:
            file_id = upload_file_to_openai(competitor_pdf)
            if file_id:
                file_ids.append(file_id)
   
    # Introduce a 10-second delay
    time.sleep(10)

    # Check if any files were uploaded and processed
    if file_ids:
        # Construct the prompt with file names
        prompt = f"My web page is {your_site_pdf_name}, the competitors' web pages are {', '.join(competitor_pdf_names)} and my main keyword is {keyword}."

        # Introduce a 10-second delay
        time.sleep(10)
       
        # Send a message to the thread with the file IDs
        st.session_state.messages = client.beta.threads.messages.create(
            thread_id=st.session_state.thread.id,
            role="user",
            content=prompt,
            file_ids=file_ids
        )

        st.session_state.run = client.beta.threads.runs.create(
            thread_id=st.session_state.thread.id,
            assistant_id=st.session_state.assistant.id,
        )
        if st.session_state.retry_error < 3:
            time.sleep(1)
            st.rerun()

# Message handling and display
elif hasattr(st.session_state.run, 'status') and st.session_state.run.status == "completed":
    st.session_state.messages = client.beta.threads.messages.list(
        thread_id=st.session_state.thread.id
    )

    for thread_message in st.session_state.messages.data:
        for message_content in thread_message.content:
            message_content = message_content.text
            annotations = message_content.annotations
            citations = []

            for index, annotation in enumerate(annotations):
                message_content.value = message_content.value.replace(annotation.text, f' [{index}]')
                if (file_citation := getattr(annotation, 'file_citation', None)):
                    cited_file = client.files.retrieve(file_citation.file_id)
                    citations.append(f'[{index}] {file_citation.quote} from {cited_file.filename}')
                elif (file_path := getattr(annotation, 'file_path', None)):
                    cited_file = client.files.retrieve(file_path.file_id)
                    citations.append(f'[{index}] Click <here> to download {cited_file.filename}')

            message_content.value += '\n' + '\n'.join(citations)

    for message in reversed(st.session_state.messages.data):
        if message.role in ["user", "assistant"]:
            with st.chat_message(message.role):
                for content_part in message.content:
                    message_text = content_part.text.value
                    st.markdown(message_text)

# Chat input
if prompt := st.chat_input("Message me"):
    with st.chat_message('user'):
        st.write(prompt)

    st.session_state.messages = client.beta.threads.messages.create(
        thread_id=st.session_state.thread.id,
        role="user",
        content=prompt
    )

    st.session_state.run = client.beta.threads.runs.create(
        thread_id=st.session_state.thread.id,
        assistant_id=st.session_state.assistant.id,
    )
    if st.session_state.retry_error < 3:
        time.sleep(1)
        st.rerun()

# Run status and retry logic
if hasattr(st.session_state.run, 'status'):
    if st.session_state.run.status == "running":
        with st.chat_message('assistant'):
            st.write("Thinking ......")
        if st.session_state.retry_error < 3:
            time.sleep(1)
            st.rerun()

    elif st.session_state.run.status == "failed":
        st.session_state.retry_error += 1
        with st.chat_message('assistant'):
            if st.session_state.retry_error < 3:
                st.write("Run failed, retrying ......")
                time.sleep(3)
                st.rerun()
            else:
                st.error("FAILED: The OpenAI API is currently processing too many requests. Please try again later ......")

    elif st.session_state.run.status != "completed":
        st.session_state.run = client.beta.threads.runs.retrieve(
            thread_id=st.session_state.thread.id,
            run_id=st.session_state.run.id,
        )
        if st.session_state.retry_error < 3:
            time.sleep(3)
            st.rerun()
