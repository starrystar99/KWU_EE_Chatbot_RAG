import json
import os

# 무조건 루트 경로 기준으로 저장되도록 설정
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CHAT_HISTORY_FILE = os.path.join(BASE_DIR, "chat_history.json")
SEARCH_HISTORY_FILE = os.path.join(BASE_DIR, "search_history.json")

# 대화 기록 로딩
def load_chat_history():
    if not os.path.exists(CHAT_HISTORY_FILE):
        return []
    with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []

# 대화 기록 저장
def save_chat_history(chat_history):
    chat_history = chat_history[-10:]  # 최대 10개 유지
    with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(chat_history, file, ensure_ascii=False, indent=4)

# 대화 초기화
def reset_chat_history():
    with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump([], file, ensure_ascii=False, indent=4)
    with open(SEARCH_HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump([], file, ensure_ascii=False, indent=4)

# 대화 추가
def add_to_chat_history(user_input, bot_response):
    chat_history = load_chat_history()
    chat_history.append({"user": user_input, "bot": bot_response})
    save_chat_history(chat_history)

# 검색 결과 추가 (기본 검색 결과만 저장)
def add_search_results_to_history(query, search_results):
    search_history = load_search_history()
    search_data = {
        "query": query,
        "results": search_results
    }
    search_history.append(search_data)
    save_search_history(search_history)

# 검색 기록 저장
def save_search_history(search_history):
    search_history = search_history[-10:]
    with open(SEARCH_HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(search_history, file, ensure_ascii=False, indent=4)

# 검색 기록 불러오기
def load_search_history():
    if os.path.exists(SEARCH_HISTORY_FILE):
        with open(SEARCH_HISTORY_FILE, "r", encoding="utf-8") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return []
    return []

# 최근 검색 결과만 불러오기
def load_previous_search_results():
    search_history = load_search_history()
    if search_history:
        return search_history[-1].get("results", [])
    return []

# 최근 교수명 불러오기 (검색 기록 기반)
def load_last_professor_search():
    search_history = load_search_history()
    for entry in reversed(search_history):
        for doc in entry.get("results", []):
            if "교수명" in doc:
                return doc["교수명"]
    return None

# 최근 강의명 불러오기 (검색 기록 기반)
def load_last_lecture_search():
    search_history = load_search_history()
    for entry in reversed(search_history):
        for doc in entry.get("results", []):
            if "강의명" in doc:
                return doc["강의명"]
    return None
