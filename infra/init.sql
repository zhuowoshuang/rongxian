-- 数据库初始化脚本
-- PostgreSQL 会在容器首次启动时自动执行此脚本

-- 确保使用 UTF-8 编码
SET client_encoding = 'UTF8';

-- 创建扩展（如果需要）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 表结构由 SQLAlchemy 自动创建，此处仅做额外初始化
-- 如需手动建表，可参考 backend/app/models/ 下的模型定义
