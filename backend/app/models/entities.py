"""Сущности БД: кампания, поток и оффер потока (с черновиком и снимком Keitaro)."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Campaign(Base):
    """Кампания Keitaro, с которой работает обёртка."""

    __tablename__ = "campaign"

    id: Mapped[int] = mapped_column(primary_key=True, comment="Внутренний ID кампании")
    keitaro_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, comment="ID кампании в Keitaro")
    name: Mapped[str] = mapped_column(String(255), comment="Название кампании")
    alias: Mapped[str] = mapped_column(String(255), default="", comment="Алиас кампании (часть ссылки)")
    fetched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Когда последний раз загружали потоки из Keitaro"
    )

    streams: Mapped[list["Stream"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", order_by="Stream.position"
    )


class Stream(Base):
    """Поток кампании. Потоки без офферов хранятся, но без содержимого."""

    __tablename__ = "stream"

    id: Mapped[int] = mapped_column(primary_key=True, comment="Внутренний ID потока")
    keitaro_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, comment="ID потока в Keitaro")
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaign.id", ondelete="CASCADE"), index=True, comment="Кампания потока"
    )
    name: Mapped[str] = mapped_column(String(255), comment="Название потока")
    position: Mapped[int] = mapped_column(Integer, default=0, comment="Позиция потока в кампании")

    campaign: Mapped[Campaign] = relationship(back_populates="streams")
    offers: Mapped[list["StreamOffer"]] = relationship(
        back_populates="stream", cascade="all, delete-orphan", order_by="StreamOffer.position"
    )


class StreamOffer(Base):
    """Оффер в потоке: снимок Keitaro (in_kt, kt_weight) и черновик пользователя (active, weight, pinned)."""

    __tablename__ = "stream_offer"
    __table_args__ = (
        UniqueConstraint("stream_id", "offer_id", name="uq_stream_offer_stream_offer"),
        CheckConstraint("weight >= 0 AND weight <= 100", name="weight_range"),
        CheckConstraint("kt_weight >= 0 AND kt_weight <= 100", name="kt_weight_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, comment="Внутренний ID записи")
    stream_id: Mapped[int] = mapped_column(
        ForeignKey("stream.id", ondelete="CASCADE"), index=True, comment="Поток, в котором лежит оффер"
    )
    position: Mapped[int] = mapped_column(Integer, default=0, comment="Порядок оффера в потоке (влияет на раздачу остатка долей)")
    offer_id: Mapped[int] = mapped_column(Integer, comment="ID оффера в Keitaro")
    name: Mapped[str] = mapped_column(String(500), comment="Название оффера")
    geo: Mapped[str] = mapped_column(String(255), default="", comment="Гео оффера для подписи")
    in_kt: Mapped[bool] = mapped_column(Boolean, default=False, comment="Есть в Keitaro по последней загрузке или отправке")
    kt_weight: Mapped[int] = mapped_column(Integer, default=0, comment="Вес в Keitaro по последней загрузке, % (снимок для merge)")
    active: Mapped[bool] = mapped_column(Boolean, default=True, comment="Активен ли оффер в черновике")
    weight: Mapped[int] = mapped_column(Integer, default=0, comment="Вес в черновике, %")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, comment="Вес закреплён пользователем")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, comment="Лежит в архиве обёртки (удалён после отправки)")
    was_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="Был в архиве до возвращения в черновик (нужно для отмены изменений)"
    )

    stream: Mapped[Stream] = relationship(back_populates="offers")
