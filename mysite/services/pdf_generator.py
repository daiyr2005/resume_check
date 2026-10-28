from io import BytesIO
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
)

STYLES = {
    "Classic Professional": colors.HexColor("#18324A"),
    "Modern Minimal": colors.HexColor("#334155"),
    "Technical / IT Developer": colors.HexColor("#075985"),
    "Data Science / AI / ML": colors.HexColor("#5B3A8A"),
    "Business / Management": colors.HexColor("#6B3F24"),
    "Entry-Level / Graduate": colors.HexColor("#166534"),
}
SECTION_HEADINGS = {
    "summary", "profile", "about", "обо мне", "профиль", "резюме",
    "опыт работы", "опыт", "experience", "work experience", "employment",
    "образование", "education", "навыки", "skills", "технологии", "technologies",
    "проекты", "projects", "сертификаты", "certifications", "языки", "languages",
    "достижения", "achievements", "контакты", "contacts",
}
FONT_CANDIDATES = (
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
)


class PDFGenerationError(RuntimeError):
    pass


def _register_unicode_fonts() -> tuple[str, str]:
    for regular_path, bold_path in FONT_CANDIDATES:
        regular = Path(regular_path)
        if not regular.is_file():
            continue
        bold = Path(bold_path)
        regular_name = "ResumeUnicode"
        bold_name = "ResumeUnicodeBold"
        try:
            pdfmetrics.registerFont(TTFont(regular_name, str(regular)))
            pdfmetrics.registerFont(TTFont(bold_name, str(bold if bold.is_file() else regular)))
        except (OSError, ValueError) as exc:
            raise PDFGenerationError("Не удалось загрузить шрифт для PDF.") from exc
        return regular_name, bold_name
    raise PDFGenerationError(
        "Не найден шрифт с поддержкой кириллицы. Установите DejaVu Sans или Arial и повторите."
    )


def _is_heading(line: str) -> bool:
    cleaned = re.sub(r"^[#\s]+|[*#\s]+$", "", line).strip().casefold().rstrip(":")
    return cleaned in SECTION_HEADINGS or (len(cleaned) < 55 and cleaned.isupper() and len(cleaned) > 2)


def create_resume_pdf(resume: str, style: str = "Classic Professional") -> bytes:
    if not resume.strip():
        raise PDFGenerationError("Нельзя создать PDF из пустого резюме.")
    if style not in STYLES:
        raise PDFGenerationError("Выбран неизвестный стиль оформления.")
    regular_font, bold_font = _register_unicode_fonts()
    accent = STYLES[style]

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ResumeTitle",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=19,
        leading=24,
        textColor=accent,
        alignment=TA_LEFT,
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "ResumeSection",
        parent=styles["Heading2"],
        fontName=bold_font,
        fontSize=11,
        leading=15,
        textColor=accent,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "ResumeBody",
        parent=styles["BodyText"],
        fontName=regular_font,
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#202833"),
        spaceAfter=3,
        splitLongWords=True,
    )
    bullet_style = ParagraphStyle(
        "ResumeBullet",
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-9,
        bulletIndent=0,
    )

    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=48,
        leftMargin=48,
        topMargin=46,
        bottomMargin=46,
        title="ATS Resume",
        author="ATS Resume AI",
    )

    def draw_page(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D7DEE5"))
        canvas.setLineWidth(0.5)
        canvas.line(48, 34, A4[0] - 48, 34)
        canvas.setFont(regular_font, 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawRightString(A4[0] - 48, 22, str(document.page))
        canvas.restoreState()

    frame = Frame(48, 46, A4[0] - 96, A4[1] - 92, id="resume")
    doc.addPageTemplates([PageTemplate(id="resume", frames=[frame], onPage=draw_page)])

    content = []
    first_content = True
    for raw_line in resume.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = line.replace("**", "").replace("__", "")
        if not line:
            content.append(Spacer(1, 3))
            continue
        if first_content:
            content.append(Paragraph(escape(line), title_style))
            first_content = False
        elif _is_heading(line):
            content.append(Paragraph(escape(line.rstrip(":")), section_style))
        elif re.match(r"^(?:[-*•▪]|\d+[.)])\s+", line):
            bullet_text = re.sub(r"^(?:[-*•▪]|\d+[.)])\s+", "", line)
            content.append(Paragraph(f"• {escape(bullet_text)}", bullet_style))
        else:
            content.append(Paragraph(escape(line), body_style))

    try:
        doc.build(content)
    except (ValueError, OSError, TypeError) as exc:
        raise PDFGenerationError("Не удалось сформировать PDF. Проверьте текст резюме.") from exc
    return buffer.getvalue()
