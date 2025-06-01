import requests
import streamlit as st
from openai import AzureOpenAI

# Azure OpenAI 클라이언트 초기화
client = AzureOpenAI(
    api_key=st.secrets["openai_key"],
    api_version=st.secrets["openai_api_version"],
    azure_endpoint=st.secrets["openai_endpoint"]
)

# 맞춤법 교정 함수
def call_spellcheck_api(text):
    response = client.chat.completions.create(
        model=st.secrets["openai_deployment"], 
        messages=[
            {"role": "system", "content": "너는 한국어 맞춤법 교정 전문가야. JSON 형식으로 결과를 제공해줘. 예: {\"교정\": \"문장\", \"오류\": \"오류 사유\"}"},
            {"role": "user", "content": f"다음 문장의 오탈자 및 문맥 오류를 교정해줘:\n{text}"}
        ],
        temperature=0.5,
        max_tokens=500
    )
    result = response.choices[0].message.content.strip()

    # JSON 형태 파싱
    import json
    try:
        # GPT 응답에서 코드 블록 (` ```json`, ``` ) 제거
        result = result.replace("```json", "").replace("```", "").strip()
        data = json.loads(result)
        return data.get("교정", ""), data.get("오류", "")
    except Exception as e:
        return result, f"JSON 파싱 오류: {str(e)}"