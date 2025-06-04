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

    # Azure Cognitive Search 호출
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

    # Chat Completion 호출
    system_prompt = """
당신은 한국어 맞춤법 전문가 입니다. 사용자가 문법적으로 올바르지 않은 문장을 입력하면 이를 교정하고 다음 형식으로 출력하세요. 입력받은 문장이 올바르거나, 검색 인덱스에서 적절한 결과를 찾지 못했을 경우 입력된 문장과 교정된 문장이 같도록 하고, 오류는 빈 문자열로 처리하세요. 입력이 문장 형식이 아닐 경우 문장 부호에 대한 교정은 이루어지지 않도록 하세요. 출력은 반드시 아래 예시와 같이 작성해야 합니다. 추가적인 설명이나 다른 형식은 포함하지 마세요.

출력 형태 예시:

{
    "입력": "교수님이 좋으셔서 정밀 다행이야",
    "교정": "교수님이 좋으셔서 정말 다행이야.",
    "오류": "오타, 문장부호"
}

오류 항목에는 해당 문장에서 발견한 오류 종류를 쉼표로 구분하여 적어주세요.

오류 종류 예시:

- 띄어쓰기
- 문장부호
- 유사 모양
- 유사 발음
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"참고 문서 내용:\n{context_text}"},
        {"role": "user", "content": text}
    ]

    url = f"{azure_oai_endpoint}/openai/deployments/{azure_oai_deployment}/chat/completions?api-version=2025-01-01-preview"
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

        # JSON 파싱
        import re
        try:
            # 코드 블록 제거 및 중괄호 내부만 추출
            content = content.replace("```json", "").replace("```", "").strip()
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                content = match.group(0)

            data = json.loads(content)
            return data.get("교정", ""), data.get("오류", "")
        except Exception as e:
            return content, f"JSON 파싱 오류: {str(e)}"

    except Exception as e:
        if "400 Client Error" in str(e) and "Bad Request" in str(e):
            return "교정 실패", "죄송합니다. 비속어가 포함된 문장은 교정할 수 없습니다."
        elif 'content' in str(e):
            return "교정 실패", "죄송합니다. 폭력, 혐오, 선정적, 자해 등의 내용을 포함한 문장은 교정할 수 없습니다."
        else:
            print(e)
            return "교정 실패", "교정에 실패했습니다."