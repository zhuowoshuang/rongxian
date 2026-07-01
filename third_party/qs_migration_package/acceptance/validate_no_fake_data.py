#!/usr/bin/env python
"""Scan migration package for fake data patterns"""
import os, sys, re
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
PROHIBITED = [
    (r'Math\.random', 'Math.random()'),
    (r'random\.random', 'random.random()'),
    (r'"score"\s*:\s*91', 'hardcoded score 91'),
    (r'fake.?quote', 'fake quote'),
    (r'mock.?score', 'mock score'),
]
def main():
    errors = []
    for root, dirs, files in os.walk(_ROOT):
        dirs[:] = [d for d in dirs if d not in ('__pycache__','acceptance','examples','fixtures','.git')]
        for fn in files:
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, _ROOT)
            if not fn.endswith(('.py','.ts','.tsx','.md','.json')): continue
            if 'acceptance' in rel.replace(chr(92),'/'): continue
            try:
                with open(fp,'r',encoding='utf-8',errors='ignore') as f: c = f.read()
            except: continue
            for pat, desc in PROHIBITED:
                if re.search(pat, c, re.I):
                    errors.append(f"{rel}: {desc}")
    if errors:
        for e in errors: print(f"  [FAIL] {e}")
        sys.exit(1)
    print(f"  [PASS] No fake data detected")
if __name__=='__main__': main()
