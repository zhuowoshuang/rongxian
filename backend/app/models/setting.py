"""系统设置模型"""
from sqlalchemy import Column, Integer, String, DateTime, func
from app.db.base import Base


class Setting(Base):
    """系统设置表"""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True, comment="设置键")
    value = Column(String(2000), comment="设置值")
    description = Column(String(500), comment="描述")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
