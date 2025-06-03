import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# 맞춤법 교정 함수 (백엔드 모델 연동)
def call_spellcheck_api(text):
    # 환경변수 로드
    azure_oai_endpoint = os.getenv("AZURE_OAI_ENDPOINT")
    azure_oai_key = os.getenv("AZURE_OAI_KEY")
    azure_oai_deployment = os.getenv("AZURE_OAI_DEPLOYMENT")
    azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    azure_search_key = os.getenv("AZURE_SEARCH_KEY")
    azure_search_index = os.getenv("AZURE_SEARCH_INDEX")

    # 1️⃣ Azure Cognitive Search 호출
    search_url = f"{azure_search_endpoint}/indexes/{azure_search_index}/docs/search?api-version=2021-04-30-Preview"
    search_headers = {
        "api-key": azure_search_key,
        "Content-Type": "application/json"
    }
    payload = {
        "search": text,
        "queryType": "simple"
    }

    try:
        search_response = requests.post(search_url, headers=search_headers, json=payload)
        search_response.raise_for_status()
        search_results = search_response.json()
        documents = [doc.get("input_text", "") for doc in search_results.get("value", [])]
        context_text = "\n\n".join(documents)
    except Exception as e:
        return f"Search API 오류: {e}", f"검색 실패"

    # 2️⃣ Chat Completion 호출
    system_prompt = "너는 한국어 맞춤법 교정 전문가야. 문장의 오탈자 및 문맥 오류를 교정해줘."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"참고 문서 내용:\n{context_text}"},
        {"role": "user", "content": text}
    ]

    url = f"{azure_oai_endpoint}/openai/deployments/{azure_oai_deployment}/chat/completions?api-version=2024-02-15-preview"
    headers = {
        "Content-Type": "application/json",
        "api-key": azure_oai_key
    }
    body = {
        "messages": messages,
        "temperature": 0.5,
        "max_tokens": 1000
    }

    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        return content, "교정 성공"
    except Exception as e:
        return f"API 오류: {e}", "Chat Completion 호출 실패"