from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import List
import httpx
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Move sensitive configs to environment variables
MONICA_API_URL = os.getenv("MONICA_API_URL", "https://monica.im/api/coder/llm_proxy/chat/completions")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "claude-3-5-sonnet-20241022")

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    model: str = DEFAULT_MODEL
    max_tokens: int = 8192
    temperature: float = 0.5
    stream: bool = False

async def get_api_key():
    api_key = os.getenv("MONICA_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="API key not configured")
    return api_key

@app.post("/chat")
async def chat(
    request: ChatRequest,
    api_key: str = Depends(get_api_key)
):
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key,
        "X-Client-Id": os.getenv("MONICA_CLIENT_ID"),
        "X-Client-Type": "streamlit",
        "X-Time-Zone": "UTC;0"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                MONICA_API_URL,
                json=request.dict(),
                headers=headers
            )
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
