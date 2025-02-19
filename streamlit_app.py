import streamlit as st
import httpx
from datetime import datetime
from typing import List, Dict, Any
import asyncio

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversations" not in st.session_state:
    st.session_state.conversations = {}
if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = None

class MonicaChat:
    def __init__(self):
        self.api_url = "https://monica.im/api/coder/llm_proxy/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "X-Api-Key": st.secrets["MONICA_API_KEY"],
            "X-Client-Id": st.secrets["MONICA_CLIENT_ID"],
            "X-Client-Type": "streamlit",
            "X-Time-Zone": "UTC;0"
        }
    
    async def send_message(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        payload = {
            "messages": messages,
            "model": "claude-3-sonnet-20240229",  # Updated model name
            "max_tokens": 8192,
            "temperature": 0.7,
            "stream": False
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:  # Added timeout
                # Debug prints
                st.write("Sending request with payload:", payload)
                st.write("Headers:", {k: v for k, v in self.headers.items() if k != 'X-Api-Key'})
                
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=self.headers
                )
                
                # Debug response
                st.write("Response status:", response.status_code)
                
                try:
                    response_data = response.json()
                    st.write("Response data:", response_data)
                    return response_data
                except json.JSONDecodeError:
                    st.error(f"Invalid JSON response. Raw response: {response.text}")
                    return {"error": "Invalid JSON response from API"}
                
        except httpx.TimeoutException:
            st.error("Request timed out")
            return {"error": "Request timed out"}
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return {"error": str(e)}

def initialize_session():
    """Initialize or reset session state"""
    if 'user_id' not in st.session_state:
        st.session_state.user_id = datetime.now().strftime("%Y%m%d%H%M%S")
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = {}

def main():
    st.title("💬 Monica AI Chat")
    initialize_session()
    
    # Sidebar for conversation management
    with st.sidebar:
        st.title("📚 Conversations")
        
        # New chat button
        if st.button("➕ New Chat"):
            new_id = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.session_state.conversations[new_id] = []
            st.session_state.current_conversation_id = new_id
            st.rerun()  # Updated from experimental_rerun
        
        st.divider()
        
        # List existing conversations
        for conv_id in st.session_state.conversations:
            # Get first message or use default title
            title = "New Chat" if not st.session_state.conversations[conv_id] else \
                   st.session_state.conversations[conv_id][0]['content'][:30] + "..."
            
            if st.button(f"💭 {title}", key=conv_id):
                st.session_state.current_conversation_id = conv_id
                st.rerun()  # Updated from experimental_rerun
    
    # Main chat interface
    if st.session_state.current_conversation_id:
        chat_interface = MonicaChat()
        
        # Display chat history
        for message in st.session_state.conversations[st.session_state.current_conversation_id]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input("Type your message here..."):
            # Add user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            user_message = {"role": "user", "content": prompt}
            st.session_state.conversations[st.session_state.current_conversation_id].append(user_message)
            
            # Get response from API
            with st.spinner("Thinking..."):
                response = asyncio.run(chat_interface.send_message(
                    st.session_state.conversations[st.session_state.current_conversation_id]
                ))
            
            # Handle API response
            if response and "error" not in response:
                assistant_message = {
                    "role": "assistant",
                    "content": response.get("choices", [{}])[0].get("message", {}).get("content", "Sorry, I couldn't process that.")
                }
                st.session_state.conversations[st.session_state.current_conversation_id].append(assistant_message)
                
                with st.chat_message("assistant"):
                    st.markdown(assistant_message["content"])
    else:
        st.info("👈 Create a new chat or select an existing one from the sidebar")

if __name__ == "__main__":
    main()