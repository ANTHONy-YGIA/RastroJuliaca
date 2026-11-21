"""Formularios dinámicos: definición de campos por categoría y validación en backend.

El mismo esquema JSON se envía al frontend, que construye su validación con Zod.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

FieldType = Literal["text", "textarea", "number", "select", "date", "boolean"]
KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")


class FieldDef(BaseModel):
    key: str
    label: str = Field(min_length=1, max_length=80)
    type: FieldType
    required: bool = False
    public: bool = False  # puede incluirse en la ficha pública si el revisor lo autoriza
    help: str | None = Field(default=None, max_length=200)
    options: list[str] | None = None
    max_length: int | None = Field(default=None, ge=1, le=2000)
    min: float | None = None
    max: float | None = None
    pattern: str | None = Field(default=None, max_length=120)

    @field_validator("key")
    @classmethod
    def _key(cls, v: str) -> str:
        if not KEY_RE.match(v):
            raise ValueError("clave inválida (minúsculas, números y guion bajo)")
        return v

    @field_validator("pattern")
    @classmethod
    def _pattern(cls, v: str | None) -> str | None:
        if v:
            re.compile(v)
        return v

    @model_validator(mode="after")
    def _options(self):
        if self.type == "select" and not self.options:
            raise ValueError("un campo select requiere opciones")
        return self


def parse_schema(raw: list[dict]) -> list[FieldDef]:
    fields = [FieldDef.model_validate(f) for f in raw]
    keys = [f.key for f in fields]
    if len(keys) != len(set(keys)):
        raise ValueError("claves de campo duplicadas")
    return fields


class FieldValidationError(Exception):
    def __init__(self, errors: dict[str, str]):
        super().__init__("Campos específicos inválidos")
        self.errors = errors


def validate_fields(schema: list[dict], data: dict[str, Any] | None, *, partial: bool = False) -> dict[str, Any]:
    data = data or {}
    fields = {f.key: f for f in parse_schema(schema)}
    errors: dict[str, str] = {}
    clean: dict[str, Any] = {}

    for k in data:
        if k not in fields:
            errors[k] = "Campo no permitido para esta categoría"

    for key, f in fields.items():
        v = data.get(key)
        if isinstance(v, str):
            v = v.strip()
        empty = v is None or v == "" or (f.type == "boolean" and v is None)
        if empty:
            if f.required and not partial:
                errors[key] = "Campo obligatorio"
            continue
        try:
            clean[key] = _coerce(f, v)
        except ValueError as e:
            errors[key] = str(e)

    if errors:
        raise FieldValidationError(errors)
    return clean


def _coerce(f: FieldDef, v: Any) -> Any:
    if f.type in ("text", "textarea"):
        if not isinstance(v, str):
            raise ValueError("Debe ser texto")
        limit = f.max_length or (2000 if f.type == "textarea" else 200)
        if len(v) > limit:
            raise ValueError(f"Máximo {limit} caracteres")
        if f.pattern and not re.fullmatch(f.pattern, v):
            raise ValueError("Formato no válido")
        return v
    if f.type == "number":
        if isinstance(v, bool):
            raise ValueError("Debe ser numérico")
        try:
            n = float(v)
        except (TypeError, ValueError):
            raise ValueError("Debe ser numérico") from None
        if f.min is not None and n < f.min:
            raise ValueError(f"Mínimo {f.min:g}")
        if f.max is not None and n > f.max:
            raise ValueError(f"Máximo {f.max:g}")
        return int(n) if n.is_integer() else n
    if f.type == "select":
        if v not in (f.options or []):
            raise ValueError("Opción no válida")
        return v
    if f.type == "date":
        try:
            return date.fromisoformat(str(v)).isoformat()
        except ValueError:
            raise ValueError("Fecha no válida (AAAA-MM-DD)") from None
    if f.type == "boolean":
        if not isinstance(v, bool):
            raise ValueError("Debe ser verdadero o falso")
        return v
    raise ValueError("Tipo no soportado")


def merged_schema(parent_schema: list[dict] | None, own_schema: list[dict]) -> list[dict]:
    """Subcategorías heredan los campos de su categoría y pueden añadir propios."""
    out = list(parent_schema or [])
    keys = {f["key"] for f in out}
    out.extend(f for f in own_schema if f["key"] not in keys)
    return out
