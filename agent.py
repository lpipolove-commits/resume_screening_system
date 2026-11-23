import os
import time
from google import genai

try:
    import streamlit as st
except ImportError:
    st = None

MODEL_NAME = "gemini-3.8-flash"
FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
]


def _get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and st is not None:
        try:
            api_key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            api_key = None
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def _generate_with_retry(client, model_name: str, prompt: str, retries: int = 1) -> str:
    models_to_try = []
    for m in [model_name] + FALLBACK_MODELS:
        if m and "2.5-flash-lite" not in m and m not in models_to_try:
            models_to_try.append(m)

    last_error = None

    for current_model in models_to_try:
        for attempt in range(retries):
            try:
                response = client.models.generate_content(model=current_model, contents=prompt)
                if response and response.text:
                    return response.text
            except Exception as e:
                last_error = e
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                if "404" in err_str or "NOT_FOUND" in err_str:
                    break
                break

    raise last_error or RuntimeError("ไม่สามารถเชื่อมต่อโมเดล AI ได้ในขณะนี้ครับ")


def ask_career_agent(candidate_profile: dict, user_message: str) -> str:
    """AI Career Coach สำหรับแนะนำผู้สมัครงาน"""
    client = _get_client()
    role = candidate_profile.get("target_role", "ตำแหน่งที่สนใจ")
    context_text = (
        f"ชื่อผู้สมัคร: {candidate_profile.get('name', '-')}\n"
        f"ตำแหน่งที่สนใจ: {role}\n"
        f"หน้าที่และความรับผิดชอบ: {candidate_profile.get('responsibilities', '-')}\n"
        f"เนื้อหาจากเรซูเม่: {candidate_profile.get('resume_text', '')[:1500]}"
    )

    if client is None:
        return (
            "ยังไม่ได้ตั้งค่า GEMINI_API_KEY (โหมดแนะนำเบื้องต้น):\n"
            f"- ตรวจดูว่าประสบการณ์ที่กรอกสอดคล้องกับตำแหน่ง '{role}' หรือไม่\n"
            "- เพิ่มตัวเลขผลงานหรือเครื่องมือที่ใช้จริงในเรซูเม่ และเตรียมตัวอย่างงานที่ทำได้จริงครับ"
        )

    prompt = (
        "คุณคือ AI Career Coach ที่ช่วยแนะนำผู้สมัครงานอย่างตรงไปตรงมาและเป็นประโยชน์\n"
        f"ข้อมูลผู้สมัคร:\n{context_text}\n\n"
        f"คำถามของผู้สมัคร:\n{user_message}\n\n"
        "ตอบเป็นภาษาไทยให้กระชับ อ่านง่าย และนำไปปรับใช้ได้จริง"
    )

    try:
        return _generate_with_retry(client, MODEL_NAME, prompt)
    except Exception:
        return (
            f"ขณะนี้เซิร์ฟเวอร์ AI กำลังมีผู้ใช้งานหนาแน่นชั่วคราว จึงขอให้คำแนะนำเบื้องต้นสำหรับตำแหน่ง **{role}** ก่อนนะครับ:\n"
            "- ตรวจสอบว่าทักษะและเครื่องมือสำคัญในเรซูเม่ตรงกับคีย์เวิร์ดของตำแหน่งที่สมัครหรือไม่\n"
            "- ใส่ผลลัพธ์เชิงตัวเลขหรือตัวอย่างผลงานที่ทำสำเร็จจริงให้ชัดเจน\n"
            "- ลองกดส่งคำถามนี้อีกครั้งในอีกไม่กี่วินาทีเพื่อให้ AI วิเคราะห์เชิงลึกครับ"
        )


def ask_hr_agent(candidates: list[dict], user_message: str) -> str:
    """AI HR Talent Assistant สำหรับค้นหา คัดกรอง และเปรียบเทียบผู้สมัคร"""
    client = _get_client()

    if not candidates:
        return "ยังไม่มีข้อมูลผู้สมัครในระบบครับ ลองให้ผู้สมัครฝากเรซูเม่ก่อนนะครับ"

    summaries = []
    for c in candidates[:15]:
        summaries.append(
            f"- ชื่อ: {c.get('name')} | ตำแหน่งที่สนใจ: {c.get('target_role')} | ติดต่อ: {c.get('contact')}\n"
            f"  หน้าที่/ประสบการณ์: {c.get('responsibilities', '-')}\n"
            f"  เนื้อหาเรซูเม่: {c.get('resume_text', '')[:600]}"
        )
    pool_text = "\n\n".join(summaries)

    if client is None:
        keywords = [w.lower() for w in user_message.split() if len(w) >= 2]
        matched = [
            c.get("name")
            for c in candidates
            if any(
                k in f"{c.get('name', '')} {c.get('target_role', '')} {c.get('responsibilities', '')} {c.get('resume_text', '')}".lower()
                for k in keywords
            )
        ]
        if matched:
            return "โหมดค้นหาเบื้องต้นพบผู้สมัครที่เกี่ยวข้อง: " + ", ".join(matched)
        return "โหมดค้นหาเบื้องต้นยังไม่พบคำที่ตรงชัดเจน ลองระบุตำแหน่งหรือทักษะ เช่น Data, Python, การตลาด ครับ"

    prompt = (
        "คุณคือ AI HR Talent Assistant ที่ช่วย HR ค้นหาและคัดเลือกผู้สมัคร\n"
        f"รายชื่อและข้อมูลผู้สมัครในระบบ:\n{pool_text}\n\n"
        f"ความต้องการหรือคำถามของ HR:\n{user_message}\n\n"
        "ให้ระบุชื่อผู้สมัครที่ตรงกับความต้องการ เรียงตามความเหมาะสม พร้อมเหตุผลสั้นๆ และจุดที่ควรซักถามเพิ่มเติม"
    )

    try:
        return _generate_with_retry(client, MODEL_NAME, prompt)
    except Exception:
        keywords = [w.lower() for w in user_message.split() if len(w) >= 2]
        matched = [
            f"{c.get('name')} ({c.get('target_role')})"
            for c in candidates
            if any(
                k in f"{c.get('name', '')} {c.get('target_role', '')} {c.get('responsibilities', '')} {c.get('resume_text', '')}".lower()
                for k in keywords
            )
        ]
        extra = ("\nผู้สมัครที่เกี่ยวข้องกับคำค้นหาเบื้องต้น: " + ", ".join(matched)) if matched else ""
        return (
            "ขณะนี้เซิร์ฟเวอร์ AI กำลังมีผู้ใช้งานหนาแน่นชั่วคราว แนะนำให้ลองส่งคำถามอีกครั้งในอีกสักครู่ครับ"
            + extra
        )


def run_hr_agent(user_message: str, candidates: list[dict] | None = None, **kwargs) -> str:
    """ฟังก์ชันหลักที่รองรับการเรียกใช้งาน HR Agent"""
    return ask_hr_agent(candidates or [], user_message)