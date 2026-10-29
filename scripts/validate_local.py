"""Validaciones reproducibles sin credenciales ni dependencias externas."""
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
files = [p for folder in ("src", "exploration", "tests", "scripts") for p in (ROOT / folder).rglob("*.py")]
for path in files:
    ast.parse(path.read_text(), filename=str(path.relative_to(ROOT)))
print(f"Sintaxis válida: {len(files)} archivos Python", flush=True)
subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests/unit", "-v"], cwd=ROOT, check=True)
subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
