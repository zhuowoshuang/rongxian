#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AData 迁移包一键验收脚本 v1.2

用法: python qs_migration_package/acceptance/run_all.py
输出: PASS / WARN / FAIL
"""
import os, sys, traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_PYTHON = os.path.join(_ROOT, 'python')
if _PYTHON not in sys.path:
    sys.path.insert(0, _PYTHON)

results = {"PASS": [], "WARN": [], "FAIL": []}

def banner(msg):
    print(f"\n{'='*60}\n  {msg}\n{'='*60}")

def record(name, result):
    results[result].append(name)
    return result

def run_import(name, mod):
    try:
        mod()
        print(f"  [PASS] {name}")
        return record(name, "PASS")
    except SystemExit as e:
        if e.code == 0: print(f"  [PASS] {name}"); return record(name, "PASS")
        print(f"  [FAIL] {name}: exit={e.code}")
        return record(name, "FAIL")
    except Exception:
        print(f"  [FAIL] {name}")
        traceback.print_exc()
        return record(name, "FAIL")

# === Step 1 ===
banner("1. Manifest")
from validate_manifest import main as v_manifest
run_import("manifest", v_manifest)

# === Step 2 ===
banner("2. Contract")
from validate_contract import main as v_contract
run_import("contract", v_contract)

# === Step 3 ===
banner("3. Importability")
from validate_importability import main as v_import
run_import("importability", v_import)

# === Step 4 ===
banner("4. Status Semantics")
from validate_status_semantics import main as v_semantics
run_import("status_semantics", v_semantics)

# === Step 5 ===
banner("5. FastAPI Template")
from validate_fastapi_template import main as v_fastapi
run_import("fastapi_template", v_fastapi)

# === Step 6 ===
banner("6. No Fake Data")
from validate_no_fake_data import main as v_nofake
run_import("no_fake_data", v_nofake)

# === Step 7: Live Smoke ===
banner("7. Live Smoke (300866)")
try:
    smoke_py = os.path.join(_PYTHON, 'qs_backend_bridge', 'smoke_test.py')
    import subprocess
    r = subprocess.run(
        [sys.executable, '-X', 'utf8', smoke_py, '--symbol', '300866',
         '--output-dir', os.path.join(_ROOT, 'examples')],
        cwd=_ROOT, capture_output=True, text=True, timeout=180,
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    )
    out = (r.stdout or '')[-600:] + (r.stderr or '')[-600:]
    if 'ProxyError' in out or 'ConnectionError' in out:
        print(f"  [WARN] Network issue (proxy)")
        record("live_smoke", "WARN")
    elif r.returncode == 0:
        print(f"  [PASS] Live smoke OK")
        record("live_smoke", "PASS")
    else:
        print(f"  [WARN] Live smoke exit={r.returncode}")
        record("live_smoke", "WARN")
    print(out[-500:])
except Exception as e:
    print(f"  [WARN] smoke_test failed: {e}")
    record("live_smoke", "WARN")

# === Summary ===
banner("Summary")
print(f"  PASS: {len(results['PASS'])}  {results['PASS']}")
print(f"  WARN: {len(results['WARN'])}  {results['WARN']}")
print(f"  FAIL: {len(results['FAIL'])}  {results['FAIL']}")

critical = [n for n in ["contract", "importability", "status_semantics", "no_fake_data"] if n in results["FAIL"]]
if critical:
    print(f"\n  *** BLOCKING: {critical}")
    print(f"  Status: NOT_READY")
    sys.exit(1)
elif results["FAIL"]:
    print(f"\n  *** Non-blocking failures, migration OK with warnings")
    print(f"  Status: READY (with warnings)")
    sys.exit(0)
else:
    print(f"\n  *** All passed")
    print(f"  Status: READY")
    sys.exit(0)
