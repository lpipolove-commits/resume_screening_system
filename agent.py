import os
import re

try:
    import streamlit as st
except ImportError:
    st = None

try:
    from google import genai
except ImportError:
    genai = None


def _get_gemini_api_key() -> str:
    """ดึง GEMINI_API_KEY จาก Environment Variable หรือ Streamlit Secrets"""
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key

    if st is not None:
        try:
            secret_key = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
            if secret_key:
                return secret_key
        except Exception:
            pass

    return ""


def _extract_keywords(text: str) -> set[str]:
    """ดึงคำสำคัญ/ทักษะเบื้องต้นจากข้อความ"""
    words = re.findall(r"[A-Za-z0-9+#.-]{2,}|[\u0E00-\u0E7F]{2,}", text.lower())
    stop_words = {
        "และ", "หรือ", "ของ", "ที่", "ใน", "การ", "มี", "ได้", "เป็น", "กับ",
        "สำหรับ", "ตาม", "จาก", "โดย", "ให้", "จะ", "ต้อง", "สามารถ", "ระดับ",
        "ปี", "คน", "งาน", "ทักษะ", "คุณสมบัติ", "ประสบการณ์",
        "the", "and", "for", "with", "from", "that", "this", "have", "are"
    }
    return {w for w in words if w not in stop_words and not w.isdigit()}


def _fallback_rule_based_agent(
    question: str,
    job_title: str,
    job_description: str,
    threshold: float,
    candidates_df,
    selected_candidate_name: str | None = None,
) -> str:
    """โหมดสำรองกรณีไม่มี API Key หรือเรียก LLM ไม่สำเร็จ"""
    q = question.strip()
    q_lower = q.lower()

    if selected_candidate_name and selected_candidate_name in candidates_df["ชื่อไฟล์เรซูเม่"].values:
        target_row = candidates_df[candidates_df["ชื่อไฟล์เรซูเม่"] == selected_candidate_name].iloc[0]
    else:
        target_row = candidates_df.iloc[0]

    target_name = target_row["ชื่อไฟล์เรซูเม่"]
    target_score = float(target_row["Match Score (%)"])
    target_text = target_row.get("full_text", target_row.get("raw_text", ""))

    jd_keywords = _extract_keywords(f"{job_title} {job_description}")
    resume_keywords = _extract_keywords(target_text)
    matched_kw = sorted(jd_keywords & resume_keywords)[:10]
    missing_kw = sorted(jd_keywords - resume_keywords)[:8]
    role_label = job_title.strip() if job_title and job_title.strip() else "ตำแหน่งที่เปิดรับ"

    if any(k in q_lower for k in ["เปรียบเทียบ", "อันดับ", "ทุกคน", "สรุปภาพรวม", "ใครเหมาะ"]):
        lines = [
            f"🤖 **HR Talent Agent (โหมดสำรอง) — สรุปผู้สมัครตำแหน่ง {role_label}**",
            f"- เกณฑ์ขั้นต่ำ: **{threshold}%** | ผ่านเกณฑ์: **{(candidates_df['Match Score (%)'] >= threshold).sum()}/{len(candidates_df)} คน**",
            "",
        ]
        for idx, row in candidates_df.iterrows():
            lines.append(f"{idx + 1}. **{row['ชื่อไฟล์เรซูเม่']}** — `{row['Match Score (%)']}%`")
        return "\n".join(lines)

    if any(k in q_lower for k in ["คำถามสัมภาษณ์", "สัมภาษณ์", "interview"]):
        focus_skills = ", ".join(matched_kw[:3]) if matched_kw else "ทักษะหลักใน JD"
        return (
            f"🤖 **HR Talent Agent (โหมดสำรอง) — คำถามสัมภาษณ์สำหรับ {target_name}** (`{target_score}%`)\n"
            f"1. เล่าประสบการณ์จริงที่ใช้ **{focus_skills}** แก้ปัญหาในงานหรือโปรเจกต์ที่ผ่านมา\n"
            f"2. หากรับผิดชอบงานตำแหน่ง **{role_label}** จะวางแผนรับมือกับความท้าทายแรกอย่างไร?"
        )

    return (
        f"🤖 **HR Talent Agent (โหมดสำรอง) — {target_name}** (`{target_score}%`)\n"
        f"- คำสำคัญที่ตรงกับ JD: {', '.join(f'`{w}`' for w in matched_kw) if matched_kw else 'ยังไม่พบชัดเจน'}\n"
        f"- คำสำคัญใน JD ที่ยังไม่เด่น: {', '.join(f'`{w}`' for w in missing_kw) if missing_kw else 'ไม่พบจุดขาดหายชัดเจน'}"
    )


def run_hr_agent(
    question: str,
    job_title: str,
    job_description: str,
    threshold: float,
    candidates_df,
    selected_candidate_name: str | None = None,
) -> str:
    """เรียก LLM วิเคราะห์เรซูเม่ตามบริบทจริง และ Fallback อัตโนมัติหากไม่ได้ตั้งค่า API Key"""
    q = question.strip()
    if candidates_df is None or candidates_df.empty:
        return (
            "🤖 **HR Talent Agent:** ยังไม่มีข้อมูลเรซูเม่ที่ประมวลผลในระบบครับ "
            "กรุณากรอก Job Description อัปโหลดไฟล์ PDF แล้วกด **ประมวลผลและจัดอันดับ** ก่อนนะครับ"
        )

    api_key = _get_gemini_api_key()
    if not api_key or genai is None:
        return _fallback_rule_based_agent(
            q, job_title, job_description, threshold, candidates_df, selected_candidate_name
        )

    if selected_candidate_name and selected_candidate_name in candidates_df["ชื่อไฟล์เรซูเม่"].values:
        target_row = candidates_df[candidates_df["ชื่อไฟล์เรซูเม่"] == selected_candidate_name].iloc[0]
    else:
        target_row = candidates_df.iloc[0]

    target_name = target_row["ชื่อไฟล์เรซูเม่"]
    target_score = float(target_row["Match Score (%)"])
    target_text = str(target_row.get("full_text", target_row.get("raw_text", "")))[:3500]

    ranking_summary = "\n".join(
        f"- อันดับ {i + 1}: {r['ชื่อไฟล์เรซูเม่']} (Match Score: {r['Match Score (%)']}%)"
        for i, (_, r) in enumerate(candidates_df.iterrows())
    )

    prompt = f"""
คุณคือ HR Talent Agent ผู้ช่วยฝ่ายทรัพยากรบุคคล วิเคราะห์ข้อมูลอย่างตรงไปตรงมา กระชับ และอ้างอิงเฉพาะข้อมูลที่มีให้
ห้ามแต่งข้อมูลหรือสมมติข้อเท็จจริงที่ไม่มีในเรซูเม่หรือ JD

[ตำแหน่งงาน]: {job_title or "ไม่ได้ระบุ"}
[เกณฑ์คะแนนขั้นต่ำ]: {threshold}%
[Job Description]:
{job_description or "ไม่ได้ระบุ"}

[สรุปอันดับผู้สมัครทั้งหมด]:
{ranking_summary}

[ผู้สมัครที่กำลังโฟกัส]: {target_name} (Match Score: {target_score}%)
[เนื้อหาเรซูเม่ของผู้สมัครที่โฟกัส]:
{target_text}

[คำถามจาก HR]:
{q}

ตอบเป็นภาษาไทย จัดรูปแบบให้อ่านง่ายด้วยหัวข้อหรือ bullet points
""".strip()

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
        )
        if response and response.text:
            return response.text.strip()
    except Exception as e:
        fallback_msg = _fallback_rule_based_agent(
            q, job_title, job_description, threshold, candidates_df, selected_candidate_name
        )
        return f"{fallback_msg}\n\n*(หมายเหตุ: เรียกใช้ LLM ไม่สำเร็จชั่วคราว — {e})*"

    return _fallback_rule_based_agent(
        q, job_title, job_description, threshold, candidates_df, selected_candidate_name
    )