"""SQLAlchemy async models — 多租户 SaaS 数据层"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Boolean, Integer, BigInteger, Float, Text,
    DateTime, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    plan = Column(String(20), default="free")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)

    config = relationship("TenantConfig", back_populates="tenant", uselist=False, lazy="joined")
    secrets = relationship("TenantSecret", back_populates="tenant", lazy="selectin")


class TenantConfig(Base):
    __tablename__ = "tenant_configs"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True)
    platforms = Column(JSONB, default=list)
    interests = Column(JSONB, default=list)
    rsshub_feeds = Column(JSONB, default=list)
    external_feeds = Column(JSONB, default=list)
    notification = Column(JSONB, default=dict)
    ai_config = Column(JSONB, default=dict)
    cron_schedule = Column(String(50), default="*/30 * * * *")
    obsidian_export = Column(Boolean, default=False)

    tenant = relationship("Tenant", back_populates="config")


class TenantSecret(Base):
    __tablename__ = "tenant_secrets"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True)
    key_name = Column(String(50), primary_key=True)
    encrypted_value = Column(Text, nullable=False)

    tenant = relationship("Tenant", back_populates="secrets")


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    action = Column(String(30), nullable=False)
    tokens_used = Column(Integer, default=0)
    cost_cents = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


class News(Base):
    __tablename__ = "news"

    id = Column(Text, primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True)
    title = Column(Text, nullable=False)
    url = Column(Text, default="")
    source = Column(Text, default="")
    source_type = Column(Text, default="")
    rank = Column(Integer, default=0)
    published_at = Column(DateTime(timezone=True), nullable=True)
    score = Column(Float, default=0)
    tags = Column(Text, default="")
    summary = Column(Text, default="")
    pushed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_news_tenant_created", "tenant_id", "created_at"),
        Index("idx_news_tenant_source", "tenant_id", "source_type"),
    )


class RunHistory(Base):
    __tablename__ = "run_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    hotlist_count = Column(Integer, default=0)
    rss_count = Column(Integer, default=0)
    dedup_count = Column(Integer, default=0)
    new_count = Column(Integer, default=0)
    matched_count = Column(Integer, default=0)
    pushed_count = Column(Integer, default=0)
    errors = Column(Text, default="")
