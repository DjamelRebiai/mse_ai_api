from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import os

app = FastAPI(title="ChatGPT API Bridge")

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    model: Optional[str] = "gpt-4o-mini"

@app.get("/")
def root():
    return {"status": "running", "message": "Custom ChatGPT API is active!"}

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    """نقطة النهاية المتوافقة مع OpenAI"""
    # استخرج آخر رسالة من المستخدم
    last_user_message = next((m.content for m in reversed(request.messages) if m.role == "user"), None)
    
    if not last_user_message:
        raise HTTPException(status_code=400, detail="No user message found")
    
    # هنا سيتم الاتصال بـ ChatGPT لاحقاً. حالياً، نعيد رداً تجريبياً.
    fake_response = f"مرحباً! لقد استلمت رسالتك: '{last_user_message}'. هذه واجهة API تعمل بنجاح!"
    
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 12345,
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": fake_response},
            "finish_reason": "stop"
        }]
    }

@app.get("/health")
def health():
    return {"status": "ok"}

# للتشغيل المحلي
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
