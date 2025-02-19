import streamlit as st
import httpx
import asyncio
import json
from typing import List, Dict, Any, AsyncGenerator
from datetime import datetime

# Configure the page layout
st.set_page_config(
    page_title="LIMITLESS",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add custom CSS for chat input positioning and styling
st.markdown("""
    <style>
    /* Base theme */
    .stApp {
        background-color: #1a1b1e;
        color: white;
    }

    /* Main container layout */
    .main-container {
        display: flex;
        flex-direction: column;
        height: calc(100vh - 80px);
        margin: -60px -20px;
        padding: 60px 20px;
        position: relative;
    }

    /* Messages container */
    .messages-container {
        flex-grow: 1;
        overflow-y: auto;
        padding-bottom: 100px;
    }

    /* Chat input container */
    .chat-input-container {
        position: fixed;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 60%;
        background-color: #2d2e33;
        padding: 20px;
        border-radius: 15px 15px 0 0;
        box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.1);
    }

    /* Message styling */
    .stChatMessage {
        background-color: #2d2e33 !important;
        border-radius: 10px;
        margin: 10px 0;
        padding: 15px;
    }

    /* User message */
    .stChatMessage[data-testid="user-message"] {
        background-color: #3a3b3f !important;
    }

    /* Assistant message */
    .stChatMessage[data-testid="assistant-message"] {
        background-color: #2d2e33 !important;
    }

    /* Sidebar styling */
    .css-1d391kg {
        background-color: #2d2e33;
        border-right: 1px solid #3a3b3f;
    }

    /* Chat history buttons */
    .stButton button {
        width: 100%;
        text-align: left;
        background-color: #2d2e33 !important;
        color: white !important;
        border: 1px solid #4a4b50 !important;
        margin: 5px 0;
        padding: 10px;
        transition: all 0.3s ease;
    }

    .stButton button:hover {
        background-color: #3a3b3f !important;
        border-color: #ffffff !important;
    }

    /* Title styling */
    .title {
        font-size: 2.5em;
        font-weight: bold;
        text-align: center;
        margin-bottom: 30px;
        color: white;
    }

    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
    }

    ::-webkit-scrollbar-track {
        background: #1a1b1e;
    }

    ::-webkit-scrollbar-thumb {
        background: #3a3b3f;
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: #4a4b50;
    }
    </style>
""", unsafe_allow_html=True)

class MonicaChat:
    def __init__(self):
        self.api_url = "https://monica.im/api/coder/llm_proxy/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "X-Api-Key": st.secrets["MONICA_API_KEY"],
            "X-Client-Id": st.secrets["MONICA_CLIENT_ID"],
            "X-Client-Type": "vscodeVisual Studio Code",
            "X-Client-Version": "1.3.14",
            "X-Product-Name": "monica-code",
            "X-Time-Zone": "UTC;0"
        }

    async def _process_stream(self, response: httpx.Response) -> AsyncGenerator[str, None]:
        async for line in response.aiter_lines():
            if line.startswith('data: '):
                data = line[6:]  # Remove 'data: ' prefix
                if data.strip() == '[DONE]':
                    break
                try:
                    json_data = json.loads(data)
                    if 'choices' in json_data and len(json_data['choices']) > 0:
                        delta = json_data['choices'][0].get('delta', {})
                        if 'content' in delta:
                            yield delta['content']
                except json.JSONDecodeError:
                    continue

    async def send_message(self, messages: List[Dict[str, str]], placeholder) -> str:
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg["role"],
                "content": [{
                    "type": "text",
                    "text": msg["content"]
                }]
            })
        
        payload = {
            "messages": formatted_messages,
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 8192,
            "temperature": 0.5,
            "stream": True,
        }

        full_response = ""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream('POST', self.api_url, json=payload, headers=self.headers) as response:
                    async for chunk in self._process_stream(response):
                        full_response += chunk
                        placeholder.markdown(full_response + "▌")
                    
                    # Final update without the cursor
                    placeholder.markdown(full_response)
                    
        except Exception as e:
            error_message = f"Error: {str(e)}"
            placeholder.error(error_message)
            return error_message

        return full_response

def init_session_state():
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'chat_interface' not in st.session_state:
        st.session_state.chat_interface = MonicaChat()
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'current_chat' not in st.session_state:
        st.session_state.current_chat = 0

def format_chat_title(messages):
    if messages:
        first_msg = messages[0]["content"]
        return first_msg[:30] + "..." if len(first_msg) > 30 else first_msg
    return "Empty Chat"

def main():
    init_session_state()

    # Sidebar for chat history
    with st.sidebar:
        st.title("Chat History")
        
        # New Chat button at the top
        if st.button("New Chat", key="new_chat"):
            st.session_state.messages = []
            st.session_state.current_chat = len(st.session_state.chat_history)
            st.experimental_rerun()

        # Display chat history
        for i, chat in enumerate(st.session_state.chat_history):
            chat_title = format_chat_title(chat)
            if st.button(f"💬 {chat_title}", key=f"chat_{i}"):
                st.session_state.messages = chat.copy()
                st.session_state.current_chat = i
                st.experimental_rerun()

    # Main chat interface
    col1, col2 = st.columns([2, 8])
    with col2:
        st.title("LIMIT●LESS")

        # Add padding at the bottom to prevent messages from being hidden
        st.markdown("<div style='padding-bottom: 100px;'></div>", unsafe_allow_html=True)

        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Chat input
        if prompt := st.chat_input("What would you like to know?"):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Add assistant message placeholder
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                
                # Get assistant response
                response = asyncio.run(st.session_state.chat_interface.send_message(
                    st.session_state.messages,
                    response_placeholder
                ))
                
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # Update chat history
                if st.session_state.current_chat < len(st.session_state.chat_history):
                    st.session_state.chat_history[st.session_state.current_chat] = st.session_state.messages.copy()
                else:
                    st.session_state.chat_history.append(st.session_state.messages.copy())

if __name__ == "__main__":
    main()
