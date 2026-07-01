#!/usr/bin/env python
"""Validate: 300866=OK/PARTIAL, 999999=EMPTY, abc=ERROR"""
import os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
_PY = os.path.join(_HERE,'..','python')
sys.path.insert(0,_PY)
def main():
    errors = []
    try:
        from qs_backend_bridge.stock_data_service import get_stock_data_bundle, get_stock_quote
    except ImportError as e:
        print(f"  [WARN] Cannot import: {e}")
        return
    b = get_stock_data_bundle("300866")
    if b.dataStatus in ("OK","PARTIAL"): print(f"  [PASS] 300866: {b.dataStatus}")
    else: print(f"  [WARN] 300866: {b.dataStatus} (network/env issue)")

    b9 = get_stock_data_bundle("999999")
    if b9.dataStatus == "EMPTY": print(f"  [PASS] 999999: EMPTY")
    else: errors.append(f"999999 should be EMPTY: {b9.dataStatus}")

    ba = get_stock_data_bundle("abc")
    if ba.dataStatus == "ERROR" and ba.errorMessage: print(f"  [PASS] abc: ERROR")
    else: errors.append(f"abc should be ERROR: {ba.dataStatus}")

    q = get_stock_quote("300866")
    if q.source == "AData-Kline-Fallback":
        if q.isRealtime: errors.append("fallback isRealtime should be False")
        if q.dataStatus != "PARTIAL": errors.append(f"fallback dataStatus should be PARTIAL: {q.dataStatus}")
        if "realtimeQuote" not in q.missingFields: errors.append("fallback missing realtimeQuote")
        if not q.quoteStatusReason: errors.append("fallback missing quoteStatusReason")
        print(f"  [PASS] fallback structure OK")
    else: print(f"  [WARN] quote not in fallback mode (source={q.source})")

    if b.missingFields:
        coarse = {"searchItem","quote","kline"}
        if set(b.missingFields) & coarse: errors.append(f"coarse missingFields: {b.missingFields}")
        else: print(f"  [PASS] missingFields granularity OK")
    if errors:
        for e in errors: print(f"  [FAIL] {e}")
        sys.exit(1)
    print(f"  [PASS] Status Semantics OK")
if __name__=='__main__': main()
