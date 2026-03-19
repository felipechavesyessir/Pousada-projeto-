from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, Date, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import check_password_hash, generate_password_hash

ReservaStatus = Literal["pendente", "entrada_paga", "completo"]

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)


class Reserva(db.Model):
    __tablename__ = "reservas"
    __table_args__ = (
        CheckConstraint("status IN ('pendente', 'entrada_paga', 'completo')", name="ck_reserva_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    telefone: Mapped[str] = mapped_column(String(32), nullable=False)
    cpf: Mapped[str] = mapped_column(String(18), nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    valor_entrada: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    plataforma: Mapped[str] = mapped_column(String(50), nullable=False)
    checkin: Mapped[str] = mapped_column(Date, nullable=False)
    checkout: Mapped[str] = mapped_column(Date, nullable=False)
    quarto: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente")
    observacoes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    comprovante_nome_arquivo: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    comprovante_url_publica: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    @property
    def valor_restante(self) -> Decimal:
        total = self.valor_total or Decimal("0.00")
        entrada = self.valor_entrada or Decimal("0.00")
        restante = total - entrada
        return restante if restante > 0 else Decimal("0.00")
