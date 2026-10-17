import io
from fastapi import APIRouter, HTTPException
from pypdf import PdfReader
from mysite.chain.ai_search import chain, vector_store
from mysite.db.db import SessionLocal
from mysite.db.model import Info
from mysite.db.schema import CheckOut, CheckTextIn, CheckUserOut

check_router = APIRouter(prefix='/check', tags=['Check resume'])


def read_resume_text(resume) -> str:
    raw = resume.file.read()
    if isinstance(raw, str):
        raw = raw.encode('utf-8')

    filename = (resume['filename'] or '').lower()

    if filename.endswith('.pdf'):
        reader = PdfReader(io.BytesIO(raw))
        return '\n'.join(page.extract_text() or '' for page in reader.pages)
    if filename.endswith('.txt'):
        return raw.decode('utf-8', errors='ignore')

    raise HTTPException(status_code=400, detail='Поддерживаются только PDF и TXT')


async def run_check(text: str) -> CheckOut:
    text = text.strip()
    if len(text) < 50:
        raise HTTPException(status_code=400, detail='Резюме пустое или не читается')
    text = text[:6000]

    results = vector_store.similarity_search(text, k=4)
    base_knowledge = '\n'.join(doc.page_content for doc in results)

    answer = await chain.ainvoke({
        'base_knowledge': base_knowledge,
        'content': text,
    })
    return CheckOut(
        suitable=answer.lower().startswith('вердикт: подходит'),
        answer=answer,
    )


@check_router.get('/user/{user_id}', response_model=CheckUserOut)
async def check_user_resume(user_id: int):
    """Проверить резюме-файл, сохранённый у пользователя"""
    with SessionLocal() as db:
        user = db.get(Info, user_id)
        if not user:
            raise HTTPException(status_code=404, detail='Пользователь не найден')
        if user.resume is None:
            raise HTTPException(status_code=400, detail='У пользователя нет резюме')
        text = read_resume_text(user.resume)
        full_name = user.full_name

    result = await run_check(text)
    return CheckUserOut(user_id=user_id, user=full_name, **result.model_dump())


@check_router.post('/text', response_model=CheckOut)
async def check_text(data: CheckTextIn):
    """Проверить резюме, присланное текстом"""
    return await run_check(data.resume)