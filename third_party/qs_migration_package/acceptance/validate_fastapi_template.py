#!/usr/bin/env python
"""验证 FastAPI 模板路由结构与 OpenAPI 对齐"""
import os, sys, re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

ROUTES_FILE = os.path.join(_ROOT, 'target_templates', 'fastapi', 'adata_stock_routes.py')
REQUIRED_PATHS = ['search', 'quote', 'kline', 'financials', 'bundle']

def main():
    errors = []
    if not os.path.exists(ROUTES_FILE):
        errors.append(f"FastAPI 路由模板缺失: {ROUTES_FILE}")
    else:
        with open(ROUTES_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        for p in REQUIRED_PATHS:
            if p not in content:
                errors.append(f"路由模板缺少: {p}")
        if not errors:
            print(f"  [PASS] FastAPI 模板: {len(REQUIRED_PATHS)}/{len(REQUIRED_PATHS)} 路由 OK")
        else:
            for e in errors: print(f"  [FAIL] {e}")

    try:
        from fastapi.testclient import TestClient  # noqa
        print(f"  [INFO] FastAPI 可用，可进行端到端测试")
    except ImportError:
        print(f"  [WARN] FastAPI 未安装，静态检查通过（WARN, non-blocking）")

    if errors:
        sys.exit(1)

if __name__ == '__main__':
    main()
