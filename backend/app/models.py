"""Modelo de datos de RastroJuliaca (SQLAlchemy 2.0, compatible con SQLite y PostgreSQL)."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return uuid.uuid4().hex


class Role(str, enum.Enum):
    DENUNCIANTE = "DENUNCIANTE"
    COLABORADOR = "COLABORADOR"
    REVISOR = "REVISOR"
    ADMIN = "ADMIN"


class Sensitivity(str, enum.Enum):
    GENERAL = "GENERAL"
    RESTRINGIDO = "RESTRINGIDO"
    INSTITUCIONAL = "INSTITUCIONAL"


SENSITIVITY_ORDER = {Sensitivity.GENERAL: 0, Sensitivity.RESTRINGIDO: 1, Sensitivity.INSTITUCIONAL: 2}


class CaseStatus(str, enum.Enum):
    BORRADOR = "BORRADOR"
    PENDIENTE_REVISION = "PENDIENTE_REVISION"
    CORRECCION_SOLICITADA = "CORRECCION_SOLICITADA"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    CERRADO = "CERRADO"


class PublicationStatus(str, enum.Enum):
    NO_PUBLICADO = "NO_PUBLICADO"
    PENDIENTE_SEGUNDA_APROBACION = "PENDIENTE_SEGUNDA_APROBACION"
    PUBLICADO = "PUBLICADO"
    RETIRADO = "RETIRADO"


class FileStatus(str, enum.Enum):
    CUARENTENA = "CUARENTENA"
    DISPONIBLE = "DISPONIBLE"
    BLOQUEADO_SIN_ANTIVIRUS = "BLOQUEADO_SIN_ANTIVIRUS"
    INFECTADO = "INFECTADO"
    RECHAZADO_FORMATO = "RECHAZADO_FORMATO"
    ERROR_PROCESAMIENTO = "ERROR_PROCESAMIENTO"
    ELIMINADO = "ELIMINADO"


class ContributionType(str, enum.Enum):
    VIDEO = "VIDEO"
    FOTO = "FOTO"
    DOCUMENTO = "DOCUMENTO"
    TEXTO = "TEXTO"


class ContributionStatus(str, enum.Enum):
    EN_VALIDACION = "EN_VALIDACION"  # archivo en cuarentena / análisis
    BLOQUEADA = "BLOQUEADA"  # archivo no superó validación o no hay antivirus
    PENDIENTE_REVISION = "PENDIENTE_REVISION"
    CLASIFICADA = "CLASIFICADA"


class Classification(str, enum.Enum):
    RELEVANTE = "RELEVANTE"
    POSIBLEMENTE_RELEVANTE = "POSIBLEMENTE_RELEVANTE"
    NO_RELEVANTE = "NO_RELEVANTE"
    DUPLICADO = "DUPLICADO"
    NO_ADMISIBLE = "NO_ADMISIBLE"


class Certainty(str, enum.Enum):
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


class DocReviewStatus(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    ACEPTADO = "ACEPTADO"
    OBSERVADO = "OBSERVADO"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Permisos de examen de evidencias sensibles: separados de la administración técnica
    can_review_restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    can_review_institutional: Mapped[bool] = mapped_column(Boolean, default=False)
    alias: Mapped[str] = mapped_column(String(20), unique=True)  # seudónimo mostrado a revisores
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSession(Base):
    __tablename__ = "user_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user: Mapped[User] = relationship()


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(40), default="circle-help")
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    sensitivity: Mapped[str] = mapped_column(String(20), default=Sensitivity.GENERAL.value)
    # Piso de sensibilidad protegido: no modificable por la API administrativa
    min_sensitivity: Mapped[str] = mapped_column(String(20), default=Sensitivity.GENERAL.value)
    field_schema: Mapped[list] = mapped_column(JSON, default=list)
    document_policy: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    parent: Mapped["Category | None"] = relationship(remote_side="Category.id", back_populates="children")
    children: Mapped[list["Category"]] = relationship(back_populates="parent")


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    incident_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    zone: Mapped[str] = mapped_column(String(80))
    private_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    private_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    private_location_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specific_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    sensitive_flags: Mapped[list] = mapped_column(JSON, default=list)
    sensitivity: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True, default=CaseStatus.BORRADOR.value)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_status: Mapped[str] = mapped_column(String(40), default=PublicationStatus.NO_PUBLICADO.value)
    contributions_open: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    category: Mapped[Category] = relationship()
    reporter: Mapped[User] = relationship()
    assignments: Mapped[list["CaseAssignment"]] = relationship(back_populates="case")
    documents: Mapped[list["SupportingDocument"]] = relationship(back_populates="case")
    public_card: Mapped["PublicCard | None"] = relationship(back_populates="case", uselist=False)


class CaseAssignment(Base):
    __tablename__ = "case_assignments"
    __table_args__ = (UniqueConstraint("case_id", "reviewer_id", name="uq_assignment"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    case: Mapped[Case] = relationship(back_populates="assignments")
    reviewer: Mapped[User] = relationship(foreign_keys=[reviewer_id])


class CaseEvent(Base):
    """Historial del expediente (append-only)."""

    __tablename__ = "case_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    event: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(Text, default="")
    visible_to_reporter: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[User | None] = relationship()


class CaseDecision(Base):
    __tablename__ = "case_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewer: Mapped[User] = relationship()


class StoredFile(Base):
    __tablename__ = "stored_files"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))  # RESPALDO | EVIDENCIA
    original_name: Mapped[str] = mapped_column(String(200))
    internal_name: Mapped[str] = mapped_column(String(80), unique=True)
    detected_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    media_class: Mapped[str | None] = mapped_column(String(20), nullable=True)  # image | video | document
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default=FileStatus.CUARENTENA.value, index=True)
    status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    scan_engine: Mapped[str | None] = mapped_column(String(60), nullable=True)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    playback_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    media_info: Mapped[dict] = mapped_column(JSON, default=dict)
    duplicate_of_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SupportingDocument(Base):
    __tablename__ = "supporting_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    doc_type: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(500), default="")
    file_id: Mapped[str] = mapped_column(ForeignKey("stored_files.id"))
    review_status: Mapped[str] = mapped_column(String(20), default=DocReviewStatus.PENDIENTE.value)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    case: Mapped[Case] = relationship(back_populates="documents")
    file: Mapped[StoredFile] = relationship()


class PublicCard(Base):
    """Ficha pública generalizada: solo contiene datos autorizados por la revisión."""

    __tablename__ = "public_cards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), unique=True)
    public_title: Mapped[str] = mapped_column(String(160))
    public_summary: Mapped[str] = mapped_column(Text)
    zone: Mapped[str] = mapped_column(String(80))
    incident_date: Mapped[str] = mapped_column(String(10))  # AAAA-MM-DD (sin hora exacta)
    public_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    case: Mapped[Case] = relationship(back_populates="public_card")


class Contribution(Base):
    __tablename__ = "contributions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    contributor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    ctype: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    declared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    declared_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    declared_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    certainty: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(30), index=True)
    classification: Mapped[str | None] = mapped_column(String(30), nullable=True)
    classified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    file_id: Mapped[str | None] = mapped_column(ForeignKey("stored_files.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    case: Mapped[Case] = relationship()
    contributor: Mapped[User] = relationship(foreign_keys=[contributor_id])
    file: Mapped[StoredFile | None] = relationship()


class Correction(Base):
    """Corrección justificada de un dato declarado. Nunca sobrescribe el original."""

    __tablename__ = "corrections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contribution_id: Mapped[int] = mapped_column(ForeignKey("contributions.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(40))
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    author: Mapped[User] = relationship()


class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    contribution_id: Mapped[int | None] = mapped_column(ForeignKey("contributions.id", ondelete="CASCADE"), nullable=True, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    author: Mapped[User] = relationship()


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[dict] = mapped_column(JSON)
    content_sha256: Mapped[str] = mapped_column(String(64))
    export_count: Mapped[int] = mapped_column(Integer, default=0)
    case: Mapped[Case] = relationship()
    author: Mapped[User] = relationship()


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    actor: Mapped[User | None] = relationship()


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict | list | int | str | bool | None] = mapped_column(JSON)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class DataRightsRequest(Base):
    """Solicitudes de derechos del titular (acceso, rectificación, cancelación, oposición)."""

    __tablename__ = "data_rights_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rtype: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="PENDIENTE")
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped[User] = relationship(foreign_keys=[user_id])
