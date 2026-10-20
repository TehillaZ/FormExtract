"""Tables (PLAN 6, ADR-016). `records.data` holds the full CommitmentRecord; the other columns are
denormalized copies used for search, filtering and the uniqueness rule."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(sa.String(300))
    file_hash: Mapped[str] = mapped_column(sa.String(64), unique=True)   # ADR-010: identical file = duplicate
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_now)
    pages: Mapped[list["Page"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "pages"
    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int]
    status: Mapped[str] = mapped_column(sa.String(20), default="pending")   # pending|processing|ready|error
    error: Mapped[str | None] = mapped_column(sa.Text)
    image_path: Mapped[str | None] = mapped_column(sa.String(500))          # enhanced image
    original_path: Mapped[str | None] = mapped_column(sa.String(500))
    record_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, index=True)   # record built from this page
    raw_extraction: Mapped[dict | None] = mapped_column(sa.JSON)            # what the model returned
    barcodes: Mapped[list | None] = mapped_column(sa.JSON)
    document: Mapped[Document] = relationship(back_populates="pages")


class Record(Base):
    __tablename__ = "records"
    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("documents.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(sa.String(20), default="pending", index=True)
    data: Mapped[dict] = mapped_column(sa.JSON)
    # search / filter copies
    id_number: Mapped[str | None] = mapped_column(sa.String(20), index=True)
    sender: Mapped[str | None] = mapped_column(sa.String(200), index=True)
    received_date: Mapped[date | None] = mapped_column(sa.Date, index=True)
    needs_review: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_now)
    approved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    commitment_numbers: Mapped[list["RecordCommitmentNumber"]] = relationship(cascade="all, delete-orphan")
    central_numbers: Mapped[list["RecordCentralNumber"]] = relationship(cascade="all, delete-orphan")
    corrections: Mapped[list["CorrectionRow"]] = relationship(cascade="all, delete-orphan", order_by="CorrectionRow.at")


class RecordCommitmentNumber(Base):
    __tablename__ = "record_commitment_numbers"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("records.id", ondelete="CASCADE"), index=True)
    value: Mapped[str] = mapped_column(sa.String(40), index=True)   # empty numbers are not stored at all
    status: Mapped[str] = mapped_column(sa.String(20), default="pending")   # mirror of records.status
    __table_args__ = (
        # ADR-016: a commitment number may belong to only one APPROVED record
        sa.Index("uq_commitment_number_approved", "value", unique=True,
                 postgresql_where=sa.text("status = 'approved'"), sqlite_where=sa.text("status = 'approved'")),
    )


class RecordCentralNumber(Base):
    __tablename__ = "record_central_numbers"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("records.id", ondelete="CASCADE"), index=True)
    value: Mapped[str] = mapped_column(sa.String(20), index=True)


class CorrectionRow(Base):
    __tablename__ = "corrections"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("records.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(sa.String(40))
    old_value: Mapped[str | None] = mapped_column(sa.Text)
    new_value: Mapped[str | None] = mapped_column(sa.Text)
    at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_now)
