**Hybrid Search Chatbot with Dual LLM Integration**

This project is a Capstone Design implementation of a hybrid search chatbot using FAISS + BM25 for high-accuracy information retrieval, combined with two interchangeable Large Language Models (LLMs) for response generation.

(1) Features
- Hybrid Search Engine
  - FAISS for dense vector search (semantic similarity).
  - BM25 for sparse keyword-based search.
  - Automatic query type classification (classify_query_type) to determine optimal text processing.
  - Score fusion of FAISS and BM25 results for improved accuracy.

- Dual LLM Support
  - Cloud-based GPT for high-quality, general-purpose responses.
  - Local EEVE-based LLM for offline, privacy-preserving conversation.
  - Both LLMs share the same hybrid search backend for consistent results.

- Dynamic Query Handling
    - Professor-related queries: Search only by professor name.
    - Course-related queries: Search by course name, professor name, and course description.
    - General queries: Automatic selection of best retrieval strategy.

- Colab-Compatible Setup
  - Fully automated indexing of course/professor data.
  - FAISS and BM25 index creation (faiss_index.bin, bm25_index.pkl).
  - Visualization of vector space and search results for analysis.
 
(2) Project Structure
CHATBOT_RAG_LLM/
├── search.py         # Hybrid search logic (FAISS + BM25)
├── gpt.py            # GPT-based chatbot
├── local_myllm.py    # EEVE-based local chatbot
├── embedding/        # Embedding storage
├── data/             # Source data files
└── ...

(3) How It Works
1. User Input → Query Classification
  - The system classifies the query as professor, course, or general.
2. Hybrid Search Execution
  - FAISS and BM25 run in parallel, scores are normalized, and results are merged.
3. LLM Response Generation
  - The retrieved context is sent to either GPT or EEVE (configurable), producing the final answer.

