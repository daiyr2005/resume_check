from io import BytesIO
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PDFValidationError(ValueError):
    pass


def validate_resume_pdf(pdf: bytes, expected_text: str) -> None:
    if not pdf.startswith(b"%PDF-"):
        raise PDFValidationError("Сформированный файл не является корректным PDF.")
    try:
        reader = PdfReader(BytesIO(pdf), strict=True)
        if not reader.pages:
            raise PDFValidationError("В PDF нет страниц.")
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    except PDFValidationError:
        raise
    except (PdfReadError, OSError, ValueError) as exc:
        raise PDFValidationError("Не удалось повторно прочитать сформированный PDF.") from exc

    expected_chars = re.sub(r"\s+", "", expected_text)
    extracted_chars = re.sub(r"\s+", "", extracted)
    if not expected_chars or len(extracted_chars) / len(expected_chars) < 0.75:
        raise PDFValidationError(
            "Проверка PDF не пройдена: извлечённый текст неполный. Попробуйте создать новую версию."
        )
