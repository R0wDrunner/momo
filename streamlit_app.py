import streamlit as st
import requests
from datetime import datetime
import os
import json

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversations" not in st.session_state:
    st.session_state.conversations = {}
if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = None

class ChatInterface:
    def __init__(self):
        # Get API URL from Streamlit secrets or environment
        self.api_url = st.secrets.get("API_URL", "http://localhost:8000/chat")
        
    def send_message(self, messages):
        try:
            payload = {
                "messages": messages,
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 8192,
                "temperature": 0.5,
                "stream": False
            }
            
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            st.error(f"Error communicating with API: {str(e)}")
            return None

def initialize_session():
    """Initialize or reset session state"""
    if 'user_id' not in st.session_state:
        st.session_state.user_id = datetime.now().strftime("%Y%m%d%H%M%S")
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = {}

def main():
    st.title("💬 AI Chat Interface")
    initialize_session()
    
    # Sidebar for conversation management
    with st.sidebar:
        st.title("📚 Conversations")
        
        # New chat button
        if st.button("➕ New Chat"):
            new_id = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.session_state.conversations[new_id] = []
            st.session_state.current_conversation_id = new_id
            st.experimental_rerun()
        
        st.divider()
        
        # List existing conversations
        for conv_id in st.session_state.conversations:
            # Get first message or use default title
            title = "New Chat" if not st.session_state.conversations[conv_id] else \
                   st.session_state.conversations[conv_id][0]['content'][:30] + "..."
            
            if st.button(f"💭 {title}", key=conv_id):
                st.session_state.current_conversation_id = conv_id
                st.experimental_rerun()
    
    # Main chat interface
    if st.session_state.current_conversation_id:
        chat_interface = ChatInterface()
        
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
                current_messages = st.session_state.conversations[st.session_state.current_conversation_id]
                response = chat_interface.send_message(current_messages)
            
            # Handle API response
            if response:
                assistant_message = {"role": "assistant", "content": response.get("content", "Sorry, I couldn't process that.")}
                st.session_state.conversations[st.session_state.current_conversation_id].append(assistant_message)
                
                with st.chat_message("assistant"):
                    st.markdown(assistant_message["content"])
    else:
        st.info("👈 Create a new chat or select an existing one from the sidebar")

if __name__ == "__main__":
    main()
