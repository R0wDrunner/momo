import streamlit as st
import httpx
import asyncio
import json
from typing import List, Dict, Any, AsyncGenerator
from datetime import datetime

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
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "builtin_read_file",
                        "description": "Use this tool whenever you need to view the contents of a file.",
                        "parameters": {
                            "type": "object",
                            "required": ["filepath"],
                            "properties": {
                                "filepath": {
                                    "type": "string",
                                    "description": "The path of the file to read, relative to the root of the workspace."
                                }
                            }
                        }
                    }
                }
            ]
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

def main():
    st.title("Monica Chat Interface")
    init_session_state()

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

if __name__ == "__main__":
    main()
