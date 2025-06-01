import gradio as gr
# --- pdf추출에 필요한 패키지 임포트 ---
import os
import platform
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import tempfile, textwrap, os
# --- OCR 처리 함수에서 넣어둔 패키지---
import pytesseract
from PIL import Image
import pdfplumber



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

# --- OCR 처리 함수들 ---
def handle_image_upload(file):
    if file is None:
        return gr.update() #초기화버튼 클릭시 이미지 파일이 None으로 설정됨
    try:
        image = Image.open(file)
        text = pytesseract.image_to_string(image, lang="kor")
        return gr.update(value=text)
    except Exception as e:
        return gr.update(value=f"[이미지 OCR 오류] {str(e)}")

def handle_pdf_upload(file):
    if file is None:
        return gr.update() #초기화버튼 클릭시 pdf 파일이 None으로 설정됨
    try:
        text = ""
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return gr.update(value=text if text else "[PDF에서 텍스트를 추출하지 못했습니다.]")
    except Exception as e:
        return gr.update(value=f"[PDF OCR 오류] {str(e)}")

# --- 검사 실행 함수 (교정 처리 포함) ---
from api_connector import call_spellcheck_api, call_ocr_api

def run_pipeline(input_type, pdf_file, image_file, input_text):
    try:
        if input_type == "이미지" and image_file:
            with open(image_file, "rb") as f:
                image_bytes = f.read()
            extracted_text = call_ocr_api(image_bytes)
        elif input_type == "PDF" and pdf_file:
            with open(pdf_file, "rb") as f:
                pdf_bytes = f.read()
            extracted_text = call_ocr_api(pdf_bytes)
        else:
            extracted_text = input_text

        # 교정 API 호출
        corrected_text, error_info = call_spellcheck_api(extracted_text)

        return gr.update(value=corrected_text, visible=True), gr.update(value=error_info, visible=True)

    except Exception as e:
        return gr.update(value="[검사 오류 발생]", visible=True), gr.update(value=f"{str(e)}", visible=True)
    
# --- 초기화 함수 ---
def clear_all():
    return "텍스트", "", "", None, None  # input_text, output_result, image_file, pdf_file

# --- 맞춤법 적용된 이미지 만드는 함수---


# --- pdf추출: 텍스트 PDF로 변환하는 함수 ---
def text_to_pdf(text, font_size=12):
    import platform

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
    image_file.change(fn=handle_image_upload, inputs=image_file, outputs=input_text)
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