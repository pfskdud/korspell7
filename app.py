# https://github.com/it-hxunzi/spellcheck-ocr-ui

import gradio as gr
# --- pdf추출에 필요한 패키지 임포트 ---
import os
import platform
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import tempfile, textwrap, os
# --- azure image OCR 처리 함수 ---
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential
# --- azure pdf OCR 처리 함수 ---
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
# --- env 함수 ---
from dotenv import load_dotenv
# --- 한국어만 필터링하기 위한 정규화 라이브러리 --
import re

# CSS 스타일 정의
css_custom = """
    <style>
        .fixed-container {
            width: 800px;
            min-height: 600px;
            overflow-y: auto;
            padding: 10px;
        }
        .file-upload-container {
            overflow-y: auto;
            height: 70px !important;
            display: inline-block;
        }
        .result-box {
            overflow-y: auto;
            height: 380px !important;
            display: inline-block;
        }
        .error-box {
            overflow-y: auto;
            height: 380px !important;
            display: inline-block;
        }
    </style>
"""

# --- 한글 + roman num(논문 Pdf에서 많이 사용해서 예외적으로) 필터링하는 함수 ---
def filter_korean_text(text):
    return re.sub(r"[^가-힣0-9\s.,!?\u2160-\u216F]", "", text)

# --- 이미지 OCR 처리 함수 ---
def handle_image_upload(file):
    # env - endpoint/api key
    load_dotenv()

    # Azure CV Studio key
    try:
        endpoint = os.getenv("VISION_ENDPOINT")
        key = os.getenv("VISION_KEY")
    except KeyError:
        print("Missing environment variable 'VISION_ENDPOINT' or 'VISION_KEY'")
        print("Set them before running this sample.")
        exit()

    # Image Analysis client
    client = ImageAnalysisClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key)
    )

    if file is None:
        return gr.update() #초기화버튼 클릭시 이미지 파일이 None으로 설정됨
    try:
        with open(file.name, "rb") as image_stream:
            result = client.analyze(
                image_data=image_stream,
                visual_features=[VisualFeatures.CAPTION, VisualFeatures.READ],
                gender_neutral_caption=True,
            )

        extracted_lines = []
        backend_data = []

        if result.read:
            for block in result.read.blocks:
                for line in block.lines:
                    line_text = filter_korean_text(line.text)
                    if line_text.strip():
                        extracted_lines.append(line_text)

                        for word in line.words:
                            filtered_text = filter_korean_text(word.text)
                            if filtered_text.strip():
                                backend_data.append({
                                    "text": filtered_text,
                                    "polygon": word.bounding_polygon,
                                    "confidence": word.confidence
                                })
                            
        frontend_text = "\n".join(extracted_lines)

        print(backend_data)

        return gr.update(value=frontend_text), backend_data

    except Exception as e:
        return gr.update(value=f"[이미지 OCR 오류] {str(e)}")

# --- pdf에서 줄이 달라지는 부분에서 강제적으로 줄바꿈되는 현상 ---
def clean_linebreaks(text):
    # 라인별로 나누기
    lines = text.split('\n')
    cleaned = []

    for i, line in enumerate(lines):
        # 현재 줄과 다음 줄을 연결할 수 있는 조건 확인
        if i < len(lines) - 1:
            next_line = lines[i + 1].strip()
            if line and not line.endswith(('.', '?', '!', ':', '”', '’')) and next_line:
                # 줄 끝이 문장 끝이 아니고, 다음 줄이 이어지는 경우
                cleaned.append(line.rstrip() + ' ')
            else:
                cleaned.append(line.strip() + '\n')
        else:
            cleaned.append(line.strip())

    return ''.join(cleaned)

# --- pdf 파일 구조 기반 수정 ---
def parse_paragraphs_from_result(result):
    # result.paragraphs는 이미 content 필드가 있으므로 바로 사용 가능
    paragraphs = result.paragraphs
    cleaned_paragraphs = []

    for p in paragraphs:
        text = p.content.strip()

        # 페이지 넘버나 주석(예: "2 국어교육연구 제31집") 같은 것 제외
        if len(text) < 5 or re.match(r"^\d+\s+[가-힣]", text):
            continue
        if text.startswith("*") or "제" in text and "집" in text:
            continue

        cleaned_paragraphs.append(text)

    return "\n\n".join(cleaned_paragraphs)

# --- pdf 파일 ocr ---
def handle_pdf_upload(file):
    load_dotenv()

    # Azure Document Intelligence key
    try:
        endpoint = os.getenv("FORM_RECOGNIZER_ENDPOINT")
        key = os.getenv("FORM_RECOGNIZER_KEY")
    except KeyError:
        print("Missing environment variable 'FORM_RECOGNIZER_ENDPOINT' or 'FORM_RECOGNIZER_KEY'")
        print("Set them before running this sample.")
        exit()

    client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))

    if file is None:
        return gr.update() #초기화버튼 클릭시 pdf 파일이 None으로 설정됨
    try:
        with open(file.name, "rb") as f:
            poller = client.begin_analyze_document("prebuilt-layout", f)
            result = poller.result()
        
        pretty_output = parse_paragraphs_from_result(result)

        filtered = filter_korean_text(pretty_output)
        cleaned_text = clean_linebreaks(filtered)

        return gr.update(value=cleaned_text)
    
    except Exception as e:
        return gr.update(value=f"[PDF OCR 오류] {str(e)}")

# --- 검사 실행 함수 (교정 처리 포함) ---
from api_connector import call_spellcheck_api

def run_pipeline(input_type, pdf_file, image_file, input_text):
    try:
        # OCR 결과는 이미 input_text에 들어있음
        extracted_text = input_text

        # 교정 API 호출
        corrected_text, error_info = call_spellcheck_api(extracted_text)

        # Gradio Textbox는 문자열만 필요!
        return corrected_text, error_info

    except Exception as e:
        return "[검사 오류 발생]", str(e)

# --- 초기화 함수 ---
def clear_all():
    return "텍스트", "", "", None, None  # input_text, output_result, image_file, pdf_file

# --- 맞춤법 적용된 이미지 만드는 함수---


# --- pdf추출: 텍스트 PDF로 변환하는 함수 ---
def text_to_pdf(text, font_size=12):

    # pdf추출 시 파일 내 폰트 오류
    system = platform.system()
    if system == "Darwin":
        font_path = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
    elif system == "Windows":
        font_path = "C:/Windows/Fonts/malgun.ttf"
    else:
        raise FileNotFoundError("지원하지 않는 운영체제입니다.")
    
    font_name = "KoreanFont"

    # 폰트 등록
    try:
        pdfmetrics.getFont(font_name)
    except KeyError:
        pdfmetrics.registerFont(TTFont(font_name, font_path))

    temp_path = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
    c = canvas.Canvas(temp_path, pagesize=A4)
    width, height = A4

    c.setFont(font_name, font_size)

    x = 50
    y = height - 60
    line_height = font_size + 6
    page_num = 1

    lines = textwrap.wrap(text, width=90)

    for line in lines:
        c.drawString(x, y, line)
        y -= line_height
        if y < 60:
            # 페이지 번호 추가
            c.setFont(font_name, 10)
            c.drawRightString(width - 50, 30, f"- {page_num} -")
            c.showPage()
            page_num += 1
            y = height - 60
            c.setFont(font_name, font_size)

    # 마지막 페이지 번호
    c.setFont(font_name, 10)
    c.drawRightString(width - 50, 30, f"- {page_num} -")
    c.save()
    return temp_path

def download_pdf(text):
    return text_to_pdf(text)    

# --- Gradio UI 구성 ---
with gr.Blocks() as demo:
    gr.HTML(css_custom)

    gr.Markdown("## OCR 기반 한국어 맞춤법 교정 챗봇 시스템")
    hidden_backend_data = gr.State()        

    with gr.Row(elem_classes="fixed-container"):
            
        with gr.Column():
            gr.Markdown("### 원문 입력")
            input_type = gr.Radio(["텍스트", "이미지", "PDF"], label=" 입력 형식 선택", value="텍스트")

            with gr.Row(visible=False) as image_row:
                image_file = gr.File(type="filepath", label="이미지 업로드", file_types=[".jpg", ".jpeg", ".png"], scale=1, elem_classes="file-upload-container")

            with gr.Row(visible=False) as pdf_row:
                pdf_file = gr.File(type="filepath", label="PDF 업로드", file_types=[".pdf"], scale=1, elem_classes="file-upload-container")

            input_text = gr.Textbox(label="검사할 문장을 입력하세요.", placeholder="여기에 문장을 입력해주세요...", lines=9, visible=True)
            submit_btn = gr.Button("검사 실행")

            with gr.Row():
                gr.Markdown("")
                btn_clear = gr.Button("모든 입력 및 출력 초기화", variant="primary")

        with gr.Column():
            gr.Markdown("### 교정 결과")

            output_result = gr.Textbox(
                label="",
                interactive=True,
                visible=True,
                lines=16,
                scale=1,
                elem_classes="result-box"
            )

            with gr.Row():
                btn_download_png = gr.Button("이미지 다운로드")
                btn_download_pdf = gr.Button("PDF 다운로드")

        with gr.Column():
            gr.Markdown("### 오류 사항")
            output_error = gr.Textbox(label="", interactive=False, lines=16, scale=1, elem_classes="error-box")

    # 입력 형식에 따른 업로드창 표시
    def toggle_inputs(input_type):
        return {
            image_row: gr.update(visible=input_type == "이미지"),
            pdf_row: gr.update(visible=input_type == "PDF")
        }

    input_type.change(fn=toggle_inputs, inputs=input_type, outputs=[image_row, pdf_row])
    
    # 이미지 또는 PDF 업로드 시 텍스트 자동 채우기
    image_file.change(fn=handle_image_upload, inputs=image_file, outputs=[input_text, hidden_backend_data])
    pdf_file.change(fn=handle_pdf_upload, inputs=pdf_file, outputs=input_text)

    # 검사 실행 클릭 
    submit_btn.click(fn=run_pipeline,
                     inputs=[input_type, pdf_file, image_file, input_text],
                     outputs=[output_result, output_error])

    # 초기화 버튼 클릭
    btn_clear.click(fn=clear_all, outputs=[input_type, input_text, output_result, image_file, pdf_file])

    # 다운로드 버튼 클릭 (기능 미완성)
    btn_download_png.click(fn=lambda: "이미지 수정 기능은 추후 ai활용해 구현 예정")
    btn_download_pdf.click(fn=download_pdf, inputs=output_result, outputs=gr.File())

demo.launch()