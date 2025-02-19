import streamlit as st
import httpx
import json
from datetime import datetime
from typing import List, Dict, Any
import asyncio

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
        # Format messages properly
        formatted_messages = [
            {
                "role": msg["role"],
                "content": msg["content"]
            } for msg in messages
        ]
        
        payload = {
            "messages": formatted_messages,
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 4096,
            "temperature": 0.7,
            "stream": False
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Debug request
                st.write("Full request URL:", self.api_url)
                st.write("Full payload:", json.dumps(payload, indent=2))
                
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=self.headers
                )
                
                st.write("Response status:", response.status_code)
                st.write("Response headers:", dict(response.headers))
                st.write("Raw response text:", response.text)
                
                if not response.text:
                    return {
                        "error": "Empty response from API",
                        "choices": [{
                            "message": {
                                "content": "I apologize, but I received an empty response from the API. Please try again."
                            }
                        }]
                    }
                
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {
                        "error": "Invalid JSON response",
                        "choices": [{
                            "message": {
                                "content": "I apologize, but I received an invalid response. Please try again."
                            }
                        }]
                    }
                
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return {
                "error": str(e),
                "choices": [{
                    "message": {
                        "content": f"An error occurred: {str(e)}"
                    }
                }]
            }

def main():
    st.title("💬 Monica AI Chat")
    
    # Initialize session state if needed
    if "conversations" not in st.session_state:
        st.session_state.conversations = {}
    if "current_conversation_id" not in st.session_state:
        st.session_state.current_conversation_id = None
    
    # Sidebar for conversation management
    with st.sidebar:
        st.title("📚 Conversations")
        
        # New chat button
        if st.button("➕ New Chat"):
            new_id = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.session_state.conversations[new_id] = []
            st.session_state.current_conversation_id = new_id
            st.rerun()
        
        st.divider()
        
        # List existing conversations
        for conv_id in st.session_state.conversations:
            title = "New Chat" if not st.session_state.conversations[conv_id] else \
                   st.session_state.conversations[conv_id][0]['content'][:30] + "..."
            
            if st.button(f"💭 {title}", key=conv_id):
                st.session_state.current_conversation_id = conv_id
                st.rerun()
    
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
            if "error" not in response:
                assistant_message = {
                    "role": "assistant",
                    "content": response.get("choices", [{}])[0].get("message", {}).get("content", "Sorry, I couldn't process that.")
                }
                st.session_state.conversations[st.session_state.current_conversation_id].append(assistant_message)
                
                with st.chat_message("assistant"):
                    st.markdown(assistant_message["content"])
            else:
                with st.chat_message("assistant"):
                    st.error(f"Error: {response.get('error', 'Unknown error')}")
    else:
        st.info("👈 Create a new chat or select an existing one from the sidebar")

if __name__ == "__main__":
    main()
