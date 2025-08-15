import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import faiss
import numpy as np
import pickle
import pandas as pd
import logging
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.config import FAISS_INDEX_PATH, BM25_INDEX_PATH, DATASET_PATH, FAISS_TOP_K, BM25_WEIGHT
from backend.chat_history import add_search_results_to_history

search_router = APIRouter()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 1. 쿼리 분류 함수
def classify_query_type(query: str) -> str:
    prof_keywords = ["교수", "교수님", "이 교수", "담당 교수", "선생님"]
    return "professor" if any(kw in query for kw in prof_keywords) else "course"

# 2. 텍스트 구성 함수
def get_combined_text(row, query_type: str) -> str:
    if query_type == "professor":
        return f"교수명: {row.get('교수명', '')} 강의명: {row.get('강의명', '')}"
    else:
        return (
            f"강의명: {row.get('강의명', '')} "
            f"교수명: {row.get('교수명', '')} "
            f"강의구성: {row.get('강의구성', '')} "
            f"개요: {row.get('교과목개요', '')}"
        )

def load_dataset():
    logging.info(f"🔹 Loading dataset from: {DATASET_PATH}")
    try:
        return pd.read_csv(DATASET_PATH, encoding="utf-8-sig")
    except Exception as e:
        logging.error(f"Dataset load failed: {e}")
        return None

def search_course_directly(query, df):
    filtered_df = df[df["강의명"] == query]
    if filtered_df.empty:
        return None
    course_info = filtered_df.iloc[0]
    return [{
        "강의명": course_info["강의명"],
        "교수명": course_info["교수명"],
        "이수구분": course_info["이수구분"],
        "평점": course_info.get("평점", "정보 없음"),
        "과제": course_info.get("과제", "정보 없음"),
        "출결": course_info.get("출결", "정보 없음"),
        "시험": course_info.get("시험", "정보 없음"),
        "교과목개요": course_info["교과목개요"][:150]
    }]

def load_faiss_index():
    logging.info(f"🔹 Loading FAISS index from: {FAISS_INDEX_PATH}")
    try:
        return faiss.read_index(FAISS_INDEX_PATH)
    except Exception as e:
        logging.error(f"FAISS index load failed: {e}")
        return None

def normalize_scores(scores):
    if len(scores) == 0:
        return np.zeros_like(scores)
    min_score = np.min(scores)
    max_score = np.max(scores)
    return (scores - min_score) / (max_score - min_score + 1e-8) if max_score - min_score > 1e-8 else np.ones_like(scores)

# 핵심 함수: 하이브리드 검색 + 쿼리 유형별 텍스트 구성
def hybrid_search(query, top_k=FAISS_TOP_K):
    logging.info(f"\n Searching for: '{query}'")
    df = load_dataset()
    if df is None:
        logging.error("데이터 로드 실패, 검색 중단")
        return []

    direct_course_result = search_course_directly(query, df)
    if direct_course_result:
        logging.info("강의명을 직접 입력하여 CSV에서 검색 완료!")
        add_search_results_to_history(query, direct_course_result)
        return direct_course_result

    # 질의 유형 분류
    query_type = classify_query_type(query)
    logging.info(f"질의 유형: {query_type}")

    # 검색 텍스트 구성 (질의 유형별)
    combined_texts = [get_combined_text(row, query_type) for _, row in df.iterrows()]
    bm25 = BM25Okapi([doc.split() for doc in combined_texts])

    # 임베딩 & FAISS 검색
    embedding_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    query_vector = embedding_model.encode([query]).astype('float32')
    faiss_index = load_faiss_index()
    if faiss_index is None:
        return []

    faiss.normalize_L2(query_vector)
    D, I = faiss_index.search(query_vector, len(df))

    # BM25 검색
    tokenized_query = query.split()
    bm25_scores = np.array(bm25.get_scores(tokenized_query))

    # 점수 정규화 & 결합
    faiss_scores = np.zeros(len(df))
    faiss_scores[I[0]] = D[0]
    faiss_norm = normalize_scores(faiss_scores)
    bm25_norm = normalize_scores(bm25_scores)
    combined_scores = (1 - BM25_WEIGHT) * faiss_norm + BM25_WEIGHT * bm25_norm

    # 상위 결과 추출
    top_indices = np.argsort(combined_scores)[::-1]
    search_results = []

    for idx in top_indices:
        score = combined_scores[idx]
        if score < 0.5 or len(search_results) >= top_k: #점수 필터링
            continue
        row = df.iloc[idx]
        search_results.append({
            "학과": row["학과"],
            "강의명": row["강의명"],
            "개설학기": row["개설학기"],
            "교수명": row["교수명"],
            "평점": row["평점"],
            "과제": row["과제"],
            "조모임": row["조모임"],
            "성적": row["성적"],
            "출결": row["출결"],
            "시험": row["시험"],
            "학정번호": row["학정번호"],
            "이수구분": row["이수구분"], #추가
            "강의구성": row["강의구성"],
            "강의시간": row["강의시간"],
            "교과목개요": row["교과목개요"][:150],
            "점수": round(float(score), 4)
        })

    if search_results:
        add_search_results_to_history(query, search_results)
    return search_results

# API 엔드포인트
class Query(BaseModel):
    query: str

@search_router.post("", include_in_schema=True)
async def search_courses(query: Query):
    try:
        user_query = query.query
        df = load_dataset()
        if df is None:
            raise HTTPException(status_code=500, detail="데이터셋 로드 실패")

        direct_course_result = search_course_directly(user_query, df)
        if direct_course_result:
            logging.info("강의명을 직접 입력하여 CSV에서 검색 완료!")
            add_search_results_to_history(user_query, direct_course_result)
            return {"results": direct_course_result}

        search_results = hybrid_search(user_query)
        if not search_results:
            return {"results": [], "message": "관련 강의를 찾을 수 없습니다."}

        return {"results": search_results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류 발생: {str(e)}")

if __name__ == "__main__":
    query = input("검색어를 입력하세요: ")
    results = hybrid_search(query)

    print("\n검색 결과:")
    for rank, result in enumerate(results, 1):
        print(f"\n {rank}위 - {result['강의명']} ({result['교수명']})")
        print(f"학과: {result['학과']} / 개설학기: {result['개설학기']}")
        print(f"평점: {result['평점']} / 출결: {result['출결']}")
        print(f"시험: {result['시험']} / 과제: {result['과제']}")
        print(f"개요: {result['교과목개요']}...")
        print(f"점수: {result['점수']:.4f}")

__all__ = ["search_router"]
