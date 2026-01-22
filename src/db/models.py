"""Database models using SQLAlchemy ORM."""

from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime, Text, ForeignKey, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    """User account."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(32), unique=True, nullable=False, index=True)
    status = Column(String(20), default='pending', index=True)  # pending, approved, blocked
    plan = Column(String(20), default='free')  # free, pro, ultra
    joined_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    blocked_reason = Column(Text, nullable=True)
    last_activity = Column(DateTime, nullable=True)
    
    # Relationships
    bots = relationship("Bot", back_populates="owner", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")


class Bot(Base):
    """Hosted bot instance."""
    
    __tablename__ = "bots"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    status = Column(String(20), default='stopped', index=True)  # stopped, running, sleeping
    token_encrypted = Column(String(1024), nullable=False)  # Fernet encrypted
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Time tracking
    total_seconds = Column(Integer, default=0)
    remaining_seconds = Column(Integer, default=0)
    start_time = Column(DateTime, nullable=True)
    
    # Power tracking
    power_max = Column(Float, default=100.0)
    power_remaining = Column(Float, default=100.0)
    
    # Sleep mode
    sleep_mode = Column(Boolean, default=False)
    sleep_reason = Column(String(100), nullable=True)
    sleep_since = Column(DateTime, nullable=True)
    
    # Restart tracking
    restart_count = Column(Integer, default=0)
    restart_window_start = Column(DateTime, nullable=True)
    last_restart_at = Column(DateTime, nullable=True)
    auto_recovery_used = Column(Boolean, default=False)
    
    # Deployment
    main_file = Column(String(255), default='main.py')
    folder = Column(String(255), nullable=False)
    
    # Docker
    container_id = Column(String(64), nullable=True)
    
    # Resource accounting
    cpu_usage_percent = Column(Float, default=0.0)
    memory_usage_mb = Column(Float, default=0.0)
    last_checked = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="bots")
    error_logs = relationship("ErrorLog", back_populates="bot", cascade="all, delete-orphan")


class ErrorLog(Base):
    """Bot error and debug logs."""
    
    __tablename__ = "error_logs"
    
    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    level = Column(String(20), default='ERROR')  # ERROR, WARNING, INFO
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    bot = relationship("Bot", back_populates="error_logs")


class AuditLog(Base):
    """Immutable audit trail (INSERT only, never UPDATE/DELETE)."""
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action = Column(String(100), nullable=False, index=True)  # bot.start, user.approve, etc
    resource_type = Column(String(50))  # bot, user, system
    resource_id = Column(String(100))
    status = Column(String(20), index=True)  # success, failure
    error_code = Column(String(50))  # RATE_LIMIT, UNAUTHORIZED, etc
    ip_address = Column(String(45))  # IPv4 or IPv6
    details = Column(JSON, default={})  # Additional context
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")


class Deployment(Base):
    """Deployment history (GitHub/upload)."""
    
    __tablename__ = "deployments"
    
    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(50))  # github, upload
    source_url = Column(String(512))  # GitHub URL or filename
    commit_hash = Column(String(40), nullable=True)
    status = Column(String(20), default='pending', index=True)  # pending, building, ready, failed
    error_message = Column(Text, nullable=True)
    deployed_at = Column(DateTime, default=datetime.utcnow)
