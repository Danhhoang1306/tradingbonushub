from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

BONUS_TYPES = ("nodep", "deposit", "cashback", "contest", "crypto")
BROKER_KINDS = ("forex", "crypto")
KIND_LABELS = {"forex": "Forex", "crypto": "Crypto"}
POST_CATEGORIES = ("Hướng dẫn", "Kiến thức", "So sánh", "Tin sàn")
POST_STATUSES = ("draft", "published")
PLACEMENTS = ("after-bonus", "before-blog", "rail-left", "rail-right")
SUBSCRIBER_STATUSES = ("pending", "confirmed", "unsubscribed")
ROLES = ("admin", "editor")


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_users"
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="admin", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class AdminSession(TimestampMixin, Base):
    __tablename__ = "admin_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    user: Mapped[AdminUser] = relationship()


class Broker(TimestampMixin, Base):
    __tablename__ = "brokers"
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    mono: Mapped[str] = mapped_column(String(2), default="", nullable=False)
    kind: Mapped[str] = mapped_column(String(10), default="forex", nullable=False)
    tagline: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    license: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    min_deposit: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    leverage: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    platforms: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    spread: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    withdrawal: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    founded: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    affiliate_url: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    logo_path: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    pros: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    cons: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    accounts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payment_methods: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    in_compare: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bonuses: Mapped[list["Bonus"]] = relationship(back_populates="broker", cascade="all, delete-orphan")


class Bonus(TimestampMixin, Base):
    __tablename__ = "bonuses"
    broker_id: Mapped[int] = mapped_column(ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    value_num: Mapped[float | None] = mapped_column(Float)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    min_deposit: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    withdrawable: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    broker: Mapped[Broker] = relationship(back_populates="bonuses")


class Post(TimestampMixin, Base):
    __tablename__ = "posts"
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_md: Mapped[str] = mapped_column(Text, default="", nullable=False)
    cover_path: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    read_minutes: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    show_home: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Banner(TimestampMixin, Base):
    __tablename__ = "banners"
    broker_id: Mapped[int | None] = mapped_column(ForeignKey("brokers.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    image_path: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    placement: Mapped[str] = mapped_column(String(20), nullable=False)
    target_url: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    broker: Mapped[Broker | None] = relationship()


class Subscriber(TimestampMixin, Base):
    __tablename__ = "subscribers"
    name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    interests: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)


class ContactMessage(TimestampMixin, Base):
    __tablename__ = "contact_messages"
    topic: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Campaign(TimestampMixin, Base):
    __tablename__ = "campaigns"
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)


class Setting(TimestampMixin, Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    value: Mapped[object] = mapped_column(JSON, nullable=True)


class MediaFile(TimestampMixin, Base):
    __tablename__ = "media_files"
    path: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)  # URL công khai, vd /media/ab12.webp
    alt: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ClickLog(TimestampMixin, Base):
    """Đếm click theo ngày (kind = broker|ad) để vẽ biểu đồ 30 ngày ở Tổng quan."""
    __tablename__ = "click_logs"
    __table_args__ = (UniqueConstraint("kind", "ref_id", "day"),)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    ref_id: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
