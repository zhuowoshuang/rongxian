#!/usr/bin/env python
"""Validate OpenAPI/TS/examples contract consistency"""
import json, os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
APIS = ['/stocks/search','/stocks/{symbol}/quote','/stocks/{symbol}/kline','/stocks/{symbol}/financials','/stocks/{symbol}/bundle']
def main():
    errors = []
    oaf = os.path.join(_ROOT,'openapi','qs_adata_api.openapi.json')
    if os.path.exists(oaf):
        with open(oaf,'r',encoding='utf-8') as f: oa = json.load(f)
        paths = set(oa.get('paths',{}).keys())
        for a in APIS:
            if a not in paths: errors.append(f"OpenAPI missing: {a}")
        if not errors: print(f"  [PASS] OpenAPI: {len(paths)} paths")
    else: errors.append("OpenAPI JSON missing")

    exd = os.path.join(_ROOT,'examples')
    for fn in ['quote_300866.json','qs_stock_bundle_300866.json']:
        fp = os.path.join(exd,fn)
        if os.path.exists(fp):
            with open(fp,'r',encoding='utf-8') as f: d = json.load(f)
            if 'quoteStatusReason' not in d and fn.startswith('quote'): errors.append(f"{fn} missing quoteStatusReason")
            if not errors: print(f"  [PASS] {fn}")
        else: errors.append(f"missing example: {fn}")

    tsf = os.path.join(_ROOT,'frontend_contract','stock-data-types.ts')
    if os.path.exists(tsf):
        with open(tsf,'r',encoding='utf-8') as f: ts = f.read()
        for k in ['quoteStatusReason','DataStatus']:
            if k not in ts: errors.append(f"TS missing: {k}")
        if not errors: print(f"  [PASS] TS types OK")
    else: errors.append("TS file missing")

    if errors:
        for e in errors: print(f"  [FAIL] {e}")
        sys.exit(1)
    print(f"  [PASS] Contract consistent")
if __name__=='__main__': main()
