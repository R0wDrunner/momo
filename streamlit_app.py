import streamlit as st
import httpx
import asyncio
import json
import logging
import traceback
from typing import List, Dict, Any, AsyncGenerator, Optional
from datetime import datetime
from contextlib import asynccontextmanager
from ratelimit import limits, sleep_and_retry

# Constants
API_TIMEOUT = 30.0
MAX_TOKENS = 150000
MODEL_NAME = "claude-3-7-sonnet-latest"
CHAT_TITLE_MAX_LENGTH = 30
RATE_LIMIT_CALLS = 60
RATE_LIMIT_PERIOD = 60

# Configure logging
logging.basicConfig(level=logging.DEBUG)  # Set to DEBUG for more detailed logs
logger = logging.getLogger(__name__)

# Page configuration
PAGE_CONFIG = {
    "page_title": "LIMITLESS",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# Keep your existing CUSTOM_CSS here...
# [Your existing CSS code remains unchanged]

class ChatError(Exception):
    """Custom exception for chat-related errors"""
    pass

async def streamSse(response):
    """Process SSE stream from response"""
    async for line in response.aiter_lines():
        if line.startswith('data: '):
            data = line[6:]
            if data.strip() == '[DONE]':
                break
            try:
                yield json.loads(data)
            except json.JSONDecodeError:
                continue

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

    @sleep_and_retry
    @limits(calls=RATE_LIMIT_CALLS, period=RATE_LIMIT_PERIOD)
    async def send_message(self, messages: List[Dict[str, str]], placeholder) -> Dict[str, str]:
        """Send a message to the chat API with rate limiting"""
        # Format messages to match the Monica extension format
        formatted_messages = []
        for msg in messages:
            content = msg["content"]
            if isinstance(content, dict):
                content = content.get("content", "")
            
            formatted_messages.append({
                "role": msg["role"],
                "content": content
            })

        logger.debug(f"Formatted messages: {formatted_messages}")

        payload = {
            "messages": formatted_messages,
            "model": MODEL_NAME,
            "max_tokens": MAX_TOKENS,
            "temperature": 0.7,
            "stream": True
        }

        logger.debug(f"Request payload: {payload}")
        logger.debug(f"Request headers: {self.headers}")

        full_response = {
            "content": "",
            "reasoning_content": "",
            "role": "assistant"
        }

        try:
            async with self.get_client() as client:
                async with client.stream('POST', self.api_url, json=payload, headers=self.headers) as response:
                    response.raise_for_status()
                    async for value in streamSse(response):
                        delta = value.get('choices', [{}])[0].get('delta', {})
                        
                        # Handle different types of content
                        if delta.get('role') == 'assistant':
                            if 'reasoning_content' in delta:
                                full_response['reasoning_content'] += delta['reasoning_content']
                            elif 'content' in delta:
                                full_response['content'] += delta['content']
                        elif 'content' in delta:
                            full_response['content'] += delta['content']
                        
                        # Update the display
                        display_text = full_response['content']
                        if full_response['reasoning_content']:
                            display_text += f"\n\n<div class='reasoning-content'><div class='reasoning-heading'>Reasoning:</div>{full_response['reasoning_content']}</div>"
                        
                        placeholder.markdown(display_text + "▋", unsafe_allow_html=True)
                    
                    # Final display without cursor
                    display_text = full_response['content']
                    if full_response['reasoning_content']:
                        display_text += f"\n\n<div class='reasoning-content'><div class='reasoning-heading'>Reasoning:</div>{full_response['reasoning_content']}</div>"
                    placeholder.markdown(display_text, unsafe_allow_html=True)

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
            logger.error(error_msg)
            logger.error(f"Response headers: {e.response.headers}")
            raise ChatError(error_msg)
        except httpx.RequestError as e:
            error_msg = f"Request error occurred: {str(e)}"
            logger.error(error_msg)
            raise ChatError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise ChatError(error_msg)

        return full_response

def handle_user_input():
    """Handle user input and generate responses"""
    if prompt := st.chat_input("What would you like to know?", key="chat_input"):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        if len(st.session_state.messages) == 1:
            st.session_state.chat_history.append(st.session_state.messages.copy())
            st.session_state.current_chat = len(st.session_state.chat_history) - 1

        with st.chat_message("user"):
            st.markdown(prompt)
            st.markdown(f"<div class='message-timestamp'>{datetime.now().strftime('%H:%M')}</div>", 
                       unsafe_allow_html=True)

        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            try:
                response = asyncio.run(
                    st.session_state.chat_interface.send_message(
                        st.session_state.messages,
                        response_placeholder
                    )
                )
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response
                })
                
                st.markdown(f"<div class='message-timestamp'>{datetime.now().strftime('%H:%M')}</div>", 
                          unsafe_allow_html=True)

                if st.session_state.current_chat < len(st.session_state.chat_history):
                    st.session_state.chat_history[st.session_state.current_chat] = (
                        st.session_state.messages.copy()
                    )
                    
            except ChatError as e:
                logger.error(f"Chat error: {e}")
                st.error(f"An error occurred: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error in handle_user_input: {str(e)}")
                st.error("An unexpected error occurred. Please try again.")

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
        st.markdown("<h1 style='text-align: center; color: #e0e0e0; margin-bottom: 30px;'>Chat History</h1>", 
                   unsafe_allow_html=True)

        if st.button("✨ New Chat", key="new_chat"):
            SessionState.reset_chat()
            st.rerun()

        for i, chat in enumerate(st.session_state.chat_history):
            chat_title = format_chat_title(chat)
            if st.button(f"💬 {chat_title}", key=f"chat_{i}"):
                st.session_state.messages = chat.copy()
                st.session_state.current_chat = i
                st.rerun()

def render_chat():
    """Render the main chat interface"""
    st.markdown("<h1 class='title'>LIMIT●LESS</h1>", unsafe_allow_html=True)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if isinstance(message["content"], dict):
                content = message["content"].get("content", "")
                reasoning = message["content"].get("reasoning_content", "")
                
                display_text = content
                if reasoning:
                    display_text += f"\n\n<div class='reasoning-content'><div class='reasoning-heading'>Reasoning:</div>{reasoning}</div>"
                st.markdown(display_text, unsafe_allow_html=True)
            else:
                st.markdown(message["content"])
            
            st.markdown(f"<div class='message-timestamp'>{datetime.now().strftime('%H:%M')}</div>", 
                       unsafe_allow_html=True)

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
    