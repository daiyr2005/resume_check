from __future__ import annotations

import asyncio
import io
import logging
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from pypdf import PdfReader
from mysite.services.ats_scorer import format_score_report, score_resume
from mysite.services.llm_service import LLMServiceError, review_resume

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MAX_PDF_BYTES = 15 * 1024 * 1024


@dataclass
class UserSession:
    resume_text: str = ""
    resume_name: str = ""
    vacancy_text: str = ""
    vacancy_parts: list[str] = field(default_factory=list)


sessions: dict[int, UserSession] = {}
dispatcher = Dispatcher()


def get_session(user_id: int) -> UserSession:
    return sessions.setdefault(user_id, UserSession())


def extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


async def analyze_resume(resume: str, vacancy: str) -> str:
    report = format_score_report(score_resume(resume, vacancy))
    expert_review = await review_resume(resume, vacancy)
    return f"{report}\n\nПРОФЕССИОНАЛЬНЫЙ РАЗБОР\n{expert_review}"


def split_telegram_text(text: str, limit: int = 4000) -> list[str]:
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip()
    if text:
        parts.append(text)
    return parts


@dispatcher.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "Пришлите PDF-файл резюме, затем отправьте требования к вакансии текстом "
        "(можно несколькими сообщениями). Когда закончите, выполните /check.\n\n"
        "Команды: /check — ATS-анализ, /status — проверить, что загружено, "
        "/reset — начать заново. Анализ выполняется через OpenAI ChatGPT API."
    )


@dispatcher.message(Command("status"))
async def status(message: Message) -> None:
    session = get_session(message.from_user.id)
    resume = session.resume_name or "не загружено"
    vacancy = "добавлены" if session.vacancy_parts else "не добавлены"
    await message.answer(f"Резюме: {resume}\nТребования вакансии: {vacancy}")


@dispatcher.message(Command("reset"))
async def reset(message: Message) -> None:
    sessions[message.from_user.id] = UserSession()
    await message.answer("Данные очищены. Пришлите PDF резюме и требования вакансии.")


@dispatcher.message(Command("check"))
async def check(message: Message) -> None:
    session = get_session(message.from_user.id)
    vacancy = "\n".join(session.vacancy_parts).strip()
    if not session.resume_text:
        await message.answer("Сначала пришлите резюме в PDF.")
        return
    if len(vacancy) < 30:
        await message.answer("Пришлите требования вакансии текстом (не менее 30 символов), затем выполните /check.")
        return

    await message.answer("Сравниваю резюме с вакансией. Это может занять немного времени…")
    try:
        result = await analyze_resume(session.resume_text, vacancy)
        if not result:
            raise RuntimeError("Модель вернула пустой ответ")
    except (LLMServiceError, asyncio.TimeoutError, RuntimeError) as exc:
        logger.exception("ATS analysis failed")
        await message.answer(f"Не удалось выполнить анализ: {str(exc)[:700]}")
        return

    for part in split_telegram_text(result):
        await message.answer(part)


@dispatcher.message(F.document)
async def receive_document(message: Message, bot: Bot) -> None:
    document = message.document
    if not document or not (document.file_name or "").lower().endswith(".pdf"):
        await message.answer("Поддерживаются только PDF-файлы резюме.")
        return
    if document.file_size and document.file_size > MAX_PDF_BYTES:
        await message.answer("Файл слишком большой. Максимальный размер — 15 МБ.")
        return
    try:
        downloaded = await bot.download(document)
        raw = downloaded.getvalue() if hasattr(downloaded, "getvalue") else downloaded.read()
        text = extract_pdf_text(raw)
    except Exception as exc:
        logger.exception("Failed to read uploaded PDF")
        await message.answer(f"Не удалось прочитать PDF: {str(exc)[:400]}")
        return
    if len(text) < 50:
        await message.answer("В PDF не найден читаемый текст. Если это скан, сначала распознайте его (OCR) и сохраните как текстовый PDF.")
        return
    session = get_session(message.from_user.id)
    session.resume_text = text
    session.resume_name = document.file_name or "resume.pdf"
    await message.answer(f"Резюме «{session.resume_name}» принято. Теперь отправьте требования вакансии текстом, затем /check.")


@dispatcher.message(F.text)
async def receive_text(message: Message) -> None:
    text = (message.text or "").strip()
    if not text:
        return
    session = get_session(message.from_user.id)
    if not session.resume_text:
        await message.answer("Сначала пришлите PDF-файл резюме. После него отправьте требования вакансии и выполните /check.")
        return
    if text.startswith("/"):
        await message.answer("Неизвестная команда. Используйте /check, /status или /reset.")
        return
    session.vacancy_parts.append(text)
    session.vacancy_text = "\n".join(session.vacancy_parts)
    await message.answer("Требования добавлены. Можете прислать продолжение или выполнить /check для ATS-анализа.")


async def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Укажите токен Telegram-бота в переменной TELEGRAM_BOT_TOKEN")
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
