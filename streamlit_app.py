import streamlit as st
import google.generativeai as genai
import time
import re
import os
import mimetypes
import tempfile
import speech_recognition as sr
import hashlib
from PyPDF2 import PdfReader
from docx import Document
import pytesseract
from PIL import Image
import pandas as pd
import json
import xml.etree.ElementTree as ET
from io import BytesIO
import base64

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY environment variable")

genai.configure(api_key=GEMINI_API_KEY)

st.set_page_config(
    page_title="Interlink AI",
    page_icon="./favicon.ico",
    layout="wide"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');

    * {
        font-family: 'Montserrat', sans-serif !important;
    }

    .stChatInputContainer {
        display: flex;
        align-items: center;
    }
    .back-button {
        width: 300px;
        margin-top: 20px;
        padding: 10px 20px;
        font-size: 18px;
        background-color: #0b1936;
        color: #5799f7;
        border: 2px solid #4a83d4;
        border-radius: 10px;
        cursor: pointer;
        transition: all 0.3s ease;
        font-family: 'Montserrat', sans-serif !important;
        text-transform: uppercase;
        letter-spacing: 2px;
        box-shadow: 0 0 15px rgba(74, 131, 212, 0.3);
        position: relative;
        overflow: hidden;
        display: inline-block;
    }
    .back-button:before {
        content: 'BACK TO INTERLINK';
        display: flex;
        align-items: center;
        justify-content: center;
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: #0b1936;
        transition: transform 0.3s ease;
        font-size: 18px;
        color: #5799f7;
        text-align: center;
        font-family: 'Montserrat', sans-serif !important;
    }
    .back-button:hover {
        background-color: #1c275c;
        color: #73abfa;
        transform: translateY(-2px);
        box-shadow: 0 6px 8px rgba(74, 131, 212, 0.2);
    }
    .back-button:hover:before {
        transform: translateY(-100%);
        color: #73abfa;
    }
    .file-preview {
        max-height: 200px;
        overflow: hidden;
        margin-bottom: 10px;
    }
    .file-preview img, .file-preview video, .file-preview audio {
        max-width: 100%;
        max-height: 200px;
        object-fit: contain;
    }

    .stMarkdown, .stText, .stTitle, .stHeader {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    .stButton button {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    .stTextInput input {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    .stSelectbox select {
        font-family: 'Montserrat', sans-serif !important;
    }
</style>
<script>
document.addEventListener('paste', function(e) {
    if (document.activeElement.tagName !== 'TEXTAREA' && document.activeElement.tagName !== 'INPUT') {
        e.preventDefault();
        const items = e.clipboardData.items;
        
        for (const item of items) {
            if (item.type.indexOf('image') !== -1) {
                const blob = item.getAsFile();
                const reader = new FileReader();
                reader.onload = function(e) {
                    const base64data = e.target.result;
                    window.parent.postMessage({
                        type: 'clipboard_paste',
                        data: base64data,
                        format: 'image'
                    }, '*');
                };
                reader.readAsDataURL(blob);
            } else if (item.type === 'text/plain') {
                item.getAsString(function(text) {
                    window.parent.postMessage({
                        type: 'clipboard_paste',
                        data: text,
                        format: 'text'
                    }, '*');
                });
            }
        }
    }
});
window.addEventListener('message', function(e) {
    if (e.data.type === 'clipboard_paste') {
        const args = {
            'data': e.data.data,
            'format': e.data.format
        };
        window.parent.postMessage({
            type: 'streamlit:set_widget_value',
            key: 'clipboard_data',
            value: args
        }, '*');
    }
});
</script>
<center>
    <a href="https://interlinkcvhs.org/" class="back-button" target="_blank" rel="noopener noreferrer">
        interlinkcvhs.org
    </a>
</center>""", unsafe_allow_html=True)

generation_config = {
    "temperature": 0,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

SYSTEM_INSTRUCTION = """
Name: Your name is Interlink AI.
Creator: You were developed by the Interlink team.
Technology: You are powered by Google Gemini.
Platform: You are hosted on the Interlink website.
Website: https://interlinkcvhs.org/.

Behavioral Guidelines:
Be helpful and professional, ensuring accuracy in every response.
Avoid being overly promotional—mention Interlink's features only when relevant or when asked.
Maintain a friendly, approachable tone while providing precise and concise answers.

Interlink's Features for Carnegie Vanguard High School (CVHS) Freshmen:
Customizable Scheduling Tool: Helps students manage assignments and stay organized. (https://interlinkcvhs.org/)
Subject Notes: Comprehensive notes for a variety of subjects. (https://interlinkcvhs.org/subject-study)
Question Bank (QBank): Hundreds of practice problems to help students prepare for tests. (https://interlinkcvhs.org/qbank)
Quizlets: Study resources to aid in test preparation. (https://interlinkcvhs.org/quizlets)
AP Human Geography Flashcards: Weekly terms and definitions tailored to the curriculum. (https://interlinkcvhs.org/extra/hug-vocab)
Educational Podcasts: Learn on-the-go with study-focused audio content. (https://interlinkcvhs.org/extra/deepdives)
Question of the Day (QOTD): A daily random question to reinforce key test topics. (https://interlinkcvhs.org/qotd)
Productivity Tools: General tools to enhance efficiency and focus. (https://interlinkcvhs.org/extra/productivity)

You can apply to contribute to Interlink at [https://interlinkcvhs.org/apply].
"""

PREBUILT_COMMANDS = {
    "/weeklyhgflashcards": {
        "title": "/weeklyhgflashcards",
        "description": "Paste a list of human geography terms.",
        "prompt": "With the following AP Human Geography vocabulary words, please created a list formatted as such: (IMPORTANT: Everywhere after, where it says Term, replace that with the term listed, don't explicitly write Term: and Definition: - make sure that you don't write out 'Definition' you actually put the definition of the term before) First, the line begins with Term: (in bold) Definition. The next two lines use a bullleted list format. The first bullet is In Other Words: (in bold) then a rephrasing/restatement/another way to say the term. The next bullet point is Examples: (in bold) and then comma-separated list of 2-5 examples of that term. For the next terms, go to the next line without any bullets for the definition once more."
    },
    "/cornellformat": {
        "title": "/cornellformat",
        "description": "Paste your digital notes.",
        "prompt": "Format the following notes into a Cornell Notes tabular format. First, before the table, should be the title. Then, create a table with two columns and multiple rows as necessary. The header for the two columns is Cues | Notes. The cues section contains questions that the corresponding notes answer. There can be multiple related lines of notes for one cue. At the end of all the cues & notes, after the table, type Summary: (in bold) and then a comprehensive, detailed summary of the notes with all necessary information while keeping it concise."
    },
    "/answer4math": {
        "title": "/answer4math",
        "description": "Provide math questions in a typed-out, image, PDF, or other file format.",
        "prompt": "Extract the math questions from the text or file added. If image, OCR and gain information. For other file formats, proceed as necessary. Provide the answer to each question systematically along with work and steps. Format as such: If there is an identifier (ex. #1) for a question, use that before. Then, within 1-2 lines (no enters or new lines, keep everything just in one line, super concise, use markdown as necessary), show the steps to get to the answer, and then provide the answer bolded. Make sure these work for multiple choice, open-ended, and free-response question types. Make sure to use optimal accuracy and confirm all answers."
    },
    "/summarize": {
        "title": "/summarize",
        "description": "Provide a long set of notes/an article.",
        "prompt": "Summarize the following notes or article into key points and brief 1-2 paragraph summary. Highlight the most important concepts and facts, focus on key definitions."
    },
    "/check4grammar": {
        "title": "/check4grammar",
        "description": "Provide a set of text for grammar to be verified.",
        "prompt": "Check the following text for grammatical errors and provide a bulleted list of corrections needed to fix. At the end, in a new line, provide the full text completed revised. Highligh the revised sections in bold."
    },
    "/synonyms": {
        "title": "/synonyms",
        "description": "Provide a word to find synonyms.",
        "prompt": "For the word provided below, provide a definition, examples, and also synonyms. Also provide 1-3 antonyms at the bottom."
    },
    "/citation": {
        "title": "/citation",
        "description": "Paste any information for a source and what citation style you need.",
        "prompt": "With the following information, format into a citation based on the citation style mentioned below. If there is no citation style, make it in multiple formats."
    },
    "/essayoutline": {
        "title": "/essayoutline",
        "description": "Paste a topic for an essay, as detailed as possible.",
        "prompt": "Based on the following topic provided and details, create a 5-paragraph essay outline (unless otherwise mentioned below for changes in the numbers of paragraphs or format) which has an introduction, three body paragraphs, and a conclusion. It should be formatted very professionally with clear topics and correct grammar."
    },
    "/litanalysis": {
        "title": "/litanalysis",
        "description": "Provide of piece of literature or an excerpt to be analyzed.",
        "prompt": "Analyze the following text and provide detailed, comprehensive summaries and insights on characters, themes, main ideas or various sections, and symbolism used. Have a comprehensive view for a high school classroom-type insight for the literature provided."
    },
    "/translation": {
        "title": "/translation",
        "description": "Provide a piece of text and what language the text is in and what is must be translated to.",
        "prompt": "Based on the text below, translate it to the language provide based on what the text is in."
    },
    "/wordcount": {
        "title": "/wordcount",
        "description": "Provide a piece of text, an image, PDF file, or other file format.",
        "prompt": "Based on the provided data in the files or text input, count the number of words in the submission and provide it back."
    }
    # Add more as needed
}

def extract_pdf_text(file):
    try:
        pdf = PdfReader(file)
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        return f"Error extracting PDF text: {str(e)}"

def extract_docx_text(file):
    try:
        doc = Document(file)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    except Exception as e:
        return f"Error extracting DOCX text: {str(e)}"

def extract_image_text(file):
    try:
        image = Image.open(file)
        return pytesseract.image_to_string(image)
    except Exception as e:
        return f"Error extracting image text: {str(e)}"

def process_structured_data(file, mime_type):
    try:
        if mime_type == 'text/csv':
            df = pd.read_csv(file)
            return df.to_string()
        elif mime_type == 'application/json':
            return json.dumps(json.load(file), indent=2)
        elif mime_type == 'application/xml':
            tree = ET.parse(file)
            return ET.tostring(tree.getroot(), encoding='unicode', method='xml')
        return file.read().decode('utf-8')
    except Exception as e:
        return f"Error processing structured data: {str(e)}"

def process_response(text):
    lines = text.split('\n')
    processed_lines = []
    
    for line in lines:
        if re.match(r'^\d+\.', line.strip()):
            processed_lines.append('\n' + line.strip())
        elif line.strip().startswith('*') or line.strip().startswith('-'):
            processed_lines.append('\n' + line.strip())
        else:
            processed_lines.append(line)
    
    text = '\n'.join(processed_lines)
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
    text = re.sub(r'(\n[*-] .+?)(\n[^*\n-])', r'\1\n\2', text)
    
    return text.strip()

# Add this function to handle clipboard data
def handle_clipboard_data():
    if 'clipboard_data' not in st.session_state:
        return
        
    clipboard_data = st.session_state.get('clipboard_data')
    if clipboard_data:
        try:
            if clipboard_data['format'] == 'image':
                img_data = base64.b64decode(clipboard_data['data'].split(',')[1])
                file = BytesIO(img_data)
                file.name = f'pasted_image_{int(time.time())}.png'
                return file
            elif clipboard_data['format'] == 'text':
                file = BytesIO(clipboard_data['data'].encode())
                file.name = f'pasted_text_{int(time.time())}.txt'
                return file
        finally:
            st.session_state.clipboard_data = None
    return None

def detect_file_type(uploaded_file):
    filename = uploaded_file.name
    file_ext = os.path.splitext(filename)[1].lower()
    
    mime_mappings = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg', 
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
        '.tiff': 'image/tiff',
        '.mp4': 'video/mp4',
        '.avi': 'video/x-msvideo', 
        '.mov': 'video/quicktime',
        '.mkv': 'video/x-matroska',
        '.webm': 'video/webm',
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.ogg': 'audio/ogg',
        '.m4a': 'audio/mp4',
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.txt': 'text/plain',
        '.csv': 'text/csv',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.json': 'application/json',
        '.xml': 'application/xml'
    }
    
    if file_ext in mime_mappings:
        return mime_mappings[file_ext]
    
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or 'application/octet-stream'

def initialize_session_state():
    if 'chat_model' not in st.session_state:
        st.session_state.chat_model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=generation_config,
            system_instruction=SYSTEM_INSTRUCTION,
        )

    if 'chat_session' not in st.session_state:
        st.session_state.chat_session = st.session_state.chat_model.start_chat(history=[])

    if 'messages' not in st.session_state:
        initial_message = """Hello! I'm Interlink AI, your personal academic assistant for Carnegie Vanguard High School. How can I assist you today?"""
        st.session_state.messages = [
            {"role": "assistant", "content": initial_message}
        ]
    
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
        
    if 'processed_audio_hashes' not in st.session_state:
        st.session_state.processed_audio_hashes = set()
        
    if 'camera_image' not in st.session_state:
        st.session_state.camera_image = None
        
    if 'camera_enabled' not in st.session_state:
        st.session_state.camera_enabled = False

    if 'clipboard_data' not in st.session_state:
        st.session_state.clipboard_data = None
    if 'file_upload_expanded' not in st.session_state:
        st.session_state.file_upload_expanded = False

def get_audio_hash(audio_data):
    return hashlib.md5(audio_data.getvalue()).hexdigest()

def convert_audio_to_text(audio_file):
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            return text
    except sr.UnknownValueError:
        raise Exception("Speech recognition could not understand the audio")
    except sr.RequestError as e:
        raise Exception(f"Could not request results from speech recognition service; {str(e)}")

def save_audio_file(audio_data):
    audio_bytes = audio_data.getvalue()
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmpfile:
        tmpfile.write(audio_bytes)
        return tmpfile.name

def handle_chat_response(response, message_placeholder):
    full_response = ""
    formatted_response = process_response(response.text)
    
    chunks = []
    for line in formatted_response.split('\n'):
        chunks.extend(line.split(' '))
        chunks.append('\n')
    
    for chunk in chunks:
        if chunk != '\n':
            full_response += chunk + ' '
        else:
            full_response += chunk
        time.sleep(0.02)
        message_placeholder.markdown(full_response + "▌", unsafe_allow_html=True)
    
    message_placeholder.markdown(full_response, unsafe_allow_html=True)
    return full_response

def show_file_preview(uploaded_file):
    mime_type = detect_file_type(uploaded_file)
    
    if mime_type.startswith('image/'):
        st.sidebar.image(uploaded_file, use_container_width=True)
    elif mime_type.startswith('video/'):
        st.sidebar.video(uploaded_file)
    elif mime_type.startswith('audio/'):
        st.sidebar.audio(uploaded_file)
    else:
        st.sidebar.info(f"Uploaded: {uploaded_file.name} (Type: {mime_type})")

def prepare_chat_input(prompt, files):
    input_parts = []
    
    for file in files:
        mime_type = detect_file_type(file)
        content = None
        
        try:
            if mime_type.startswith('application/pdf'):
                content = extract_pdf_text(file)
            elif mime_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                content = extract_docx_text(file)
            elif mime_type.startswith('image/'):
                content = extract_image_text(file)
            elif mime_type in ['text/csv', 'application/json', 'application/xml', 'text/plain']:
                content = process_structured_data(file, mime_type)
            
            if content:
                input_parts.append({
                    'type': mime_type,
                    'content': content,
                    'name': file.name
                })
        except Exception as e:
            st.error(f"Error processing {file.name}: {str(e)}")
            continue
    
    input_parts.append(prompt)
    return input_parts

def main():
    initialize_session_state()

    st.title("💬 Interlink AI")
    
    INTERLINK_LOGO = "interlink_logo.png"

    st.logo(
        INTERLINK_LOGO,
        size="large",
        link="https://interlinkcvhs.org/",
        icon_image=INTERLINK_LOGO,
    )

    # File Upload Section
    with st.sidebar:
        with st.expander("**File Upload**", expanded=False):
            clipboard_file = handle_clipboard_data()
            if clipboard_file:
                st.session_state.uploaded_files.append(clipboard_file)
            uploaded_files = st.file_uploader(
                "Upload files to analyze", 
                type=[
                    'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff',
                    'mp4', 'avi', 'mov', 'mkv', 'webm',
                    'mp3', 'wav', 'ogg', 'm4a',
                    'pdf', 'doc', 'docx', 'txt', 'csv', 'xlsx', 'json', 'xml'
                ],
                accept_multiple_files=True
            )

            if uploaded_files:
                oversized_files = []
                valid_files = []
                
                for file in uploaded_files:
                    if file.size > 20 * 1024 * 1024:  # 20MB limit
                        oversized_files.append(file.name)
                    else:
                        valid_files.append(file)
                
                if oversized_files:
                    st.warning(f"Files exceeding 20MB limit: {', '.join(oversized_files)}")
                
                st.session_state.uploaded_files = valid_files

    # Camera Input Section
    with st.sidebar:
        with st.expander("**Camera Input**", expanded=False):
            camera_enabled = st.checkbox("Enable camera", value=st.session_state.camera_enabled)
            
            if camera_enabled != st.session_state.camera_enabled:
                st.session_state.camera_enabled = camera_enabled
                st.session_state.camera_image = None
                
            if st.session_state.camera_enabled:
                camera_image = st.camera_input("Take a picture")
                if camera_image is not None:
                    st.session_state.camera_image = camera_image
                    st.image(camera_image, caption="Captured Image")
                    st.success("Image captured! You can now ask about the image.")

    # Voice Input Section
    with st.sidebar:
        with st.expander("**Voice Input**", expanded=False):
            audio_input = st.audio_input("Record your question")

    # Prebuilt Commands Section
    with st.sidebar:
        with st.expander("**Prebuilt Commands**", expanded=False):
            # Initialize current_command in session state if not present
            if 'current_command' not in st.session_state:
                st.session_state.current_command = None
                
            # Display current command status
            st.write("**Active:**", st.session_state.current_command if st.session_state.current_command else "None")
            
            # Create buttons for each command
            for cmd, info in PREBUILT_COMMANDS.items():
                col1, col2 = st.columns([4, 1])
                
                # Command button
                with col1:
                    button_active = st.session_state.current_command == cmd
                    if st.button(
                        info["title"],
                        key=f"cmd_{cmd}",
                        type="primary" if button_active else "secondary"
                    ):
                        # Toggle command state
                        if st.session_state.current_command == cmd:
                            st.session_state.current_command = None
                        else:
                            st.session_state.current_command = cmd
                        st.rerun()
                
                # Help button
                with col2:
                    help_key = f"help_{cmd}"
                    if help_key not in st.session_state:
                        st.session_state[help_key] = False
                    
                    # Toggle help display
                    button_text = "×" if st.session_state[help_key] else "?"
                    if st.button(button_text, key=f"help_btn_{cmd}"):
                        st.session_state[help_key] = not st.session_state[help_key]
                        st.rerun()
                
                # Display help text if enabled
                if st.session_state[help_key]:
                    st.info(info["description"])

    # Display messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"], unsafe_allow_html=True)

    # Handle audio input
    if audio_input is not None:
        audio_hash = get_audio_hash(audio_input)
        
        if audio_hash not in st.session_state.processed_audio_hashes:
            try:
                audio_file = save_audio_file(audio_input)
                st.audio(audio_input, format='audio/wav')
                
                try:
                    st.info("Converting speech to text...")
                    transcribed_text = convert_audio_to_text(audio_file)
                    
                    st.success("Speech converted to text!")
                    st.text(f"Transcribed text: {transcribed_text}")
                    
                    st.chat_message("user").markdown(transcribed_text)
                    st.session_state.messages.append({"role": "user", "content": transcribed_text})
                    
                    with st.chat_message("assistant"):
                        message_placeholder = st.empty()
                        response = st.session_state.chat_session.send_message(transcribed_text)
                        full_response = handle_chat_response(response, message_placeholder)
                        
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": full_response
                        })
                    
                    st.session_state.processed_audio_hashes.add(audio_hash)
                    
                finally:
                    os.unlink(audio_file)
                    
            except Exception as e:
                st.error(f"An error occurred while processing the audio: {str(e)}")
                st.warning("Please try again or type your question instead.")

    # Chat input handling
    prompt = st.chat_input("What can I help you with?")

    if prompt:
        final_prompt = prompt
        if hasattr(st.session_state, 'current_command') and st.session_state.current_command:
            command_prompt = PREBUILT_COMMANDS[st.session_state.current_command]["prompt"]
            final_prompt = f"{command_prompt}\n{prompt}"
            st.session_state.current_command = None

        input_parts = []
        
        if st.session_state.uploaded_files:
            for file in st.session_state.uploaded_files:
                input_parts.append({
                    'mime_type': detect_file_type(file),
                    'data': file.getvalue()
                })
        
        if st.session_state.camera_image:
            input_parts.append({
                'mime_type': 'image/jpeg',
                'data': st.session_state.camera_image.getvalue()
            })

        input_parts.append(final_prompt)

        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            try:
                response = st.session_state.chat_session.send_message(input_parts)
                full_response = handle_chat_response(response, message_placeholder)
                
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": full_response
                })
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                if "rate_limit" in str(e).lower():
                    st.warning("The API rate limit has been reached. Please wait a moment before trying again.")
                else:
                    st.warning("Please try again in a moment.")

        if st.session_state.camera_image and not st.session_state.camera_enabled:
            st.session_state.camera_image = None

if __name__ == "__main__":
    main()
