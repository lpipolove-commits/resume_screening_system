import streamlit as st
import pandas as pd
from parser import extract_text_from_pdf
from agent import run_hr_agent
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# 1. ตั้งค่าหน้าเว็บ
st.set_page_config(
    page_title="AI Resume Screening & Ranking System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. CSS Dark Mode สไตล์ Enterprise Dashboard
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Prompt:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', 'Prompt', sans-serif;
    color: #f1f5f9;
}

.stApp {
    background-color: #0b0f19 !important;
    color: #f8fafc !important;
}

h1, h2, h3, h4, h5, h6, p, label, span {
    color: #f8fafc !important;
}

section[data-testid="stSidebar"] {
    background-color: #111827 !important;
    border-right: 1px solid #1f2937 !important;
}

/* Stat Cards ด้านบน 4 ช่อง */
.stat-card-container {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 20px;
}

.stat-card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 14px;
    padding: 16px 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
}

.stat-title {
    font-size: 0.85rem;
    color: #94a3b8 !important;
    margin-bottom: 4px;
}

.stat-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: #38bdf8 !important;
}

.stat-icon {
    font-size: 1.5rem;
    padding: 8px 12px;
    border-radius: 10px;
    background: rgba(56, 189, 248, 0.1);
}

/* กล่อง Panel สีดำ */
.panel-box {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    margin-bottom: 1.5rem;
}

/* Donut Score Card */
.donut-score-box {
    text-align: center;
    padding: 20px;
    background: #131b2e;
    border-radius: 14px;
    border: 1px solid #1e293b;
    margin-bottom: 16px;
}

.donut-circle {
    width: 95px;
    height: 95px;
    border-radius: 50%;
    border: 5px solid #06b6d4;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.7rem;
    font-weight: 700;
    color: #38bdf8 !important;
    margin: 0 auto 12px auto;
    background: rgba(6, 182, 212, 0.08);
}

.agent-badge {
    display: inline-block;
    font-size: 0.75rem;
    padding: 3px 10px;
    border-radius: 999px;
    background: rgba(56, 189, 248, 0.15);
    color: #38bdf8 !important;
    border: 1px solid rgba(56, 189, 248, 0.35);
    margin-bottom: 10px;
}

/* ปุ่มกดหลักแบบสีนีออน */
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.7rem 1.2rem !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4) !important;
}

div.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.6) !important;
}
</style>
""", unsafe_allow_html=True)

# 3. โหลดโมเดล Sentence Transformers
@st.cache_resource
def load_nlp_model():
    return SentenceTransformer('all-MiniLM-L6-v2')

model = load_nlp_model()

# เตรียม State สำหรับแชทของ Agent AI
if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = [
        {
            "role": "assistant",
            "content": (
                "สวัสดีครับ ผมคือ **HR Talent Agent** ผู้ช่วยวิเคราะห์เรซูเม่และช่วยตัดสินใจคัดเลือกผู้สมัคร "
                "คุณสามารถถามเกี่ยวกับผู้สมัครที่เลือก เปรียบเทียบผู้สมัครทุกคน หรือให้ช่วยร่างคำถามสัมภาษณ์ได้เลยครับ"
            ),
        }
    ]

# 4. Sidebar เมนูระบบ
with st.sidebar:
    st.markdown("### 🤖 **ระบบคัดกรองเรซูเม่ AI**")
    st.caption("Human Capital Analytics System")
    st.markdown("---")
    department = st.selectbox(
        "แผนกที่รับสมัคร:",
        ["เทคโนโลยีสารสนเทศ (IT & MIS)", "การตลาดดิจิทัล (Marketing)", "การเงินและบัญชี (Finance)", "ทรัพยากรบุคคล (HR)"]
    )
    threshold = st.slider("เกณฑ์คะแนนเรียกสัมภาษณ์ขั้นต่ำ (%):", min_value=50, max_value=90, value=70, step=5)
    st.markdown("---")
    st.caption("💡 **MIS Note:** ระบบใช้ Cosine Similarity คำนวณความสอดคล้องระหว่างข้อความ Job Description และเนื้อหาในเรซูเม่ PDF ร่วมกับ HR Talent Agent")

# 5. ส่วนหัวของหน้าเว็บ
top_col1, top_col2 = st.columns([2.5, 1])
with top_col1:
    st.markdown("## **คัดกรองและจัดอันดับเรซูเม่ (Resume Screening & Ranking)**")
with top_col2:
    st.markdown(f"<div style='text-align: right; padding-top: 10px; color: #94a3b8;'>แผนก: <strong style='color:#38bdf8;'>{department}</strong></div>", unsafe_allow_html=True)

# คำนวณค่าจริงของ Metrics
total_uploaded = len(st.session_state.get("uploaded_cache", []))
if "results_df" in st.session_state and not st.session_state["results_df"].empty:
    df_calc = st.session_state["results_df"]
    processed_count = len(df_calc)
    interview_count = len(df_calc[df_calc["Invite Interview"] == True])
    passed_count = len(df_calc[df_calc["Match Score (%)"] >= threshold])
else:
    processed_count = 0
    interview_count = 0
    passed_count = 0

# 6. แถบสถิติ Stat Cards 4 ช่อง
st.markdown(f"""
<div class="stat-card-container">
    <div class="stat-card">
        <div>
            <div class="stat-title">เรซูเม่ที่อัปโหลด</div>
            <div class="stat-value">{total_uploaded}</div>
        </div>
        <div class="stat-icon">📁</div>
    </div>
    <div class="stat-card">
        <div>
            <div class="stat-title">ประมวลผลแล้ว</div>
            <div class="stat-value">{processed_count}</div>
        </div>
        <div class="stat-icon">⚡</div>
    </div>
    <div class="stat-card">
        <div>
            <div class="stat-title">เลือกเรียกสัมภาษณ์</div>
            <div class="stat-value">{interview_count}</div>
        </div>
        <div class="stat-icon">📅</div>
    </div>
    <div class="stat-card">
        <div>
            <div class="stat-title">ผ่านเกณฑ์แนะนำ (≥{threshold}%)</div>
            <div class="stat-value">{passed_count}</div>
        </div>
        <div class="stat-icon">🎯</div>
    </div>
</div>
""", unsafe_allow_html=True)

# 7. แบ่ง Layout: ซ้าย (Input & Table) | ขวา (Candidate Deep Dive + AI Agent Chat)
col_main, col_detail = st.columns([1.55, 1.15], gap="medium")

selected_file_for_agent = None

with col_main:
    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    st.markdown("#### 📝 1. กำหนดรายละเอียดงาน (Job Description)")
    job_title = st.text_input("ชื่อตำแหน่งงาน:", placeholder="เช่น Data Analyst / Software Engineer / MIS Officer")
    job_description = st.text_area(
        "รายละเอียดคุณสมบัติที่ต้องการ (Job Requirements):",
        height=130,
        placeholder="ระบุทักษะ เช่น Python, SQL, Dashboard Visualization, ประสบการณ์ 1-2 ปี..."
    )

    st.markdown("#### 📂 2. อัปโหลดเรซูเม่ผู้สมัคร")
    uploaded_files = st.file_uploader(
        "เลือกไฟล์ PDF เรซูเม่ (สามารถลากมาวางพร้อมกันหลายไฟล์ได้):",
        type=["pdf"],
        accept_multiple_files=True
    )

    if uploaded_files:
        st.session_state["uploaded_cache"] = uploaded_files

    process_btn = st.button("🚀 ประมวลผลและจัดอันดับ (Screen Resumes)", type="primary", use_container_width=True)

    # การประมวลผลจริงเมื่อกดปุ่ม
    if process_btn:
        if not job_description.strip():
            st.warning("⚠️ กรุณากรอกรายละเอียดงาน (Job Description) ก่อนทำการประมวลผล")
        elif not uploaded_files:
            st.warning("⚠️ กรุณาอัปโหลดไฟล์เรซูโม่อย่างน้อย 1 ไฟล์")
        else:
            with st.spinner("AI กำลังอ่านไฟล์ PDF และเปรียบเทียบเชิงเวกเตอร์..."):
                jd_embedding = model.encode([job_description])
                candidates_data = []

                for file in uploaded_files:
                    resume_text = extract_text_from_pdf(file)
                    if resume_text.strip():
                        resume_embedding = model.encode([resume_text])
                        similarity = cosine_similarity(jd_embedding, resume_embedding)[0][0]
                        score = round(max(0.0, float(similarity)) * 100, 2)
                    else:
                        score = 0.0

                    status = "🌟 ผ่านเกณฑ์" if score >= threshold else "⏳ พิจารณาเพิ่มเติม"

                    candidates_data.append({
                        "ชื่อไฟล์เรซูเม่": file.name,
                        "Match Score (%)": score,
                        "ผลการประเมิน": status,
                        "Invite Interview": score >= threshold,
                        "raw_text": resume_text[:350] + ("..." if len(resume_text) > 350 else ""),
                        "full_text": resume_text
                    })

                df = pd.DataFrame(candidates_data)
                df = df.sort_values(by="Match Score (%)", ascending=False).reset_index(drop=True)
                st.session_state["results_df"] = df

    # แสดงตารางผลลัพธ์จริง
    if "results_df" in st.session_state and not st.session_state["results_df"].empty:
        st.markdown("---")
        st.markdown("#### 🏆 ผลการจัดอันดับผู้สมัคร (Candidate Leaderboard)")

        edited_df = st.data_editor(
            st.session_state["results_df"],
            column_config={
                "Match Score (%)": st.column_config.ProgressColumn(
                    "AI Match Score",
                    format="%.1f%%",
                    min_value=0,
                    max_value=100,
                ),
                "Invite Interview": st.column_config.CheckboxColumn(
                    "เลือกสัมภาษณ์",
                    default=False,
                ),
                "raw_text": None,
                "full_text": None
            },
            disabled=["ชื่อไฟล์เรซูเม่", "Match Score (%)", "ผลการประเมิน"],
            hide_index=True,
            use_container_width=True
        )
        st.session_state["results_df"] = edited_df

    st.markdown('</div>', unsafe_allow_html=True)

with col_detail:
    # กล่องที่ 1: AI Candidate Deep Dive
    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    st.markdown("#### 🎯 ข้อมูลวิเคราะห์เชิงลึก (AI Candidate Deep Dive)")

    if "results_df" in st.session_state and not st.session_state["results_df"].empty:
        current_data = st.session_state["results_df"]
        candidate_list = current_data["ชื่อไฟล์เรซูเม่"].tolist()

        selected_file = st.selectbox("เลือกผู้สมัครที่ต้องการดูรายละเอียด:", candidate_list)
        selected_file_for_agent = selected_file
        selected_row = current_data[current_data["ชื่อไฟล์เรซูเม่"] == selected_file].iloc[0]

        score_val = selected_row["Match Score (%)"]

        st.markdown(f"""
        <div class="donut-score-box">
            <div class="donut-circle">{score_val}%</div>
            <div style="font-weight:600; font-size:1.05rem; color:#f8fafc;">คะแนนความเข้ากันได้ (Match Score)</div>
            <div style="font-size:0.85rem; color:#94a3b8; margin-top:4px;">ไฟล์: <strong>{selected_file}</strong></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("##### 📄 ข้อความตัวอย่างที่สกัดได้จากเรซูเม่:")
        st.text_area("", value=selected_row["raw_text"], height=130, disabled=True)

        st.markdown(f"<div style='margin-top:8px; font-size:0.85rem; color:#94a3b8;'>ระดับความพร้อมเทียบกับคุณสมบัติ: <strong>{score_val}%</strong></div>", unsafe_allow_html=True)
        st.progress(score_val / 100.0)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📧 ส่งหนังสือเชิญสัมภาษณ์ผู้สมัครรายนี้", type="primary", use_container_width=True):
            st.toast(f"ส่งคำเชิญไปยังผู้สมัคร {selected_file} เรียบร้อยแล้ว!", icon="✅")
    else:
        st.info("💡 อัปโหลดไฟล์ PDF และกดประมวลผลทางด้านซ้ายเพื่อดูคะแนนและรายละเอียดของผู้สมัครในหน้านี้")

    st.markdown('</div>', unsafe_allow_html=True)

    # กล่องที่ 2: AI Talent Agent Chat
    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    st.markdown('<span class="agent-badge">AGENTIC HR ASSISTANT</span>', unsafe_allow_html=True)
    st.markdown("#### 🤖 คุยกับ AI เรื่อง Resume & การคัดเลือก")

    results_for_agent = st.session_state.get("results_df", pd.DataFrame())

    # ปุ่มคำสั่งด่วนสำหรับ Agent
    q_col1, q_col2, q_col3 = st.columns(3)
    quick_prompt = None
    if q_col1.button("🔍 วิเคราะห์รายคน", use_container_width=True):
        quick_prompt = "ช่วยวิเคราะห์จุดแข็ง จุดอ่อน และความเหมาะสมของผู้สมัครที่เลือกเทียบกับ JD"
    if q_col2.button("📊 เปรียบเทียบทุกคน", use_container_width=True):
        quick_prompt = "ช่วยเปรียบเทียบอันดับและสรุปภาพรวมของผู้สมัครทุกคน"
    if q_col3.button("🎤 คำถามสัมภาษณ์", use_container_width=True):
        quick_prompt = "ช่วยสร้างคำถามสัมภาษณ์เฉพาะสำหรับผู้สมัครที่เลือก"

    user_prompt = st.chat_input("พิมพ์ถาม AI เกี่ยวกับ Resume, ทักษะ, การเปรียบเทียบ หรือคำถามสัมภาษณ์...")
    active_prompt = quick_prompt or user_prompt

    if active_prompt:
        st.session_state["chat_messages"].append({"role": "user", "content": active_prompt})
        agent_reply = run_hr_agent(
            question=active_prompt,
            job_title=job_title,
            job_description=job_description,
            threshold=threshold,
            candidates_df=results_for_agent,
            selected_candidate_name=selected_file_for_agent,
        )
        st.session_state["chat_messages"].append({"role": "assistant", "content": agent_reply})

    # แสดงประวัติการคุย (จำกัดข้อความล่าสุดให้อ่านง่าย)
    chat_container = st.container(height=280)
    with chat_container:
        for msg in st.session_state["chat_messages"][-8:]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if st.button("🗑️ ล้างประวัติการคุยกับ Agent", use_container_width=True):
        st.session_state["chat_messages"] = st.session_state["chat_messages"][:1]
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)