import os
import json
from openai import AzureOpenAI
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# Azure OpenAI 클라이언트 초기화
client = AzureOpenAI(
    api_key=os.getenv("OPENAI_KEY"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("OPENAI_ENDPOINT")
)

# 맞춤법 교정 함수
def call_spellcheck_api(text):
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": "너는 한국어 맞춤법 교정 전문가야. JSON 형식으로 결과를 제공해줘. 예: {\"교정\": \"문장\", \"오류\": \"오류 사유\"}"},
            {"role": "user", "content": f"다음 문장의 오탈자 및 문맥 오류를 교정해줘:\n{text}"}
        ],
        temperature=0.5,
        max_tokens=500
    )
    result = response.choices[0].message.content.strip()

    try:
        # GPT 응답에서 코드 블록(` ```json`, ``` ) 제거
        result = result.replace("```json", "").replace("```", "").strip()
        data = json.loads(result)
        return data.get("교정", ""), data.get("오류", "")
    except Exception as e:
        return result, f"JSON 파싱 오류: {str(e)}"