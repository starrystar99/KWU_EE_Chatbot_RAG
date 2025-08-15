import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import ollama
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import re

from backend.search import hybrid_search
from backend.chat_history import (
    load_chat_history, add_to_chat_history,
    add_search_results_to_history, load_previous_search_results
)
from backend.config import DATASET_PATH

llm_router = APIRouter()

# 초기 데이터 로딩
COURSE_DF = pd.read_csv(DATASET_PATH, encoding="utf-8-sig")
LECTURE_LIST = COURSE_DF["강의명"].dropna().unique().tolist()
PROFESSOR_LIST = COURSE_DF["교수명"].dropna().unique().tolist()

# 헬퍼 함수
def clean_text_field(field):
    return field if pd.notna(field) else "정보 없음"

def format_course_info(course):
    return "\n".join([
        f"강의명: {clean_text_field(course.get('강의명'))}",
        f"교수명: {clean_text_field(course.get('교수명'))}",
        f"이수구분: {clean_text_field(course.get('이수구분'))}",
        f"평점: {clean_text_field(course.get('평점'))}",
        f"과제: {clean_text_field(course.get('과제'))}",
        f"출결: {clean_text_field(course.get('출결'))}",
        f"시험: {clean_text_field(course.get('시험'))}",
        f"개요: {clean_text_field(course.get('교과목개요'))[:150]}..."
    ])

def is_follow_up_to_lecture(query: str) -> bool:
    patterns = [
        r"(이|그)?\s?(수업|강의|교수(님)?)",
        r"수업", r"강의", r"시험", r"과제", r"출결", r"평가", r"레포트", r"팀플",
        r"(난이도|어려운|쉬운|지루|재밌)",
        r"(어때|어떤가요|좋나요|괜찮나요|추천)",
        r"(많[아요]?|적[어요]?)",
        r"설명", r"말투", r"스타일", r"성향"
    ]
    return any(re.search(pattern, query, re.IGNORECASE) for pattern in patterns)

def get_last_lecture_name_from_chat():
    chat = load_chat_history()
    if not chat:
        return None
    for turn in reversed(chat):
        user_input = turn.get("user", "")
        for lecture in LECTURE_LIST:
            if lecture in user_input:
                return lecture
    return None

def get_last_professor_name_from_chat():
    chat = load_chat_history()
    if not chat:
        return None
    for turn in reversed(chat):
        user_input = turn.get("user", "")
        for professor in PROFESSOR_LIST:
            if professor in user_input:
                return professor
    return None

# 핵심 함수: 답변 생성
def generate_answer(query, previous_results=[]):
    try:
        # 1. 정확한 강의명 직접 검색
        if query in LECTURE_LIST:
            related_courses = COURSE_DF[COURSE_DF['강의명'] == query].to_dict(orient="records")
            if not related_courses:
                return f"❌ '{query}' 과목의 정보를 찾을 수 없습니다."
            response_lines = [f"'{query}' 강의에 대한 정보입니다:"]
            for course in related_courses:
                response_lines.append(format_course_info(course) + "\n")
            add_search_results_to_history(query, related_courses)
            return "\n".join(response_lines)

        # 2. 교수명 포함 검색
        professor_names_in_query = [prof for prof in PROFESSOR_LIST if prof in query]
        if professor_names_in_query:
            professor_name = professor_names_in_query[0]
            related_courses = COURSE_DF[COURSE_DF['교수명'] == professor_name].to_dict(orient="records")
            descriptions = [format_course_info(c) for c in related_courses]
            prompt = f"""
            당신은 광운대학교 전자공학과 강의 추천 챗봇입니다.
            
            사용자가 다음 질문을 했습니다: '{query}'  
            검색된 교수명: {professor_name}
            
            해당 교수가 담당하는 강의는 다음과 같습니다:
            {chr(10).join(descriptions)}
            
            [요청사항]
            - 질문에서 사용자의 질문의도를 파악한 후 관련 정보를 중심으로 답변하세요.
            - 강의에 대한 정보(강의명, 이수구분, 평점, 과제, 출결 방법, 시험 횟수)를 자연어로 요약하여 친절하게 설명해주세요.
            - 강의개요도 요약하여 설명해주세요.
            - 제공된 정보 외 내용은 추측하지 말아주세요.
            - 답변은 자연스럽고 간결하게 제공해주세요.
            """
            response = ollama.chat(model='eeve-korean:latest', messages=[
                {"role": "system", "content": "너는 광운대학교 전자공학과 강의 추천 챗봇이야."},
                {"role": "user", "content": prompt}
            ])
            return response["message"]["content"].strip()

        # 3. 후속 질문 (교수 기반)
        if is_follow_up_to_lecture(query):
            professor_name = get_last_professor_name_from_chat()
            if professor_name:
                related_courses = COURSE_DF[COURSE_DF['교수명'] == professor_name].to_dict(orient="records")
                chat_log = load_chat_history()
                last_q = chat_log[-1].get("user", "없음") if chat_log else ""
                last_a = chat_log[-1].get("bot", "없음") if chat_log else ""

                descriptions = [format_course_info(c) for c in related_courses]
                prompt = f"""
                당신은 대학 강의 정보를 안내하는 챗봇입니다.
                사용자는 교수님의 강의에 대해 질문했고 후속 질문을 이어가고 있습니다.
                
                [이전 질문] {last_q}
                [이전 응답] {last_a}
                [현재 질문] {query}
                
                교수명: {professor_name}
                강의 목록:
                {chr(10).join(descriptions)}
                
                [답변 작성 가이드라인]
                - 위의 대화 흐름과 강의 정보를 바탕으로 후속 질문에 자연스럽게 응답해 주세요.
                - 친절하고 섬세히 알려주세요.
                - 답변은 너무 길지 않게, 자연스럽게 작성해 주세요.
                """
                response = ollama.chat(model='eeve-korean:latest', messages=[
                    {"role": "system", "content": "너는 광운대학교 전자공학과 강의 추천 챗봇이야."},
                    {"role": "user", "content": prompt}
                ])
                return response["message"]["content"].strip()

        # 4. 후속 질문 (강의 기반)
        if is_follow_up_to_lecture(query):
            last_lecture = get_last_lecture_name_from_chat()
            if last_lecture:
                related_courses = COURSE_DF[COURSE_DF['강의명'] == last_lecture].to_dict(orient="records")
                chat_log = load_chat_history()
                last_q = chat_log[-1].get("user", "없음") if chat_log else ""
                last_a = chat_log[-1].get("bot", "없음") if chat_log else ""

                descriptions = [format_course_info(c) for c in related_courses]
                prompt = f"""
                당신은 대학 강의 정보를 안내하는 챗봇입니다.
                사용자는 '{last_lecture}'에 대해 질문했고, 후속 질문을 하고 있습니다.
                
                [이전 질문] {last_q}
                [이전 응답] {last_a}
                [현재 질문] {query}
                
                해당 강의 정보:
                {chr(10).join(descriptions)}
                
                [답변 작성 가이드라인]
                - 위의 대화 흐름과 강의 정보를 바탕으로 후속 질문에 자연스럽게 응답해 주세요.
                - 친절하고 섬세히 알려주세요.
                - 답변은 너무 길지 않게, 자연스럽게 작성해 주세요.
                """
                response = ollama.chat(model='eeve-korean:latest', messages=[
                    {"role": "system", "content": "너는 광운대학교 전자공학과 강의 추천 챗봇이야."},
                    {"role": "user", "content": prompt}
                ])
                return response["message"]["content"].strip()

        # 5. 일반 자연어 검색 (hybrid_search)
        search_results = hybrid_search(query)
        retrieved_docs = [doc for doc in search_results if doc.get("점수", 0) >= 0.5]
        if not retrieved_docs:
            return "❌ 검색된 강의 중 유사도가 충분한 결과가 없습니다."

        add_search_results_to_history(query, retrieved_docs)
        descriptions = [format_course_info(doc) for doc in retrieved_docs]
        prompt = f"""
        당신은 대학 강의 정보를 안내하는 챗봇입니다.
        사용자는 다음과 같은 질문을 했습니다: '{query}'
        
        검색된 강의 정보:
        {chr(10).join(descriptions)}
        
        [답변 작성 가이드라인]
        - 질문과 관련되지 않은 강의가 검색된 경우 배제해주세요.
        - 질문에서 사용자의 질문의도를 파악한 후 관련 정보를 중심으로 답변하세요.
        - 강의에 대한 정보(강의명, 이수구분, 평점, 과제, 출결 방법, 시험 횟수)를 자연스러운 문장으로 요약하여 친절하게 설명해주세요.
        - 검색된 강의가 여러 개일 경우, 공통적인 특징이나 주요 차이점을 중심으로 요약하세요.
        - 강의개요도 요약하여 설명해주세요.
        - 제공된 정보 외 내용은 추측하지 말아주세요.
        - 답변은 자연스럽고 간결하게 제공해주세요.
        """
        response = ollama.chat(model='eeve-korean:latest', messages=[
            {"role": "system", "content": "너는 광운대학교 전자공학과 강의 추천 챗봇이야."},
            {"role": "user", "content": prompt}
        ])
        return response["message"]["content"].strip()

    except Exception as e:
        return f"Ollama 로컬 모델 호출 오류: {e}"

# FastAPI 엔드포인트
class Query(BaseModel):
    query: str

@llm_router.post("/")
async def chat_endpoint(query: Query):
    try:
        previous_results = load_previous_search_results()
        answer = generate_answer(query.query, previous_results)
        add_to_chat_history(query.query, answer)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류 발생: {str(e)}")
