import os
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import traceback
import re

from backend.config import OPENAI_API_KEY, DATASET_PATH
from backend.search import hybrid_search
from backend.chat_history import (
    load_chat_history, add_to_chat_history,
    load_previous_search_results, add_search_results_to_history
)


# FastAPI Router
gpt_router = APIRouter()

# OpenAI 클라이언트 준비
if not OPENAI_API_KEY:
    raise ValueError("OpenAI API 키가 설정되지 않았습니다.")
client = OpenAI(api_key=OPENAI_API_KEY)

# 데이터 불러오기
COURSE_DF = pd.read_csv(DATASET_PATH, encoding="utf-8-sig")
LECTURE_LIST = COURSE_DF["강의명"].dropna().unique().tolist()
PROFESSOR_LIST = COURSE_DF["교수명"].dropna().unique().tolist()


# 텍스트 전처리 및 포맷 함수
def clean_text_field(field):
    return field if pd.notna(field) else "정보 없음"

def format_course_info(course):
    return "\n".join([
        f"학과: {clean_text_field(course.get('학과'))}",
        f"강의명: {clean_text_field(course.get('강의명'))}",
        f"개설학기: {clean_text_field(course.get('개설학기'))}",
        f"교수명: {clean_text_field(course.get('교수명'))}",
        f"이수구분: {clean_text_field(course.get('이수구분'))}",
        f"학정번호: {clean_text_field(course.get('학정번호'))}",
        f"강의구성: {clean_text_field(course.get('강의구성'))}",
        f"강의시간: {clean_text_field(course.get('강의시간'))}",
        f"평점: {clean_text_field(course.get('평점'))}",
        f"과제: {clean_text_field(course.get('과제'))}",
        f"조모임: {clean_text_field(course.get('조모임'))}",
        f"성적: {clean_text_field(course.get('성적'))}",
        f"출결: {clean_text_field(course.get('출결'))}",
        f"시험: {clean_text_field(course.get('시험'))}",
        f"교과목 개요: {clean_text_field(course.get('교과목개요'))[:150]}..."
    ])

# 후속 질문 여부 판별 (어투 기반)
def is_follow_up_to_lecture(query: str) -> bool:
    patterns = [
        r"(이|그)?\s?(수업|강의|교수(님)?)", r"수업", r"강의", r"시험", r"과제",
        r"출결", r"평가", r"레포트", r"팀플", r"(난이도|어려운|쉬운|지루|재밌)",
        r"(어때|어떤가요|좋나요|괜찮나요|추천)", r"(많[아요]?|적[어요]?)",
        r"설명", r"말투", r"스타일", r"성향"
    ]
    return any(re.search(pattern, query, re.IGNORECASE) for pattern in patterns)

# chat_history 기반 마지막 질문/답변, 교수명/강의명
def get_last_turn():
    chat = load_chat_history()
    if not chat:
        return "", ""
    return chat[-1].get("user", ""), chat[-1].get("bot", "")

def get_last_lecture_name():
    chat = load_chat_history()
    for turn in reversed(chat):
        for lecture in LECTURE_LIST:
            if lecture in turn.get("user", ""):
                return lecture
    return None

def get_last_professor_name():
    chat = load_chat_history()
    for turn in reversed(chat):
        for prof in PROFESSOR_LIST:
            if prof in turn.get("user", ""):
                return prof
    return None

# 프롬프트 생성기
def build_prompt(context, query, mode, last_q="", last_a="", lecture="", professor=""):
    if mode == "professor_followup":
        return f"""
        당신은 광운대학교 전자공학과 강의 정보를 안내하는 친절한 챗봇입니다.
        사용자는 이전에 교수님 강의에 대해 질문했고, 이어지는 후속 질문을 하고 있습니다.
        
        [이전 사용자 질문]
        {last_q}
        
        [이전 챗봇 응답]
        {last_a}
        
        [현재 사용자 질문]
        {query}
        
        교수명: {professor}
        다음은 해당 교수가 담당하는 강의 목록입니다:
        {context}
        
        [응답 지침]
        - 위의 대화 흐름과 강의 정보를 바탕으로 자연스럽고 일관된 문장으로 후속 질문에 답변하세요.
        - 강의명, 과제, 출결, 시험, 평가 방식 등 핵심 정보를 빠짐없이 반영하세요.
        - 말투는 정중하고 따뜻하며, 문장은 간결하고 친근하게 유지하세요.
        """

    elif mode == "lecture_followup":
        return f"""
        당신은 광운대학교 전자공학과 강의 정보를 안내하는 챗봇입니다.
        사용자는 특정 강의에 대해 질문했고, 지금은 그 강의에 대한 후속 질문을 하고 있습니다.
        
        [이전 사용자 질문]
        {last_q}
        
        [이전 챗봇 응답]
        {last_a}
        
        [현재 사용자 질문]
        {query}
        
        📘 강의명: {lecture}
        해당 강의에 대한 상세 정보는 다음과 같습니다:
        {context}
        
        [응답 지침]
        - 위의 대화 흐름과 강의 정보를 참고해 자연스럽고 일관된 답변을 해주세요.
        - 강의 관련된 핵심 정보(교수명, 과제, 시험, 출결 등)를 모두 포함하세요.
        - 답변은 과도하게 길지 않게, 친절하고 쉽게 이해될 수 있도록 작성해주세요.
        """

    else:  # 일반 자연어 질문
        return f"""
        당신은 광운대학교 전자공학과 강의 정보를 안내하는 챗봇입니다.
        사용자는 자연어로 강의에 대한 질문을 했고, 관련 강의 정보를 검색한 결과가 아래에 있습니다.
        
        [사용자 질문]
        {query}
        
        [검색된 강의 정보]
        {context}
        
        [응답 지침]
        - 질문과 관련되지 않은 강의가 검색된 경우 배제해주세요.
        - 사용자의 질문 의도를 파악한 후, 관련된 강의 정보를 자연스러운 자연어 문장으로 정리해 답변하세요.
        - 강의명, 교수명, 이수구분, 평점, 과제, 출결 방식, 시험 횟수, 교과목 개요 등 주요 정보를 자연스러운 문장으로 요약해주세요.
        - 여러 강의가 검색된 경우, 공통점과 차이점을 자연스럽게 언급해 주세요.
        - 검색된 모든 강의 정보를 고려하세요.
        - 항상 정중하고 따뜻한 말투로, 친절하고 부드럽게 안내해주세요.
        """

# GPT 응답 생성
def generate_answer(query: str):
    try:
        last_q, last_a = get_last_turn()
        last_lecture = get_last_lecture_name()
        last_professor = get_last_professor_name()

        if is_follow_up_to_lecture(query) and (last_lecture or last_professor):
            if last_professor:
                matched = load_previous_search_results()
                context = "\n\n".join(format_course_info(c) for c in matched)
                prompt = build_prompt(context, query, mode="professor_followup", last_q=last_q, last_a=last_a, professor=last_professor)
            else:
                matched = load_previous_search_results()
                context = "\n\n".join(format_course_info(c) for c in matched)
                prompt = build_prompt(context, query, mode="lecture_followup", last_q=last_q, last_a=last_a, lecture=last_lecture)
        else:
            matched = hybrid_search(query)
            context = "\n\n".join(format_course_info(c) for c in matched)
            prompt = build_prompt(context, query, mode="default")
            add_search_results_to_history(query, matched)

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "너는 광운대학교 전자공학과 강의 추천 챗봇이야."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        answer = response.choices[0].message.content.strip()
        add_to_chat_history(query, answer)
        return answer

    except Exception as e:
        traceback.print_exc()
        return f"GPT 응답 생성 중 오류: {e}"

# FastAPI endpoint
class Query(BaseModel):
    query: str

@gpt_router.post("/")
async def chat(query: Query):
    try:
        return {"response": generate_answer(query.query)}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")
