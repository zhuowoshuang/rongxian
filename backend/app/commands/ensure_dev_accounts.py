from __future__ import annotations

import os

from app.api.auth import hash_password
from app.db.session import SessionLocal
from app.models.user import User

DEV_ACCOUNTS = [
    {
        "username": "analyst",
        "password": "Analyst123",
        "display_name": "Analyst",
        "role": "analyst",
        "status": "active",
    },
    {
        "username": "admin",
        "password": "Admin123456",
        "display_name": "Admin",
        "role": "admin",
        "status": "active",
    },
]


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_dev_account_bootstrap_allowed() -> tuple[bool, str]:
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    debug = _truthy(os.getenv("DEBUG"))
    if app_env == "production" and not debug:
        return False, "production_guard=blocked"
    return True, f"production_guard=allowed(app_env={app_env}, debug={str(debug).lower()})"


def ensure_dev_accounts() -> list[str]:
    allowed, guard_status = is_dev_account_bootstrap_allowed()
    if not allowed:
        raise SystemExit("ensure_dev_accounts is disabled in production unless DEBUG=true")

    db = SessionLocal()
    results: list[str] = [guard_status]
    try:
        for account in DEV_ACCOUNTS:
            user = db.query(User).filter(User.username == account["username"]).first()
            password_hash = hash_password(account["password"])
            if user:
                user.password_hash = password_hash
                user.display_name = account["display_name"]
                user.role = account["role"]
                user.user_id = user.user_id or account["username"]
                user.is_active = True
                user.status = account["status"]
                results.append(f"{account['username']} exists/fixed")
            else:
                db.add(
                    User(
                        username=account["username"],
                        user_id=account["username"],
                        password_hash=password_hash,
                        display_name=account["display_name"],
                        role=account["role"],
                        is_active=True,
                        status=account["status"],
                    )
                )
                results.append(f"{account['username']} created")
        db.commit()
        return results
    finally:
        db.close()


def main() -> None:
    for line in ensure_dev_accounts():
        print(line)


if __name__ == "__main__":
    main()
