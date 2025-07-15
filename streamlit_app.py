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
MAX_TOKENS = 32000
# MODEL_NAME = "claude-3-7-sonnet-latest-thinking"
# MODEL_NAME = "claude-4-sonnet"
MODEL_NAME = "claude-sonnet-4-20250514-thinking"
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
        background-color: #0e1117;
        color: #e0e0e0;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Main container */
    .main .block-container {
        padding-bottom: 100px;
        max-width: 1200px;
        margin: 0 auto;
    }

    /* Chat messages container */
    .stChatMessageContent {
        background-color: #1a1f2c !important;
        border-radius: 12px !important;
        padding: 15px;
        border: 1px solid #2d3544;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    }

    /* User message */
    [data-testid="stChatMessageContent"][class*="user"] {
        background-color: #2d3544 !important;
        border: 1px solid #3a4556;
    }

    /* Chat input container */
    .stChatInputContainer {
        position: fixed !important;
        bottom: 0 !important;
        left: 50%;
        transform: translateX(-50%) !important;
        width: min(30%, 400px) !important; /* Added max-width limit */
        background-color: rgba(14, 17, 23, 0.95) !important;
        padding: 20px !important;
        z-index: 1000 !important;
        border-top: 1px solid #2d3544 !important;
        backdrop-filter: blur(10px);
        box-shadow: 0 -4px 12px rgba(0,0,0,0.1);
    }

    /* Adjust width when sidebar is collapsed */
    [data-testid="stSidebar"][aria-expanded="false"] ~ .main .stChatInputContainer {
        width: min(80%, 1000px) !important;
    }

    /* Chat input field */
    .stChatInput {
        background-color: #1a1f2c !important;
        border-radius: 12px !important;
        border: 2px solid #2d3544 !important;
        transition: all 0.3s ease;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    /* Target the actual input element */
    .stChatInput textarea {
        background-color: #1a1f2c !important;
        color: #e0e0e0 !important;
    }

    /* Placeholder color */
    .stChatInput textarea::placeholder {
        color: #6b7280 !important;
    }

    /* Chat input hover state */
    .stChatInput:hover {
        border-color: #3a4556 !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }

    /* Chat input focus state */
    .stChatInput:focus {
        border-color: #4a5567 !important;
        box-shadow: 0 0 0 2px rgba(74, 85, 103, 0.2) !important;
    }

    /* Chat input field wrapper */
    .stChatInputContainer > div {
        border-radius: 12px !important;
    }

    /* Fix for red border radius */
    .stChatInput > div > div {
        border-radius: 12px !important;
    }

    .stChatInput > div {
        border-radius: 12px !important;
    }

    /* Additional fix for red border */
    .stChatInput div[data-baseweb="input"] {
        border-radius: 12px !important;
    }

    /* Sidebar styling */
    .css-1d391kg {
        background-color: #1a1f2c;
    }

    /* Chat history buttons */
    .stButton button {
        width: 100%;
        text-align: left;
        background-color: #1a1f2c !important;
        color: #e0e0e0 !important;
        border: 1px solid #2d3544 !important;
        margin: 5px 0;
        padding: 12px;
        border-radius: 8px;
        transition: all 0.3s ease;
        font-size: 0.95em;
    }

    .stButton button:hover {
        background-color: #2d3544 !important;
        border-color: #3a4556 !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    /* Title styling */
    .title {
        font-size: 2.8em;
        font-weight: 700;
        text-align: center;
        margin-bottom: 40px;
        color: #e0e0e0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.2);
        letter-spacing: 1px;
    }

    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
    }

    ::-webkit-scrollbar-track {
        background: #0e1117;
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb {
        background: #2d3544;
        border-radius: 4px;
        transition: all 0.3s ease;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: #3a4556;
    }

    /* Chat message spacing */
    .stChatMessage {
        margin-bottom: 1.5rem !important;
        border-radius: 12px !important;
        animation: fadeIn 0.3s ease;
    }

    /* Chat container scroll area */
    [data-testid="stChatMessageContainer"] {
        overflow-y: auto !important;
        max-height: calc(100vh - 200px) !important;
        padding: 2rem !important;
        padding-bottom: 120px !important;
    }

    /* Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* New Chat button styling */
    button[key="new_chat"] {
        background-color: #2d3544 !important;
        color: #e0e0e0 !important;
        border: none !important;
        padding: 12px 20px !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px !important;
        margin-bottom: 20px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1) !important;
    }

    button[key="new_chat"]:hover {
        background-color: #3a4556 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
    }

    /* Sidebar title styling */
    .sidebar .element-container:first-child {
        background-color: #1a1f2c;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    /* Message timestamp styling */
    .message-timestamp {
        font-size: 0.8em;
        color: #6b7280;
        margin-top: 5px;
    }

    /* Code block styling */
    pre {
        background-color: #1a1f2c !important;
        padding: 15px !important;
        border-radius: 8px !important;
        border: 1px solid #2d3544 !important;
        overflow-x: auto !important;
    }

    code {
        color: #e0e0e0 !important;
        font-family: 'Fira Code', monospace !important;
    }

    /* Link styling */
    a {
        color: #60a5fa !important;
        text-decoration: none !important;
        transition: all 0.3s ease !important;
    }

    a:hover {
        color: #93c5fd !important;
        text-decoration: underline !important;
    }

    /* Reasoning content styling */
    .reasoning-content {
        background-color: #1c2334;
        border-left: 3px solid #60a5fa;
        padding: 10px 15px;
        margin-top: 15px;
        border-radius: 6px;
        font-style: italic;
        color: #a9b2c3;
        font-size: 0.95em;
    }

    .reasoning-heading {
        font-weight: 600;
        color: #60a5fa;
        margin-bottom: 5px;
        font-size: 0.9em;
        text-transform: uppercase;
        letter-spacing: 0.5px;
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
            "X-Client-Version": "1.3.156",
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

    async def _process_stream(self, response: httpx.Response) -> AsyncGenerator[Dict[str, str], None]:
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
                            result = {}
                            
                            if 'content' in delta:
                                result['content'] = delta['content']
                            
                            if 'reasoning_content' in delta:
                                result['reasoning_content'] = delta['reasoning_content']
                            
                            if result:  # Only yield if we have content
                                yield result
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error: {e}")
                        continue
        except Exception as e:
            logger.error(f"Stream processing error: {e}")
            raise ChatError(f"Stream processing failed: {str(e)}")

    @sleep_and_retry
    @limits(calls=RATE_LIMIT_CALLS, period=RATE_LIMIT_PERIOD)
    async def send_message(self, messages: List[Dict[str, str]], placeholder) -> Dict[str, str]:
        """Send a message to the chat API with rate limiting"""
        # Fix the message formatting for API request
        formatted_messages = []
        for msg in messages:
            # Extract the content properly based on message structure
            content_text = ""
            if msg["role"] == "assistant" and isinstance(msg["content"], dict):
                # If it's an assistant message with a dict content
                content_text = msg["content"].get("content", "")
            else:
                # For user messages or simple string content
                content_text = msg["content"]
                
            formatted_messages.append({
                "role": msg["role"],
                "content": [{
                    "type": "text",
                    "text": content_text
                }]
            })

        # Set temperature based on model
        temperature = 1.0 #if MODEL_NAME == "claude-3-7-sonnet-latest-thinking" else 0.5

        payload = {
            "messages": formatted_messages,
            "model": MODEL_NAME,
            "max_tokens": MAX_TOKENS,
            "temperature": temperature,
            "stream": True
        }

        full_response = {"content": "", "reasoning_content": ""}
        try:
            async with self.get_client() as client:
                async with client.stream('POST', self.api_url, json=payload, headers=self.headers) as response:
                    response.raise_for_status()
                    async for chunk in self._process_stream(response):
                        if 'content' in chunk:
                            full_response['content'] += chunk['content']
                        if 'reasoning_content' in chunk:
                            full_response['reasoning_content'] += chunk['reasoning_content']
                        
                        # Update placeholder with content and reasoning_content
                        display_text = full_response['content']
                        if full_response['reasoning_content']:
                            display_text += f"\n\n<div class='reasoning-content'><div class='reasoning-heading'>Reasoning:</div>{full_response['reasoning_content']}</div>"
                        
                        placeholder.markdown(display_text + "▋", unsafe_allow_html=True)
                    
                    # Final display without cursor
                    display_text = full_response['content']
                    if full_response['reasoning_content']:
                        display_text += f"\n\n<div class='reasoning-content'><div class='reasoning-heading'>Reasoning:</div>{full_response['reasoning_content']}</div>"
                    placeholder.markdown(display_text, unsafe_allow_html=True)
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
    if isinstance(first_msg, dict):
        first_msg = first_msg.get("content", "")
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
            if isinstance(message["content"], dict) and "content" in message["content"] and "reasoning_content" in message["content"]:
                content = message["content"]["content"]
                reasoning = message["content"]["reasoning_content"]
                
                display_text = content
                if reasoning:
                    display_text += f"\n\n<div class='reasoning-content'><div class='reasoning-heading'>Reasoning:</div>{reasoning}</div>"
                st.markdown(display_text, unsafe_allow_html=True)
            else:
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