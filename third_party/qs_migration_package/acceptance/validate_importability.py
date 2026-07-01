#!/usr/bin/env python
"""Validate imports work independently"""
import os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
_PY = os.path.join(_HERE,'..','python')
sys.path.insert(0,_PY)
def main():
    errors = []
    try:
        import qs_adapter; print(f"  [PASS] import qs_adapter OK")
    except ImportError as e: errors.append(f"qs_adapter: {e}")
    try:
        import qs_backend_bridge; print(f"  [PASS] import qs_backend_bridge OK")
    except ImportError as e: errors.append(f"qs_backend_bridge: {e}")
    try:
        from qs_backend_bridge.stock_data_service import get_stock_data_bundle
        print(f"  [PASS] import get_stock_data_bundle OK")
    except ImportError as e: errors.append(f"get_stock_data_bundle: {e}")
    try:
        import adata; print(f"  [INFO] adata available")
    except ImportError: print(f"  [WARN] adata not installed (runtime queries will ERROR)")
    if errors:
        for e in errors: print(f"  [FAIL] {e}")
        sys.exit(1)
    print(f"  [PASS] Importability OK")
if __name__=='__main__': main()
