from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import traceback  # 에러 디버깅용

from backend.chat_history import (
    load_chat_history,
    add_to_chat_history,
    reset_chat_history,
    load_previous_search_results
)
from backend.gpt import generate_answer, LECTURE_LIST  # GPT 기반 LLM 사용

chat_router = APIRouter()

# 요청 데이터 모델
class Query(BaseModel):
    query: str

# 강의명이 직접 포함되어 있는지 확인
def contains_direct_course_name(query: str):
    for name in LECTURE_LIST:
        if name and name.strip() in query:
            return True
    return False

# 이전 검색 결과에서 강의명, 교수명 키워드 추출
def extract_keywords_from_results(previous_results: list):
    keywords = []
    for result in previous_results:
        if "강의명" in result:
            keywords.append(result["강의명"])
        if "교수명" in result:
            keywords.append(result["교수명"])
    return keywords

# 현재 질문이 이전 검색과 관련 있는지 확인
def is_related_to_previous_results(query: str, previous_results: list):
    related_terms = extract_keywords_from_results(previous_results)
    for term in related_terms:
        if term and term.strip() in query:
            return True
    return False

# 후속 질문 여부 판단
def is_followup_question(query: str):
    previous_results = load_previous_search_results()
    if not previous_results:
        return False  # 🔹 검색 기록 없음
    if contains_direct_course_name(query):
        return False  # 🔹 강의명이 직접 포함된 경우 → 새로운 검색
    if is_related_to_previous_results(query, previous_results):
        return True   # 🔹 이전 검색과 관련된 후속 질문
    return False      # 🔹 기본적으로는 새로운 질문으로 간주

# 메인 채팅 API
@chat_router.post("/", response_model=dict)
async def chat(query: Query):
    try:
        user_query = query.query

        # 후속 질문 여부 판단
        if is_followup_question(user_query):
            previous_results = load_previous_search_results()
            bot_response = generate_answer(user_query, previous_results)
        else:
            bot_response = generate_answer(user_query, [])

        # 대화 기록 저장
        add_to_chat_history(user_query, bot_response)

        # 최신 대화 기록을 반영하여 응답
        updated_chat_history = load_chat_history()
        return {"response": bot_response, "chat_history": updated_chat_history}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

# 대화 초기화 API
@chat_router.post("/reset_chat")
async def reset_chat():
    reset_chat_history()
    return {"message": "대화 기록 및 검색 결과가 초기화되었습니다."}
