import os
import streamlit as st


def _get_gemini_api_key() -> str:
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip()


def _call_gemini(prompt: str) -> str | None:
    api_key = _get_gemini_api_key()
    if not api_key:
        return None

    # ลองใช้ SDK รุ่นใหม่ google-genai ก่อน
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = getattr(response, "text", None)
        if text and text.strip():
            return text.strip()
    except Exception:
        pass

    # สำรองด้วย SDK รุ่นเก่า google-generativeai หากติดตั้งไว้
    try:
        import google.generativeai as genai_legacy

        genai_legacy.configure(api_key=api_key)
        model = genai_legacy.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        text = getattr(response, "text", None)
        if text and text.strip():
            return text.strip()
    except Exception:
        pass

    return None


def ask_career_agent(profile: dict, user_msg: str) -> str:
    name = profile.get("name", "-")
    target_role = profile.get("target_role", "-")
    responsibilities = profile.get("responsibilities", "-")
    resume_text = profile.get("resume_text", "")

    prompt = f"""
คุณคือ AI Career Coach ผู้เชี่ยวชาญด้านการรีวิวเรซูเม่และการแนะแนวอาชีพ
ข้อมูลผู้สมัครปัจจุบัน:
- ชื่อ: {name}
- ตำแหน่งที่สนใจ: {target_role}
- หน้าที่และความรับผิดชอบ: {responsibilities}
- เนื้อหาเรซูเม่:
{resume_text}

คำถามของผู้สมัคร: {user_msg}
กรุณาตอบเป็นภาษาไทยอย่างสุภาพ ชัดเจน และนำไปปฏิบัติได้จริง
"""
    ai_reply = _call_gemini(prompt)
    if ai_reply:
        return ai_reply

    return (
        f"**คำแนะนำเบื้องต้นสำหรับ {name} (ตำแหน่ง: {target_role}):**\n\n"
        f"จากคำถามของคุณ: *\"{user_msg}\"*\n\n"
        "- **จุดแข็งที่ควรชู:** เน้นทักษะและผลงานที่สอดคล้องกับตำแหน่งเป้าหมายให้เห็นชัดเจนในย่อหน้าแรก\n"
        "- **การปรับเรซูเม่:** เพิ่มตัวเลขหรือผลลัพธ์เชิงปริมาณ (เช่น % ที่เพิ่มขึ้น หรือเวลาที่ลดลง) ในประสบการณ์ทำงาน\n"
        "- **การเตรียมสัมภาษณ์:** เตรียมยกตัวอย่างโปรเจกต์จริง 1–2 ตัวอย่าง พร้อมอธิบายบทบาทและวิธีแก้ปัญหาของคุณ\n\n"
        "*(หมายเหตุ: ขณะนี้ยังไม่ได้เชื่อมต่อ `GEMINI_API_KEY` ใน Secrets จึงแสดงคำตอบโหมดสาธิตครับ)*"
    )


def ask_hr_agent(candidates: list[dict], hr_prompt: str) -> str:
    if not candidates:
        return "ยังไม่มีข้อมูลผู้สมัครในระบบครับ ลองเพิ่มข้อมูลผู้สมัครในหน้า Candidate Portal ก่อนนะครับ"

    summaries = []
    for idx, c in enumerate(candidates[:15], start=1):
        summaries.append(
            f"{idx}. ชื่อ: {c.get('name', '-')} | ตำแหน่งที่สนใจ: {c.get('target_role', '-')} | "
            f"ประสบการณ์: {c.get('responsibilities', '-')} | เรซูเม่ย่อ: {(c.get('resume_text') or '')[:300]}"
        )
    candidates_block = "\n".join(summaries)

    prompt = f"""
คุณคือ AI HR Talent Assistant ผู้ช่วยคัดกรองและวิเคราะห์ผู้สมัครงาน
รายชื่อผู้สมัครในระบบ:
{candidates_block}

คำสั่งจาก HR: {hr_prompt}
กรุณาสรุป วิเคราะห์เปรียบเทียบ และแนะนำคำถามสัมภาษณ์เป็นภาษาไทยอย่างเป็นระบบ
"""
    ai_reply = _call_gemini(prompt)
    if ai_reply:
        return ai_reply

    lines = [f"**สรุปรายชื่อผู้สมัครทั้งหมด {len(candidates)} คน (โหมดสาธิต):**\n"]
    for idx, c in enumerate(candidates[:10], start=1):
        lines.append(
            f"- **{idx}. {c.get('name', '-')}** — ตำแหน่ง: *{c.get('target_role', '-')}* ({c.get('contact', '-')})"
        )
    lines.append(
        "\n*(หมายเหตุ: ขณะนี้ยังไม่ได้ตั้งค่า `GEMINI_API_KEY` ใน Secrets จึงแสดงรายชื่อสรุปเบื้องต้นครับ)*"
    )
    return "\n".join(lines)
