from sqlalchemy import Column, Integer, String, DateTime, func, Boolean
from app.db.base import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    phone = Column(String(32), unique=True, nullable=True, index=True)
    user_id = Column(String(64), unique=True, nullable=True, index=True)
    password_hash = Column(String(200), nullable=False)
    display_name = Column(String(100), comment="显示名称")
    email = Column(String(100), comment="邮箱")
    role = Column(String(20), default="user", comment="角色: admin / user")
    status = Column(String(20), default="active", comment="状态: active / disabled")
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
