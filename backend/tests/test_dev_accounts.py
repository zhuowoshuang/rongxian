from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import verify_password
from app.commands import ensure_dev_accounts as ensure_module
from app.db.base import Base
from app.models.user import User


def _build_testing_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal


def test_ensure_dev_accounts_creates_or_fixes_accounts(monkeypatch):
    testing_session = _build_testing_session()
    db = testing_session()
    db.add(
        User(
            username="admin",
            user_id="admin",
            password_hash="broken-hash",
            display_name="Old Admin",
            role="user",
            is_active=False,
            status="disabled",
        )
    )
    db.commit()
    db.close()

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.setattr(ensure_module, "SessionLocal", testing_session)

    result = ensure_module.ensure_dev_accounts()

    assert result[0].startswith("production_guard=allowed")
    verify_db = testing_session()
    try:
      admin = verify_db.query(User).filter(User.username == "admin").first()
      analyst = verify_db.query(User).filter(User.username == "analyst").first()
      assert admin is not None
      assert analyst is not None
      assert admin.role == "admin"
      assert analyst.role == "analyst"
      assert admin.is_active is True
      assert analyst.is_active is True
      assert verify_password("Admin123456", admin.password_hash) is True
      assert verify_password("Analyst123", analyst.password_hash) is True
    finally:
      verify_db.close()


def test_ensure_dev_accounts_blocks_production_without_debug(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DEBUG", raising=False)
    try:
        ensure_module.ensure_dev_accounts()
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert "disabled in production" in str(exc)
