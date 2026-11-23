from pypdf import PdfReader
import io

def extract_text_from_pdf(pdf_file) -> str:
    """
    อ่านไฟล์ PDF และคืนค่าเป็นข้อความทั้งหมด (Raw Text)
    รองรับทั้ง path ของไฟล์ หรือ BytesIO object จาก Streamlit uploader
    """
    text = ""
    try:
        reader = PdfReader(pdf_file)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการอ่านไฟล์ PDF: {e}")
    return text.strip()