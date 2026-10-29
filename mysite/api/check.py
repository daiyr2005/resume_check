from __future__ import annotations

import io

from fastapi import APIRouter, HTTPException
from pypdf import PdfReader

from mysite.db.db import SessionLocal
from mysite.db.model import Info
from mysite.db.schema import CheckOut, CheckTextIn, CheckUserOut
from mysite.services.ats_scorer import format_score_report, score_resume
from mysite.services.llm_service import LLMServiceError, review_resume

check_router = APIRouter(prefix="/check", tags=["Check resume"])


def read_resume_text(resume) -> str:
    """Extract text from a stored resume when its storage backend exposes a file handle."""
    file_handle = getattr(resume, "file", None)
    if file_handle is None:
        raise HTTPException(status_code=422, detail="Не удалось получить содержимое сохранённого файла резюме")
    raw = file_handle.read()
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    filename = str(getattr(resume, "filename", "") or "").lower()
    if filename.endswith(".pdf"):
        try:
            return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Не удалось прочитать PDF резюме") from exc
    if filename.endswith(".txt"):
        return raw.decode("utf-8-sig", errors="replace")
    raise HTTPException(status_code=400, detail="Поддерживаются только PDF и TXT")


async def run_check(text: str, vacancy: str = "") -> CheckOut:
    resume = text.strip()
    vacancy = vacancy.strip()
    if len(resume) < 50:
        raise HTTPException(status_code=400, detail="Резюме пустое или содержит слишком мало читаемого текста")
    try:
        if vacancy:
            score = score_resume(resume, vacancy)
            answer = format_score_report(score) + "\n\nПРОФЕССИОНАЛЬНЫЙ РАЗБОР\n"
            answer += await review_resume(resume[:25000], vacancy[:12000])
            suitable = score.score >= 50
        else:
            answer = (
                "Вакансия не предоставлена, поэтому оценка соответствия и вывод о пригодности не формируются. "
                "Ниже — разбор ясности, структуры и полноты резюме.\n\n"
            ) + await review_resume(resume[:25000], "Вакансия не предоставлена. Оцени только качество и структуру резюме; не делай вывод о соответствии должности.")
            suitable = False
    except LLMServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return CheckOut(suitable=suitable, answer=answer)


@check_router.get("/user/{user_id}", response_model=CheckUserOut)
async def check_user_resume(user_id: int, vacancy: str = ""):
    with SessionLocal() as db:
        user = db.get(Info, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        if user.resume is None:
            raise HTTPException(status_code=400, detail="У пользователя нет резюме")
        text = read_resume_text(user.resume)
        full_name = user.full_name
    result = await run_check(text, vacancy)
    return CheckUserOut(user_id=user_id, user=full_name, **result.model_dump())


@check_router.post("/text", response_model=CheckOut)
async def check_text(data: CheckTextIn):
    return await run_check(data.resume, data.vacancy)
