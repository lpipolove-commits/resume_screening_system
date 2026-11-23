from io import BytesIO
import os
import streamlit as st
from fpdf import FPDF

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

from agent import ask_career_agent, ask_hr_agent
from storage import (
    clear_all_candidates,
    delete_candidate,
    load_candidates,
    save_candidate,
)

st.set_page_config(
    page_title="AI Resume Screening & Career Coaching",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .stApp {
        background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
    }
    .hero-card {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 55%, #2563eb 100%);
        color: #ffffff;
        padding: 2rem 2.25rem;
        border-radius: 20px;
        box-shadow: 0 14px 30px -10px rgba(30, 58, 138, 0.35);
        margin-bottom: 1.5rem;
    }
    .hero-badge {
        display: inline-block;
        background: rgba(255, 255, 255, 0.16);
        border: 1px solid rgba(255, 255, 255, 0.25);
        color: #e0f2fe;
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 600;
        margin-bottom: 0.75rem;
    }
    .hero-title {
        font-size: 2rem;
        font-weight: 800;
        margin: 0 0 0.5rem 0;
        line-height: 1.25;
    }
    .hero-subtitle {
        font-size: 1rem;
        color: #dbeafe;
        margin: 0;
        max-width: 780px;
        line-height: 1.6;
    }
    .feature-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 1.35rem 1.5rem;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
        height: 100%;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .feature-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
    }
    .feature-icon {
        font-size: 1.6rem;
        margin-bottom: 0.5rem;
    }
    .feature-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.35rem;
    }
    .feature-desc {
        font-size: 0.92rem;
        color: #475569;
        line-height: 1.55;
        margin: 0;
    }
    div[data-testid="stExpander"] {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03);
        margin-bottom: 0.6rem;
    }
    div[data-testid="stExpander"] summary {
        font-weight: 600;
        color: #0f172a;
    }
    .stButton > button, .stDownloadButton > button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.15s ease;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

DEMO_USERS = {
    "candidate@demo.com": {
        "password": os.environ.get("CANDIDATE_PASSWORD", "1234"),
        "role": "candidate",
        "display_name": "บัญชีผู้หางาน (Candidate)",
    },
    "hr@demo.com": {
        "password": os.environ.get("HR_PASSWORD", "admin123"),
        "role": "hr",
        "display_name": "บัญชีฝ่ายบุคคล (HR)",
    },
}


def _extract_pdf_text(uploaded_file) -> str:
    if PdfReader is None:
        raise RuntimeError("ยังไม่ได้ติดตั้ง pypdf (รัน: pip install pypdf)")
    reader = PdfReader(BytesIO(uploaded_file.getvalue()))
    pages_text = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        if extracted.strip():
            pages_text.append(extracted.strip())
    return "\n\n".join(pages_text)


def _find_thai_font() -> str | None:
    candidates_fonts = [
        r"C:\Windows\Fonts\Tahoma.ttf",
        r"C:\Windows\Fonts\angsana.ttc",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for path in candidates_fonts:
        if os.path.exists(path):
            return path
    return None


def _build_candidate_pdf(cand: dict) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    font_path = _find_thai_font()
    if font_path:
        try:
            pdf.add_font("CustomFont", "", font_path, uni=True)
            font_name = "CustomFont"
        except Exception:
            font_name = "Helvetica"
    else:
        font_name = "Helvetica"

    def _safe_text(text: str) -> str:
        s = str(text or "-")
        if font_name == "Helvetica":
            return s.encode("latin-1", "replace").decode("latin-1")
        return s

    pdf.set_font(font_name, size=16)
    pdf.cell(0, 10, _safe_text("Candidate Resume & Profile Report"), ln=True)
    pdf.ln(2)

    pdf.set_font(font_name, size=11)
    pdf.cell(0, 8, _safe_text(f"Name: {cand.get('name', '-')}"), ln=True)
    pdf.cell(0, 8, _safe_text(f"Target Role: {cand.get('target_role', '-')}"), ln=True)
    pdf.cell(0, 8, _safe_text(f"Contact: {cand.get('contact', '-')}"), ln=True)
    pdf.ln(4)

    pdf.set_font(font_name, size=12)
    pdf.cell(0, 8, _safe_text("Responsibilities & Key Experience:"), ln=True)
    pdf.set_font(font_name, size=10)
    pdf.multi_cell(0, 6, _safe_text(cand.get("responsibilities", "-")))
    pdf.ln(4)

    pdf.set_font(font_name, size=12)
    pdf.cell(0, 8, _safe_text("Resume Content:"), ln=True)
    pdf.set_font(font_name, size=10)
    pdf.multi_cell(0, 6, _safe_text(cand.get("resume_text", "-")))

    output = pdf.output(dest="S")
    if isinstance(output, (bytes, bytearray)):
        return bytes(output)
    return output.encode("latin-1")


def _init_session_state():
    all_candidates = load_candidates()
    if "auth_user" not in st.session_state:
        st.session_state["auth_user"] = None
    if "current_candidate" not in st.session_state and all_candidates:
        st.session_state["current_candidate"] = all_candidates[0]
    if "candidate_chat_history" not in st.session_state:
        st.session_state["candidate_chat_history"] = []
    if "hr_chat_history" not in st.session_state:
        st.session_state["hr_chat_history"] = []
    if "pdf_extracted_text" not in st.session_state:
        st.session_state["pdf_extracted_text"] = ""
    if "last_uploaded_pdf_name" not in st.session_state:
        st.session_state["last_uploaded_pdf_name"] = ""
    if "form_nonce" not in st.session_state:
        st.session_state["form_nonce"] = 0
    if "form_initialized_nonce" not in st.session_state:
        st.session_state["form_initialized_nonce"] = -1


def _login_as(role: str):
    if role == "candidate":
        st.session_state["auth_user"] = {
            "email": "candidate@demo.com",
            "role": "candidate",
            "display_name": "บัญชีผู้หางาน (Candidate)",
        }
    else:
        st.session_state["auth_user"] = {
            "email": "hr@demo.com",
            "role": "hr",
            "display_name": "บัญชีฝ่ายบุคคล (HR)",
        }
    st.rerun()


def _render_login_sidebar():
    with st.sidebar:
        st.markdown("### 🔐 ระบบเข้าสู่ระบบ")
        auth_user = st.session_state.get("auth_user")

        if auth_user:
            role_label = "ผู้หางาน (Candidate)" if auth_user["role"] == "candidate" else "ฝ่ายบุคคล (HR)"
            st.success(f"**{auth_user['display_name']}**")
            st.caption(f"บทบาท: {role_label} · `{auth_user['email']}`")

            if st.button("🚪 ออกจากระบบ", use_container_width=True):
                st.session_state["auth_user"] = None
                st.rerun()
            return

        email = st.text_input("อีเมลบัญชี", placeholder="candidate@demo.com หรือ hr@demo.com")
        password = st.text_input("รหัสผ่าน", type="password", placeholder="กรอกรหัสผ่าน")

        if st.button("เข้าสู่ระบบ", type="primary", use_container_width=True):
            user_rec = DEMO_USERS.get(email.strip().lower())
            if user_rec and password == user_rec["password"]:
                st.session_state["auth_user"] = {
                    "email": email.strip().lower(),
                    "role": user_rec["role"],
                    "display_name": user_rec["display_name"],
                }
                st.rerun()
            else:
                st.error("อีเมลหรือรหัสผ่านไม่ถูกต้องครับ")

        st.divider()
        st.caption("⚡ ล็อกอินด่วนสำหรับทดสอบ")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("ผู้สมัคร", use_container_width=True, key="sidebar_login_cand"):
                _login_as("candidate")
        with col_b:
            if st.button("HR", use_container_width=True, key="sidebar_login_hr"):
                _login_as("hr")


def _render_landing_screen():
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-badge">✨ AI-Powered Talent & Career Platform</div>
            <div class="hero-title">💼 AI Resume Screening & Career Coaching</div>
            <p class="hero-subtitle">
                ยกระดับการสมัครงานและการคัดกรองบุคลากรด้วย AI อัจฉริยะ อัปโหลดเรซูเม่ PDF ได้ทันที
                พร้อมโค้ชแนะแนวอาชีพส่วนตัวสำหรับผู้หางาน และแดชบอร์ดค้นหาผู้สมัคร + ส่งออก PDF สำหรับทีม HR
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            """
            <div class="feature-card">
                <div class="feature-icon">📄</div>
                <div class="feature-title">Smart PDF Resume Reader</div>
                <p class="feature-desc">อัปโหลดไฟล์เรซูเม่ PDF และดึงข้อความเข้าสู่ระบบอัตโนมัติ แก้ไขและบันทึกโปรไฟล์ได้ง่ายในคลิกเดียว</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class="feature-card">
                <div class="feature-icon">💬</div>
                <div class="feature-title">AI Career Coach</div>
                <p class="feature-desc">วิเคราะห์จุดแข็ง จุดที่ควรปรับปรุง แนะนำการเขียนผลงานเชิงตัวเลข และเตรียมพร้อมก่อนสัมภาษณ์</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            """
            <div class="feature-card">
                <div class="feature-icon">📊</div>
                <div class="feature-title">HR Talent Hub & PDF Export</div>
                <p class="feature-desc">ค้นหาผู้สมัครตามทักษะหรือตำแหน่ง ให้ AI ช่วยคัดเลือกผู้สมัคร และดาวน์โหลดโปรไฟล์เป็น PDF ได้ทันที</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")
    st.markdown("#### 🚀 เริ่มต้นใช้งานด่วน")
    b1, b2, _ = st.columns([1.4, 1.4, 3.2])
    with b1:
        if st.button("🧑‍💼 เข้าใช้งานฝั่งผู้หางาน", type="primary", use_container_width=True, key="hero_btn_cand"):
            _login_as("candidate")
    with b2:
        if st.button("📊 เข้าใช้งานฝั่ง HR", use_container_width=True, key="hero_btn_hr"):
            _login_as("hr")


def _render_candidate_portal():
    st.markdown("## 🧑‍💼 Candidate Portal & AI Career Coach")

    current_cand = st.session_state.get("current_candidate")
    if current_cand:
        m1, m2 = st.columns(2)
        with m1:
            st.metric("ผู้สมัครปัจจุบัน", current_cand.get("name", "-"))
        with m2:
            st.metric("ตำแหน่งที่สนใจ", current_cand.get("target_role", "-"))

    nonce = st.session_state["form_nonce"]
    k_name = f"cand_name_{nonce}"
    k_contact = f"cand_contact_{nonce}"
    k_role = f"cand_role_{nonce}"
    k_resp = f"cand_resp_{nonce}"
    k_resume = f"cand_resume_{nonce}"

    if st.session_state["form_initialized_nonce"] != nonce:
        if nonce == 0 and current_cand:
            st.session_state[k_name] = current_cand.get("name", "")
            st.session_state[k_contact] = current_cand.get("contact", "")
            st.session_state[k_role] = current_cand.get("target_role", "")
            st.session_state[k_resp] = current_cand.get("responsibilities", "")
            st.session_state[k_resume] = current_cand.get("resume_text", "")
        else:
            st.session_state[k_name] = ""
            st.session_state[k_contact] = ""
            st.session_state[k_role] = ""
            st.session_state[k_resp] = ""
            st.session_state[k_resume] = ""
        st.session_state["form_initialized_nonce"] = nonce

    with st.expander("📝 แก้ไข / อัปเดตข้อมูลเรซูเม่และโปรไฟล์", expanded=False):
        if st.button("🔄 โหลดข้อมูลผู้สมัครปัจจุบันมาแก้ไข", key=f"load_current_btn_{nonce}"):
            if current_cand:
                st.session_state[k_name] = current_cand.get("name", "")
                st.session_state[k_contact] = current_cand.get("contact", "")
                st.session_state[k_role] = current_cand.get("target_role", "")
                st.session_state[k_resp] = current_cand.get("responsibilities", "")
                st.session_state[k_resume] = current_cand.get("resume_text", "")
                st.rerun()

        uploaded_pdf = st.file_uploader(
            "อัปโหลดไฟล์เรซูเม่ (PDF) เพื่อดึงข้อความอัตโนมัติ",
            type=["pdf"],
            key=f"candidate_pdf_uploader_{nonce}",
        )

        # เมื่อมีการใส่ไฟล์ PDF ใหม่ ให้ล้างข้อความแชท AI เดิมออกทันที
        if uploaded_pdf is not None and uploaded_pdf.name != st.session_state["last_uploaded_pdf_name"]:
            try:
                extracted_text = _extract_pdf_text(uploaded_pdf)
                st.session_state["last_uploaded_pdf_name"] = uploaded_pdf.name
                st.session_state["pdf_extracted_text"] = extracted_text
                st.session_state["candidate_chat_history"] = []  # ล้างข้อความ AI เดิมเมื่อเปลี่ยนไฟล์
                if extracted_text:
                    st.session_state[k_resume] = extracted_text
                    st.success(f"ดึงข้อความจากไฟล์ **{uploaded_pdf.name}** สำเร็จแล้วครับ (รีเซ็ตแชท AI สำหรับคนใหม่)")
                    st.rerun()
                else:
                    st.warning(
                        "อ่านไฟล์ PDF ได้ แต่ไม่พบข้อความตัวอักษร (อาจเป็น PDF แบบรูปภาพสแกน) สามารถพิมพ์หรือวางข้อความเพิ่มเติมเองได้ครับ"
                    )
            except Exception as e:
                st.error(f"ไม่สามารถอ่านไฟล์ PDF ได้: {e}")

        with st.form(f"candidate_form_{nonce}"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("ชื่อ-นามสกุล", key=k_name)
                contact = st.text_input("ข้อมูลติดต่อ (อีเมล / โทรศัพท์)", key=k_contact)
            with col2:
                target_role = st.text_input("ตำแหน่งที่สนใจ", key=k_role)
                responsibilities = st.text_area(
                    "หน้าที่และความรับผิดชอบ / ประสบการณ์สำคัญ",
                    height=100,
                    key=k_resp,
                )

            resume_text = st.text_area(
                "เนื้อหาเรซูเม่ (วางข้อความเรซูเม่ที่นี่ หรืออัปโหลด PDF ด้านบน)",
                height=180,
                key=k_resume,
            )

            submitted = st.form_submit_button("💾 บันทึกโปรไฟล์และเรซูเม่", type="primary")
            if submitted:
                saved_profile = save_candidate(
                    name.strip(),
                    contact.strip(),
                    target_role.strip(),
                    responsibilities.strip(),
                    resume_text.strip(),
                )
                st.session_state["current_candidate"] = saved_profile
                st.session_state["pdf_extracted_text"] = ""
                st.session_state["last_uploaded_pdf_name"] = ""
                st.session_state["candidate_chat_history"] = []  # ล้างข้อความ AI เดิมเมื่อบันทึกข้อมูลคนใหม่

                next_nonce = nonce + 1
                st.session_state["form_nonce"] = next_nonce
                st.session_state[f"cand_name_{next_nonce}"] = ""
                st.session_state[f"cand_contact_{next_nonce}"] = ""
                st.session_state[f"cand_role_{next_nonce}"] = ""
                st.session_state[f"cand_resp_{next_nonce}"] = ""
                st.session_state[f"cand_resume_{next_nonce}"] = ""
                st.session_state["form_initialized_nonce"] = next_nonce

                st.success("บันทึกข้อมูลผู้สมัครเรียบร้อยแล้วครับ")
                st.rerun()

    st.markdown("### 💬 คุยกับ AI Career Coach")

    # เพิ่มปุ่มกดรีเซ็ตข้อความแชทด้วยตนเอง
    c_head, c_clear = st.columns([5, 1])
    with c_clear:
        if st.session_state["candidate_chat_history"]:
            if st.button("🗑️ ล้างแชท", key="clear_chat_btn", use_container_width=True):
                st.session_state["candidate_chat_history"] = []
                st.rerun()

    active_profile = st.session_state.get("current_candidate") or {
        "name": "-",
        "target_role": "-",
        "responsibilities": "-",
        "resume_text": "",
    }

    for msg in st.session_state["candidate_chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_msg = st.chat_input(
        "ถาม AI Career Coach (เช่น โปรไฟล์นี้ควรปรับจุดไหน หรือควรเตรียมตัวสัมภาษณ์อย่างไร)..."
    )
    if user_msg:
        st.session_state["candidate_chat_history"].append({"role": "user", "content": user_msg})
        with st.chat_message("user"):
            st.markdown(user_msg)

        with st.chat_message("assistant"):
            with st.spinner("AI กำลังวิเคราะห์ข้อมูลและคิดคำแนะนำ..."):
                reply = ask_career_agent(active_profile, user_msg)
            st.markdown(reply)

        st.session_state["candidate_chat_history"].append({"role": "assistant", "content": reply})


def _render_hr_dashboard():
    st.markdown("## 📊 HR Dashboard & Talent Search")

    candidates = load_candidates()
    top_col1, top_col2 = st.columns([4, 1])
    with top_col1:
        search_query = st.text_input(
            "ค้นหาผู้สมัคร (ชื่อ, ตำแหน่ง, ทักษะ หรือคีย์เวิร์ดในเรซูเม่)",
            placeholder="เช่น Data Analyst, Python, SQL, การตลาด...",
        )
    with top_col2:
        st.write("")
        st.write("")
        if st.button("🧹 ล้างทั้งหมด", use_container_width=True, key="hr_clear_all_btn"):
            clear_all_candidates()
            st.session_state.pop("current_candidate", None)
            st.rerun()

    if search_query.strip():
        q = search_query.strip().lower()
        filtered_candidates = [
            c
            for c in candidates
            if q
            in f"{c.get('name', '')} {c.get('target_role', '')} {c.get('contact', '')} {c.get('responsibilities', '')} {c.get('resume_text', '')}".lower()
        ]
    else:
        filtered_candidates = candidates

    st.metric("จำนวนผู้สมัครที่แสดง", f"{len(filtered_candidates)} / {len(candidates)} รายการ")

    for idx, cand in enumerate(filtered_candidates):
        cand_id = str(cand.get("id", idx))
        with st.expander(
            f"👤 {cand.get('name', '-')} — 🎯 {cand.get('target_role', '-')} (รหัส: {cand_id[:8]})"
        ):
            st.write(f"**ข้อมูลติดต่อ:** {cand.get('contact', '-')}")
            st.write(f"**หน้าที่และความรับผิดชอบ:** {cand.get('responsibilities', '-')}")
            st.text_area(
                "Resume Text",
                cand.get("resume_text", ""),
                height=150,
                disabled=True,
                key=f"hr_resume_{cand_id}_{idx}",
            )

            col_dl, col_del = st.columns([3, 1])
            with col_dl:
                pdf_bytes = _build_candidate_pdf(cand)
                safe_filename = f"resume_{cand.get('name', 'candidate').replace(' ', '_')}_{cand_id[:6]}.pdf"
                st.download_button(
                    label="📄 ดาวน์โหลดโปรไฟล์ & เรซูเม่ (PDF)",
                    data=pdf_bytes,
                    file_name=safe_filename,
                    mime="application/pdf",
                    key=f"hr_pdf_dl_{cand_id}_{idx}",
                )
            with col_del:
                if st.button("🗑️ ลบรายชื่อนี้", key=f"hr_del_{cand_id}_{idx}", use_container_width=True):
                    delete_candidate(cand_id)
                    st.rerun()

    st.divider()
    st.markdown("### 🤖 AI HR Talent Assistant")

    for msg in st.session_state["hr_chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    hr_prompt = st.chat_input(
        "สั่งงาน HR Agent (เช่น ช่วยคัดผู้สมัครที่เหมาะกับ Data Analyst พร้อมจุดที่ควรสัมภาษณ์)..."
    )
    if hr_prompt:
        st.session_state["hr_chat_history"].append({"role": "user", "content": hr_prompt})
        with st.chat_message("user"):
            st.markdown(hr_prompt)

        with st.chat_message("assistant"):
            with st.spinner("AI กำลังวิเคราะห์รายชื่อผู้สมัคร..."):
                hr_reply = ask_hr_agent(candidates, hr_prompt)
            st.markdown(hr_reply)

        st.session_state["hr_chat_history"].append({"role": "assistant", "content": hr_reply})


def main():
    _init_session_state()
    _render_login_sidebar()

    auth_user = st.session_state.get("auth_user")
    if not auth_user:
        _render_landing_screen()
        return

    if auth_user["role"] == "candidate":
        _render_candidate_portal()
    elif auth_user["role"] == "hr":
        _render_hr_dashboard()


if __name__ == "__main__":
    main()
