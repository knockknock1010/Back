# app/services/pdf_parser.py

import fitz # PyMuPDF
import base64

def extract_content_from_pdf(file_content: bytes):
    """
    텍스트 추출을 시도하고, 텍스트가 부족하면 이미지(Base64) 리스트를 반환합니다.
    """
    doc = fitz.open(stream=file_content, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()

    # 텍스트가 50자 미만이면 스캔본으로 간주
    if len(text.strip()) < 50:
        print("🔍 스캔본 PDF 감지: 이미지 변환을 시작합니다.")
        base64_images = []
        for page in doc:
            # DPI를 높여 글자 가독성 확보 (2배 확대)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_bytes = pix.tobytes("png")
            base64_img = base64.b64encode(img_bytes).decode('utf-8')
            base64_images.append(base64_img)
        return {"type": "images", "content": base64_images}
    
    return {"type": "text", "content": text}