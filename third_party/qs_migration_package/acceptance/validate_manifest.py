#!/usr/bin/env python
"""Validate package_manifest.json"""
import json, os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
_MANIFEST = os.path.join(_HERE, '..', 'package_manifest.json')
REQUIRED = ['packageName','version','generatedAt','includedFiles','requiredPythonPackages','supportedFunctions','verifiedCases','migrationReadiness','testCommands','knownLimitations']
MIG_KEYS = ['backendReady','frontendReady','contractFrozen','blockingIssues']
def main():
    with open(_MANIFEST,'r',encoding='utf-8') as f: m = json.load(f)
    errors = [f"missing: {k}" for k in REQUIRED if k not in m]
    errors += [f"missing migrationReadiness.{k}" for k in MIG_KEYS if k not in m.get('migrationReadiness',{})]
    if errors:
        for e in errors: print(f"  [FAIL] {e}")
        sys.exit(1)
    print(f"  [PASS] manifest OK: {m['packageName']} v{m['version']}")
if __name__=='__main__': main()
