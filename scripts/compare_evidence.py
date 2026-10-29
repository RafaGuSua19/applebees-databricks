"""Compara conteos y huellas agregadas de dos snapshots de evidencia."""
import argparse
import json
from pathlib import Path


def fingerprints(path):
    document = json.loads(path.read_text())
    result = next((r for r in document["results"] if r["file"] == "idempotencia.sql"), None)
    if result is None:
        raise ValueError(f"Falta idempotencia.sql en {path}")
    return {row[0]: tuple(row[1:]) for row in result["rows"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()
    before, after = fingerprints(args.before), fingerprints(args.after)
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    if not before or changed:
        raise SystemExit("Falló idempotencia: " + ", ".join(changed or ["snapshot vacío"]))
    print(f"Idempotencia OK: conteos y huellas coinciden en {len(before)} tablas.")


if __name__ == "__main__":
    main()
