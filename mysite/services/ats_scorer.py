import re
from dataclasses import dataclass


MANDATORY_MARKERS = (
    "обязательно",
    "обязателен",
    "обязательные",
    "требуется",
    "необходимо",
    "must have",
    "required",
    "mandatory",
)
PREFERRED_MARKERS = (
    "желательно",
    "будет плюсом",
    "преимуществом",
    "необязательно",
    "nice to have",
    "preferred",
    "desirable",
)
HEADING_MARKERS = (
    "требования",
    "requirements",
    "обязанности",
    "responsibilities",
    "квалификация",
    "qualification",
    "условия",
    "мы ищем",
)
STOP_WORDS = {
    "and", "are", "for", "from", "have", "with", "или", "для", "как", "над",
    "при", "это", "опыт", "знание", "работы", "работа", "умение", "навык",
    "навыки", "лет", "года", "году", "уровне", "будет", "требования",
}
SECTION_PATTERNS = {
    "опыт": ("опыт", "experience", "employment", "work history"),
    "образование": ("образование", "education"),
    "навыки": ("навыки", "skills", "технологии", "technologies"),
    "контакты": ("контакты", "contact", "email", "телефон", "phone"),
    "проекты": ("проекты", "projects"),
}
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-zА-Яа-я]{2,}\b")
TOKEN_PATTERN = re.compile(r"[^\W_]+(?:[+#.]?[^\W_]+)*", re.UNICODE)


@dataclass(frozen=True)
class RequirementResult:
    text: str
    mandatory: bool
    status: str


@dataclass(frozen=True)
class AtsScore:
    score: int
    mandatory: tuple[RequirementResult, ...]
    preferred: tuple[RequirementResult, ...]
    document_quality: int
    quality_checks: tuple[tuple[str, bool], ...]


def _tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in TOKEN_PATTERN.findall(text)
        if len(token) > 1 and token.casefold() not in STOP_WORDS
    }


def _requirements(vacancy: str) -> list[tuple[str, bool]]:
    result: list[tuple[str, bool]] = []
    seen: set[str] = set()
    for raw_line in vacancy.splitlines():
        line = re.sub(r"^\s*(?:[-*•▪]|\d+[.)])\s*", "", raw_line).strip()
        if len(line) < 3 or len(line) > 300:
            continue
        folded = line.casefold()
        if any(marker in folded for marker in HEADING_MARKERS) and len(line.split()) <= 5:
            continue
        mandatory = any(marker in folded for marker in MANDATORY_MARKERS)
        preferred = any(marker in folded for marker in PREFERRED_MARKERS)
        pieces = re.split(r"\s*[,;]\s*", line)
        if len(pieces) == 1 and len(line) > 150:
            pieces = re.split(r"(?<=[.!?])\s+", line)
        for piece in pieces:
            piece = re.sub(
                r"^(?:обязательно|обязателен|обязательные|требуется|необходимо|required|must have)\s*:?\s*",
                "",
                piece,
                flags=re.IGNORECASE,
            ).strip(" .:-")
            if not piece or len(_tokens(piece)) == 0:
                continue
            key = " ".join(_tokens(piece))
            if key in seen:
                continue
            seen.add(key)
            result.append((piece, mandatory and not preferred))

    return result[:40]


def _match_status(requirement: str, resume_tokens: set[str], normalized_resume: str) -> str:
    normalized_requirement = " ".join(requirement.casefold().split())
    if normalized_requirement in normalized_resume:
        return "matched"
    tokens = _tokens(requirement)
    if not tokens:
        return "missing"
    overlap = len(tokens & resume_tokens) / len(tokens)
    if overlap >= 0.75:
        return "matched"
    if overlap >= 0.4:
        return "partial"
    return "missing"


def score_resume(resume: str, vacancy: str) -> AtsScore:
    normalized_resume = " ".join(resume.casefold().split())
    resume_tokens = _tokens(resume)
    mandatory_results: list[RequirementResult] = []
    preferred_results: list[RequirementResult] = []

    for requirement, mandatory in _requirements(vacancy):
        result = RequirementResult(
            text=requirement,
            mandatory=mandatory,
            status=_match_status(requirement, resume_tokens, normalized_resume),
        )
        (mandatory_results if mandatory else preferred_results).append(result)

    weighted_total = sum(2 if item.mandatory else 1 for item in mandatory_results + preferred_results)
    weighted_match = sum(
        (2 if item.mandatory else 1) * (1 if item.status == "matched" else 0.5 if item.status == "partial" else 0)
        for item in mandatory_results + preferred_results
    )
    score = round(100 * weighted_match / weighted_total) if weighted_total else 0

    checks = (
        ("Контактные данные", bool(EMAIL_PATTERN.search(resume))),
        ("Опыт работы", any(marker in normalized_resume for marker in SECTION_PATTERNS["опыт"])),
        ("Образование", any(marker in normalized_resume for marker in SECTION_PATTERNS["образование"])),
        ("Навыки", any(marker in normalized_resume for marker in SECTION_PATTERNS["навыки"])),
        ("Проекты", any(marker in normalized_resume for marker in SECTION_PATTERNS["проекты"])),
    )
    document_quality = round(sum(passed for _, passed in checks) * 100 / len(checks))
    return AtsScore(
        score=score,
        mandatory=tuple(mandatory_results),
        preferred=tuple(preferred_results),
        document_quality=document_quality,
        quality_checks=checks,
    )


def format_score_report(score: AtsScore) -> str:
    lines = [
        f"Прозрачная оценка соответствия: {score.score}% "
        "(обязательные требования имеют двойной вес; частичное совпадение — половину баллов).",
        f"Качество структуры документа: {score.document_quality}% "
        "(контакты, опыт, образование, навыки и проекты проверяются отдельно).",
        "",
        "Обязательные требования:",
    ]
    lines.extend(
        f"• {item.text} — {_status_label(item.status)}"
        for item in score.mandatory
    )
    if not score.mandatory:
        lines.append("• В тексте вакансии не удалось выделить требования с явной пометкой обязательности.")
    lines.extend(["", "Желательные требования / остальные условия:"])
    lines.extend(
        f"• {item.text} — {_status_label(item.status)}"
        for item in score.preferred
    )
    if not score.preferred:
        lines.append("• Не выделены.")
    lines.extend(["", "Проверка структуры:"])
    lines.extend(f"• {label}: {'есть' if passed else 'не найдено'}" for label, passed in score.quality_checks)
    lines.extend(
        [
            "",
            "Оценка — ориентир по тексту вакансии и резюме, а не гарантия прохождения ATS или трудоустройства.",
        ]
    )
    return "\n".join(lines)


def _status_label(status: str) -> str:
    return {"matched": "подтверждено", "partial": "частично подтверждено", "missing": "не найдено"}[status]
