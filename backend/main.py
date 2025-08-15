import sys
import os
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.search import search_router
# from backend.local_myllm import llm_router
from backend.gpt import gpt_router  # GPT-3.5 Turbo
from backend.recommend import recommend_router
from backend.image_processing import image_router
from backend.chain import chat_router

# 로깅
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="광운대학교 챗봇 API", version="1.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ngrok 및 로컬 테스트 지원
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 엔드포인트 등록
app.include_router(search_router, prefix="/api/search")
# app.include_router(llm_router, prefix="/api/llm")  # 기존 Ollama 기반 API (비활성화)
app.include_router(gpt_router, prefix="/api/chat")  # OpenAI GPT 기반 API
app.include_router(image_router, prefix="/api/image")
app.include_router(recommend_router, prefix="/api/recommend")
app.include_router(chat_router, prefix="/api/chat")

# 헬스 체크 API
@app.get("/api/health")
async def health_check():
    return {"status": "OK"}

# 프론트엔드 정적 파일 제공 (Next.js 정적 사이트)
app.mount("/", StaticFiles(directory="frontend/out", html=True), name="static")

# FastAPI 실행
if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 FastAPI 서버 시작...")
    uvicorn.run(app, host="0.0.0.0", port=20005, timeout_keep_alive=300, reload=True)
