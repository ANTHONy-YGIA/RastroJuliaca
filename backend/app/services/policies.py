"""Políticas de sensibilidad. Las protecciones reforzadas están definidas en código y
no pueden desactivarse desde la configuración administrativa."""
from __future__ import annotations

from ..models import SENSITIVITY_ORDER, Case, CaseStatus, PublicationStatus, Sensitivity

# Marcadores que obligan a tratamiento INSTITUCIONAL sin importar la categoría.
PROTECTED_FLAGS: dict[str, str] = {
    "secuestro": "Posible secuestro",
    "violencia_sexual": "Violencia sexual",
    "menor_vulnerable": "Involucra a menores de edad o personas vulnerables",
    "desaparicion_alto_riesgo": "Desaparición de alto riesgo",
}

# Pisos mínimos por categoría (slug). La API administrativa no puede bajar de estos valores.
SENSITIVITY_FLOORS: dict[str, str] = {
    "personas-desaparecidas": Sensitivity.RESTRINGIDO.value,
    "desaparecidas-menor": Sensitivity.INSTITUCIONAL.value,
    "desaparecidas-alto-riesgo": Sensitivity.INSTITUCIONAL.value,
    "tratamiento-institucional": Sensitivity.INSTITUCIONAL.value,
    "agresiones-altercados": Sensitivity.RESTRINGIDO.value,
}

POLICY_TEXT = {
    Sensitivity.GENERAL.value: "Puede solicitar la publicación de una ficha generalizada tras la revisión.",
    Sensitivity.RESTRINGIDO.value: "Revisión reforzada por dos revisores habilitados; ficha pública mínima sin campos específicos.",
    Sensitivity.INSTITUCIONAL.value: "Expediente privado. Sin publicación ni aportaciones abiertas hasta que exista un procedimiento institucional autorizado.",
}


def level(s: str) -> int:
    return SENSITIVITY_ORDER[Sensitivity(s)]


def higher(a: str, b: str) -> str:
    return a if level(a) >= level(b) else b


def floor_for_slug(slug: str) -> str:
    return SENSITIVITY_FLOORS.get(slug, Sensitivity.GENERAL.value)


def effective_sensitivity(category_sensitivity: str, category_floor: str, parent_sensitivity: str | None, flags: list[str]) -> str:
    s = higher(category_sensitivity, category_floor)
    if parent_sensitivity:
        s = higher(s, parent_sensitivity)
    if any(f in PROTECTED_FLAGS for f in flags):
        s = Sensitivity.INSTITUCIONAL.value
    return s


def can_publish(case: Case) -> tuple[bool, str]:
    if case.sensitivity == Sensitivity.INSTITUCIONAL.value:
        return False, "Los expedientes INSTITUCIONALES no pueden publicarse."
    if case.status != CaseStatus.APROBADO.value:
        return False, "Solo se publican expedientes aprobados."
    if case.publication_status in (PublicationStatus.PUBLICADO.value, PublicationStatus.PENDIENTE_SEGUNDA_APROBACION.value):
        return False, "La publicación ya está en curso o vigente."
    return True, ""


def can_open_contributions(case: Case) -> tuple[bool, str]:
    if case.sensitivity == Sensitivity.INSTITUCIONAL.value:
        return False, "Los expedientes INSTITUCIONALES no admiten aportaciones abiertas."
    if case.status != CaseStatus.APROBADO.value:
        return False, "El expediente debe estar aprobado."
    if case.publication_status != PublicationStatus.PUBLICADO.value:
        return False, "El expediente debe tener una ficha pública vigente."
    return True, ""


def accepts_contributions(case: Case) -> bool:
    ok, _ = can_open_contributions(case)
    return ok and case.contributions_open
