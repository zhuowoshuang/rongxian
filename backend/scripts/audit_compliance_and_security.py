"""
Compliance and security audit - read-only.
Usage: cd backend && PYTHONPATH=. python scripts/audit_compliance_and_security.py
"""
from __future__ import annotations
import json, os, re, sys
from pathlib import Path

def main():
    report = {"items": [], "summary": {"PASS": 0, "WARN": 0, "FAIL": 0}}
    backend = Path(__file__).parent.parent

    def add(level, item, detail=""):
        report["items"].append({"level": level, "item": item, "detail": detail})
        report["summary"][level] = report["summary"].get(level, 0) + 1

    # 1. Default passwords
    try:
        import sqlite3
        db_path = backend / "stock_agent.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            c = conn.cursor()
            users = c.execute("SELECT username, password_hash FROM users").fetchall()
            import bcrypt
            defaults = {"admin": "admin123", "demo": "demo123", "analyst": "analyst123", "guest": "guest123"}
            found = False
            for username, ph in users:
                if username in defaults:
                    try:
                        if bcrypt.checkpw(defaults[username].encode(), ph.encode()):
                            found = True
                    except:
                        pass
            if found:
                add("WARN", "Default passwords exist", "Some users still have default passwords - change before production")
            else:
                add("PASS", "No default passwords found")
            conn.close()
        else:
            add("WARN", "DB not found", "Cannot check passwords")
    except Exception as e:
        add("WARN", "Password check failed", str(e))

    # 2. Login page doesn't expose passwords
    login_file = backend.parent / "frontend/src/components/LoginPage.tsx"
    if login_file.exists():
        content = login_file.read_text(encoding="utf-8")
        if "admin123" in content or "demo123" in content:
            add("FAIL", "Login page exposes default passwords", "LoginPage.tsx contains plaintext passwords")
        else:
            add("PASS", "Login page does not expose passwords")
    else:
        add("WARN", "LoginPage not found")

    # 3. JWT secret
    env_file = backend / ".env"
    if env_file.exists():
        env_content = env_file.read_text(encoding="utf-8", errors="replace")
        if "JWT_SECRET_KEY" in env_content:
            import re as _re
            m = _re.search(r"JWT_SECRET_KEY=(.+)", env_content)
            if m and len(m.group(1).strip()) >= 32 and "change" not in m.group(1).lower():
                add("PASS", "JWT secret configured")
            else:
                add("WARN", "JWT secret weak or default", "Use a strong secret >= 32 chars")
        else:
            add("WARN", "JWT_SECRET_KEY not in .env", "Will auto-generate (fine for dev, not production")
    else:
        add("WARN", ".env not found", "JWT will auto-generate")

    # 4. DEBUG mode
    config_file = backend / "app/core/config.py"
    if config_file.exists():
        content = config_file.read_text(encoding="utf-8")
        if "DEBUG: bool = True" in content:
            add("WARN", "DEBUG=True in config", "Should be False in production")
        else:
            add("PASS", "DEBUG not hardcoded to True")

    # 5. Compliance words check
    forbidden = ["买入", "卖出", "目标价", "止损价", "投资建议", "强烈推荐", "保证收益"]
    found_words = []
    for py_file in (backend / "app").rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            for word in forbidden:
                if word in content:
                    found_words.append(f"{py_file.name}: {word}")
        except:
            pass
    if found_words:
        add("WARN", "Compliance words found", "; ".join(found_words[:5]))
    else:
        add("PASS", "No forbidden compliance words in backend")

    # 6. Auth on protected APIs
    api_dir = backend / "app/api"
    protected_endpoints = []
    for py_file in api_dir.glob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            if "@router.get" in content or "@router.post" in content:
                if "get_current_user" not in content and "get_current_admin" not in content and "get_member_user" not in content:
                    if py_file.name not in ["__init__.py", "auth.py"]:
                        protected_endpoints.append(py_file.name)
        except:
            pass
    if protected_endpoints:
        add("WARN", "API files without auth dependency", ", ".join(protected_endpoints))
    else:
        add("PASS", "All API routes have auth dependencies")

    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
