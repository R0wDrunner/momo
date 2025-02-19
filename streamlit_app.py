import streamlit as st
import httpx
import asyncio
import json
import logging
from typing import List, Dict, Any, AsyncGenerator, Optional
from datetime import datetime
from contextlib import asynccontextmanager
from ratelimit import limits, sleep_and_retry

# Constants
API_TIMEOUT = 30.0
MAX_TOKENS = 8192
TEMPERATURE = 0.5
MODEL_NAME = "claude-3-5-sonnet-20241022"
CHAT_TITLE_MAX_LENGTH = 30
RATE_LIMIT_CALLS = 60
RATE_LIMIT_PERIOD = 60

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
PAGE_CONFIG = {
    "page_title": "LIMITLESS",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# Enhanced CSS with better UI styling
CUSTOM_CSS = """
    <style>
    /* Base theme */
    .stApp {
        background-color: #0f172a;
        color: #e2e8f0;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Main container */
    .main .block-container {
        padding-bottom: 100px;
        max-width: 800px;  /* Reduced from 1200px for a narrower layout */
        margin: 0 auto;
    }

    /* Chat messages container */
    .stChatMessageContent {
        background-color: #1e293b !important;
        border-radius: 16px !important;
        padding: 1.25rem;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }

    /* User message */
    [data-testid="stChatMessageContent"][class*="user"] {
        background-color: #312e81 !important;
        border: none;
    }

    /* Chat input container */
    .stChatInputContainer {
        position: fixed !important;
        bottom: 0 !important;
        left: 50%;
        transform: translateX(-50%) !important;
        width: min(400px, 80%) !important;  /* Narrower input field */
        background-color: rgba(15, 23, 42, 0.95) !important;
        padding: 1.5rem !important;
        z-index: 1000 !important;
        border-top: 1px solid #334155 !important;
        backdrop-filter: blur(12px);
        box-shadow: 0 -10px 15px -3px rgba(0, 0, 0, 0.1);
    }

    /* Chat input field */
    .stChatInput {
        background-color: #1e293b !important;
        border-radius: 12px !important;
        border: 2px solid #334155 !important;
        transition: all 0.2s ease;
    }

    .stChatInput textarea {
        background-color: #1e293b !important;
        color: #e2e8f0 !important;
        font-size: 0.95rem !important;
        padding: 12px !important;
    }

    .stChatInput textarea::placeholder {
        color: #64748b !important;
    }

    /* Chat input hover and focus states */
    .stChatInput:hover {
        border-color: #4f46e5 !important;
    }

    .stChatInput:focus-within {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2) !important;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #1e293b;
        border-right: 1px solid #334155;
    }

    /* Chat history buttons */
    .stButton button {
        width: 100%;
        text-align: left;
        background-color: #1e293b !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
        margin: 4px 0;
        padding: 12px;
        border-radius: 12px;
        transition: all 0.2s ease;
        font-size: 0.9rem;
    }

    .stButton button:hover {
        background-color: #2d3748 !important;
        border-color: #4f46e5 !important;
        transform: translateY(-1px);
    }

    /* Title styling */
    .title {
        font-size: 2.5rem;
        font-weight: 800;
        text-align: center;
        margin-bottom: 2rem;
        color: #e2e8f0;
        background: linear-gradient(45deg, #6366f1, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.5px;
    }

    /* Message timestamp styling */
    .message-timestamp {
        font-size: 0.75rem;
        color: #64748b;
        margin-top: 0.5rem;
    }

    /* Code block styling */
    pre {
        background-color: #1e293b !important;
        padding: 1rem !important;
        border-radius: 8px !important;
        border: 1px solid #334155 !important;
    }

    code {
        color: #e2e8f0 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* New Chat button styling */
    button[key="new_chat"] {
        background: linear-gradient(45deg, #6366f1, #8b5cf6) !important;
        color: white !important;
        border: none !important;
        padding: 12px 20px !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px !important;
        margin-bottom: 20px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 4px 6px -1px rgba(99, 102, 241, 0.2) !important;
    }

    button[key="new_chat"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 8px -1px rgba(99, 102, 241, 0.3) !important;
    }

    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
    }

    ::-webkit-scrollbar-track {
        background: #1e293b;
    }

    ::-webkit-scrollbar-thumb {
        background: #4f46e5;
        border-radius: 3px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: #6366f1;
    }

    /* Chat message animations */
    .stChatMessage {
        margin-bottom: 1.25rem !important;
        animation: slideIn 0.3s ease;
    }

    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    </style>
"""

class ChatError(Exception):
    """Custom exception for chat-related errors"""
    pass

class MonicaChat:
    def __init__(self):
        """Initialize the MonicaChat client with API configuration"""
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
        self._client: Optional[httpx.AsyncClient] = None

    @asynccontextmanager
    async def get_client(self):
        """Async context manager for HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=API_TIMEOUT)
        try:
            yield self._client
        finally:
            if self._client:
                await self._client.aclose()
                self._client = None

    async def _process_stream(self, response: httpx.Response) -> AsyncGenerator[str, None]:
        """Process streaming response from the API"""
        try:
            async for line in response.aiter_lines():
                if line.startswith('data: '):
                    data = line[6:]
                    if data.strip() == '[DONE]':
                        break
                    try:
                        json_data = json.loads(data)
                        if 'choices' in json_data and json_data['choices']:
                            delta = json_data['choices'][0].get('delta', {})
                            if 'content' in delta:
                                yield delta['content']
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error: {e}")
                        continue
        except Exception as e:
            logger.error(f"Stream processing error: {e}")
            raise ChatError(f"Stream processing failed: {str(e)}")

    @sleep_and_retry
    @limits(calls=RATE_LIMIT_CALLS, period=RATE_LIMIT_PERIOD)
    async def send_message(self, messages: List[Dict[str, str]], placeholder) -> str:
        """Send a message to the chat API with rate limiting"""
        formatted_messages = [
            {
                "role": msg["role"],
                "content": [{
                    "type": "text",
                    "text": msg["content"]
                }]
            }
            for msg in messages
        ]

        payload = {
            "messages": formatted_messages,
            "model": MODEL_NAME,
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "stream": True,
        }

        full_response = ""
        try:
            async with self.get_client() as client:
                async with client.stream('POST', self.api_url, json=payload, headers=self.headers) as response:
                    response.raise_for_status()
                    async for chunk in self._process_stream(response):
                        full_response += chunk
                        # Add typing indicator animation
                        placeholder.markdown(full_response + "▋", unsafe_allow_html=True)
                    placeholder.markdown(full_response, unsafe_allow_html=True)
        except Exception as e:
            logger.error(f"API request failed: {e}")
            error_message = f"Error: {str(e)}"
            placeholder.error(error_message)
            raise ChatError(error_message)

        return full_response

class SessionState:
    """Manage Streamlit session state"""
    @staticmethod
    def init():
        """Initialize session state variables"""
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        if 'chat_interface' not in st.session_state:
            st.session_state.chat_interface = MonicaChat()
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        if 'current_chat' not in st.session_state:
            st.session_state.current_chat = len(st.session_state.chat_history)

    @staticmethod
    def reset_chat():
        """Reset the current chat session"""
        st.session_state.messages = []
        st.session_state.current_chat = len(st.session_state.chat_history)

def format_chat_title(messages: List[Dict[str, str]]) -> str:
    """Format the chat title for display"""
    if not messages:
        return "Empty Chat"
    first_msg = messages[0]["content"]
    return f"{first_msg[:CHAT_TITLE_MAX_LENGTH]}..." if len(first_msg) > CHAT_TITLE_MAX_LENGTH else first_msg

def render_sidebar():
    """Render the sidebar with chat history"""
    with st.sidebar:
        st.markdown("<h1 style='text-align: center; color: #e0e0e0; margin-bottom: 30px;'>Chat History</h1>", unsafe_allow_html=True)

        # Styled New Chat button
        if st.button("✨ New Chat", key="new_chat"):
            SessionState.reset_chat()
            st.rerun()

        # Display chat history with enhanced styling
        for i, chat in enumerate(st.session_state.chat_history):
            chat_title = format_chat_title(chat)
            if st.button(f"💬 {chat_title}", key=f"chat_{i}"):
                st.session_state.messages = chat.copy()
                st.session_state.current_chat = i
                st.rerun()

def render_chat():
    """Render the main chat interface"""
    st.markdown("<h1 class='title'>LIMIT●LESS</h1>", unsafe_allow_html=True)

    # Display chat messages with timestamps
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            st.markdown(f"<div class='message-timestamp'>{datetime.now().strftime('%H:%M')}</div>", unsafe_allow_html=True)

def handle_user_input():
    """Handle user input and generate responses"""
    if prompt := st.chat_input("What would you like to know?", key="chat_input"):
        st.session_state.messages.append({"role": "user", "content": prompt})

        if len(st.session_state.messages) == 1:
            st.session_state.chat_history.append(st.session_state.messages.copy())
            st.session_state.current_chat = len(st.session_state.chat_history) - 1

        with st.chat_message("user"):
            st.markdown(prompt)
            st.markdown(f"<div class='message-timestamp'>{datetime.now().strftime('%H:%M')}</div>", unsafe_allow_html=True)

        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            try:
                response = asyncio.run(
                    st.session_state.chat_interface.send_message(
                        st.session_state.messages,
                        response_placeholder
                    )
                )
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.markdown(f"<div class='message-timestamp'>{datetime.now().strftime('%H:%M')}</div>", unsafe_allow_html=True)

                if st.session_state.current_chat < len(st.session_state.chat_history):
                    st.session_state.chat_history[st.session_state.current_chat] = (
                        st.session_state.messages.copy()
                    )
            except ChatError as e:
                logger.error(f"Chat error: {e}")
                st.error(f"An error occurred: {str(e)}")

def main():
    """Main application entry point"""
    try:
        st.set_page_config(**PAGE_CONFIG)
        st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

        SessionState.init()
        render_sidebar()
        render_chat()
        handle_user_input()
    except Exception as e:
        logger.error(f"Application error: {e}")
        st.error("An unexpected error occurred. Please try again later.")

if __name__ == "__main__":
    main()