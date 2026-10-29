"""Deterministic and explainable comparison between a resume and vacancy."""

from __future__ import annotations

import re
from dataclasses import dataclass

TOKEN_PATTERN = re.compile(r"[^\W_]+(?:[+#.]?[^\W_]+)*", re.UNICODE)
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-zА-Яа-я]{2,}\b")
MANDATORY_MARKERS = ("обязательно", "обязателен", "обязательные", "требуется", "необходимо", "must have", "required", "mandatory")
PREFERRED_MARKERS = ("желательно", "будет плюсом", "преимуществом", "необязательно", "nice to have", "preferred", "desirable")
STOP_WORDS = {"для", "или", "при", "это", "опыт", "знание", "работы", "работа", "умение", "навык", "навыки", "лет", "года", "году", "уровне", "требования", "the", "and", "with", "for"}


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
    return {word.casefold() for word in TOKEN_PATTERN.findall(text) if len(word) > 1 and word.casefold() not in STOP_WORDS}


def _requirements(vacancy: str) -> list[tuple[str, bool]]:
    result: list[tuple[str, bool]] = []
    seen: set[str] = set()
    for raw in vacancy.splitlines():
        line = re.sub(r"^\s*(?:[-*•▪]|\d+[.)])\s*", "", raw).strip()
        if not 3 <= len(line) <= 300:
            continue
        folded = line.casefold()
        mandatory = any(marker in folded for marker in MANDATORY_MARKERS)
        preferred = any(marker in folded for marker in PREFERRED_MARKERS)
        for part in re.split(r"\s*[,;]\s*", line):
            part = re.sub(r"^(?:обязательно|обязателен|обязательные|требуется|необходимо|required|must have)\s*:?[ ]*", "", part, flags=re.I).strip(" .:-")
            tokens = _tokens(part)
            key = " ".join(sorted(tokens))
            if tokens and key not in seen:
                seen.add(key)
                result.append((part, mandatory and not preferred))
    return result[:40]


def _match_status(requirement: str, resume: str, resume_tokens: set[str]) -> str:
    normalized = " ".join(requirement.casefold().split())
    if normalized and normalized in resume:
        return "matched"
    tokens = _tokens(requirement)
    overlap = len(tokens & resume_tokens) / len(tokens) if tokens else 0
    return "matched" if overlap >= 0.75 else "partial" if overlap >= 0.4 else "missing"


def score_resume(resume: str, vacancy: str) -> AtsScore:
    normalized_resume = " ".join(resume.casefold().split())
    resume_tokens = _tokens(resume)
    mandatory: list[RequirementResult] = []
    preferred: list[RequirementResult] = []
    for text, required in _requirements(vacancy):
        result = RequirementResult(text, required, _match_status(text, normalized_resume, resume_tokens))
        (mandatory if required else preferred).append(result)
    items = mandatory + preferred
    weight_total = sum(2 if item.mandatory else 1 for item in items)
    weight_earned = sum((2 if item.mandatory else 1) * (1 if item.status == "matched" else 0.5 if item.status == "partial" else 0) for item in items)
    score = round(100 * weight_earned / weight_total) if weight_total else 0

    sections = {
        "Контакты": ("контакт", "contact", "email", "телефон", "phone"),
        "Опыт работы": ("опыт работы", "опыт", "experience", "employment", "work history"),
        "Образование": ("образование", "education"),
        "Навыки": ("навыки", "skills", "технологии", "technologies"),
        "Проекты": ("проекты", "projects"),
    }
    checks = tuple((name, bool(EMAIL_PATTERN.search(resume)) if name == "Контакты" else any(alias in normalized_resume for alias in aliases)) for name, aliases in sections.items())
    quality = round(100 * sum(passed for _, passed in checks) / len(checks))
    return AtsScore(score, tuple(mandatory), tuple(preferred), quality, checks)


def format_score_report(score: AtsScore) -> str:
    status_label = {"matched": "подтверждено", "partial": "частично подтверждено", "missing": "не найдено"}
    lines = [
        f"Оценка соответствия требованиям: {score.score}% (обязательные требования имеют двойной вес; частичное совпадение учитывается как половина баллов).",
        f"Структура резюме: {score.document_quality}% по наличию проверяемых разделов.",
        "", "Обязательные требования:",
    ]
    lines.extend(f"• {item.text} — {status_label[item.status]}" for item in score.mandatory)
    if not score.mandatory:
        lines.append("• В вакансии не выделены требования с явной пометкой обязательности.")
    lines.extend(["", "Желательные требования и прочие условия:"])
    lines.extend(f"• {item.text} — {status_label[item.status]}" for item in score.preferred)
    if not score.preferred:
        lines.append("• Не выделены.")
    lines.extend(["", "Проверка структуры:"])
    lines.extend(f"• {name}: {'найдено' if passed else 'не найдено'}" for name, passed in score.quality_checks)
    lines.extend(["", "Оценка — ориентир на основе текстового совпадения, а не гарантия прохождения ATS или трудоустройства."])
    return "\n".join(lines)
