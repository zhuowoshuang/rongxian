from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# 连接参数
connect_args = {}
engine_kwargs = {}

if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # PostgreSQL/MySQL 生产级连接池配置
    engine_kwargs = {
        "pool_size": 10,          # 常驻连接数
        "max_overflow": 20,       # 溢出连接数（pool_size + max_overflow = 最大并发）
        "pool_timeout": 30,       # 获取连接的超时时间（秒）
        "pool_recycle": 1800,     # 连接回收时间（秒），防止数据库侧断开
        "pool_pre_ping": True,    # 每次取连接前先 ping，剔除失效连接
    }

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """获取数据库会话，用于 FastAPI 依赖注入（含异常时自动 rollback）"""
    db = SessionLocal()
    try:
        yield db
        db.commit()  # 请求正常完成时提交
    except Exception:
        db.rollback()  # 请求异常时回滚
        raise
    finally:
        db.close()
