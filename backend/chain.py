import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import APIRouter
from backend.chat import chat_router  # `chat.py`에서 이미 등록된 라우터 사용

chain_router = APIRouter()
chain_router.include_router(chat_router)  # `chat_router`를 `chain_router`에 포함
