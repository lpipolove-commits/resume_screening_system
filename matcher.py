from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# โหลดโมเดล Sentence Transformers
model = SentenceTransformer('all-MiniLM-L6-v2')

def calculate_match_score(job_description: str, resume_text: str) -> float:
    """
    แปลงข้อความเป็น High-dimensional Vector แล้วคำนวณ Cosine Similarity
    แปลงค่าออกมาเป็นคะแนนร้อยละ (0 - 100%)
    """
    if not job_description.strip() or not resume_text.strip():
        return 0.0

    embeddings = model.encode([job_description, resume_text])
    similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
    
    # แปลง similarity scale จาก [-1, 1] หรือ [0, 1] เป็นเปอร์เซ็นต์
    score = max(0.0, float(similarity)) * 100
    return round(score, 2)