import io
from contextvars import ContextVar

from fastapi import APIRouter, File as FastFile, Form, HTTPException, UploadFile
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from pypdf import PdfReader
from sqlalchemy_file import File

from mysite.api.info import get_all, get_one
from mysite.db.db import SessionLocal
from mysite.db.schema import InfoOut

agent_router = APIRouter(prefix='/agents', tags=['Agent with Tools'])

model = ChatOllama(model='llama3.2:latest', temperature=0)

# файл, пришедший в текущем запросе (агент сам файл не видит)
current_resume: ContextVar[dict | None] = ContextVar('current_resume', default=None)


@tool
def info_list() -> str:
    """список всех пользователей (чтобы узнать id)"""
    with SessionLocal() as db:
        users = get_all(skip=0, limit=50, db=db)
        return str([InfoOut.model_validate(u).model_dump(mode='json') for u in users])


@tool
def fill_resume(user_id: int) -> str:
    """сохранить загруженное резюме в поле resume пользователя по id"""
    data = current_resume.get()
    if data is None:
        return 'Файл резюме не загружен'

    with SessionLocal() as db:
        try:
            user = get_one(user_id, db=db)
        except HTTPException as e:
            return e.detail

        user.resume = File(
            content=data['raw'],
            filename=data['filename'],
            content_type=data['content_type'],
        )
        db.commit()
        return f'Резюме {data["filename"]} сохранено пользователю {user.full_name}'


tools = [info_list, fill_resume]
tools_dict = {t.name: t for t in tools}
model_with_tools = model.bind_tools(tools)

SYSTEM = (
    'Ты HR-ассистент. Тебе загрузили файл резюме. '
    'Вызови fill_resume с id пользователя, чтобы сохранить его. '
    'Если id не указан или неизвестен, сначала вызови info_list. '
    'Отвечай коротко, на русском.'
)


def check_readable(filename: str, raw: bytes) -> None:
    name = filename.lower()
    if name.endswith('.pdf'):
        text = '\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(raw)).pages)
        if len(text.strip()) < 50:
            raise HTTPException(status_code=400, detail='PDF пустой или это скан без текста')
    elif name.endswith('.txt'):
        if len(raw.decode('utf-8', errors='ignore').strip()) < 50:
            raise HTTPException(status_code=400, detail='Резюме слишком короткое')
    else:
        raise HTTPException(status_code=400, detail='Поддерживаются только PDF и TXT')


@agent_router.post('/resume/')
def chat(
    resume: UploadFile = FastFile(...),
    question: str = Form('Сохрани это резюме пользователю'),
):
    raw = resume.file.read()
    filename = resume.filename or 'resume'
    check_readable(filename, raw)

    current_resume.set({
        'raw': raw,
        'filename': filename,
        'content_type': resume.content_type,
    })

    messages = [SystemMessage(content=SYSTEM), HumanMessage(content=question)]
    response = model_with_tools.invoke(messages)

    for _ in range(3):  # info_list -> fill_resume -> ответ
        if not response.tool_calls:
            break
        messages.append(response)
        for call in response.tool_calls:
            result = tools_dict[call['name']].invoke(call['args'])
            messages.append(ToolMessage(content=str(result), tool_call_id=call['id']))
        response = model_with_tools.invoke(messages)

    return {'answer': response.content}