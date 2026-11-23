import glob
import json
import os
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_FILE = os.path.join(BASE_DIR, "candidates.json")


def _find_candidate_files() -> list[str]:
    """ค้นหาไฟล์ json ในโฟลเดอร์ที่เก็บข้อมูลผู้สมัคร"""
    found = []
    for path in glob.glob(os.path.join(BASE_DIR, "*.json")):
        base = os.path.basename(path).lower()
        if "secret" in base or "config" in base or "package" in base:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and (
                len(data) == 0 or (isinstance(data[0], dict) and ("name" in data[0] or "resume_text" in data[0]))
            ):
                found.append(path)
        except Exception:
            continue
    return found or [DEFAULT_DATA_FILE]


def load_candidates() -> list[dict]:
    files = _find_candidate_files()
    merged = []
    seen_ids = set()

    for path in files:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        cid = str(item.get("id") or uuid.uuid4())
                        item["id"] = cid
                        if cid not in seen_ids:
                            seen_ids.add(cid)
                            merged.append(item)
        except Exception:
            continue
    return merged


def _save_all(candidates: list[dict]) -> None:
    files = _find_candidate_files()
    primary_file = files[0] if files else DEFAULT_DATA_FILE
    with open(primary_file, "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)

    # ล้างไฟล์ข้อมูลผู้สมัครสำรองอื่นที่ซ้ำกันในโฟลเดอร์เดียวกัน
    for extra_path in files[1:]:
        try:
            with open(extra_path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def save_candidate(
    name: str,
    contact: str,
    target_role: str,
    responsibilities: str,
    resume_text: str,
) -> dict:
    candidates = load_candidates()
    norm_name = _normalize_text(name)
    norm_resume = _normalize_text(resume_text)

    if norm_resume:
        for existing in candidates:
            same_name = (not norm_name) or (_normalize_text(existing.get("name", "")) == norm_name)
            same_resume = _normalize_text(existing.get("resume_text", "")) == norm_resume
            if same_name and same_resume:
                existing["contact"] = contact or existing.get("contact", "")
                existing["target_role"] = target_role or existing.get("target_role", "")
                existing["responsibilities"] = responsibilities or existing.get("responsibilities", "")
                _save_all(candidates)
                return existing

    new_record = {
        "id": str(uuid.uuid4()),
        "name": name or "-",
        "contact": contact or "-",
        "target_role": target_role or "-",
        "responsibilities": responsibilities or "-",
        "resume_text": resume_text or "",
    }
    candidates.insert(0, new_record)
    _save_all(candidates)
    return new_record


def delete_candidate(candidate_id: str) -> bool:
    candidates = load_candidates()
    updated = [c for c in candidates if str(c.get("id")) != str(candidate_id)]
    if len(updated) == len(candidates):
        return False
    _save_all(updated)
    return True


def clear_all_candidates() -> None:
    _save_all([])