"""Ejecuta consultas agregadas versionadas mediante la CLI; guarda evidencia fuera de Git."""
import argparse
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="APPLEBEES")
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--catalog", default="workspace")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--only", help="Nombre de un archivo SQL para ejecutar solo esa comprobación")
    parser.add_argument("--output", type=Path, default=ROOT / ".local/validation/evidence.json")
    args = parser.parse_args()

    def api(method, path, payload=None):
        cmd = ["databricks", "api", method, path, "--profile", args.profile, "--output", "json"]
        if payload is not None:
            cmd += ["--json", json.dumps(payload)]
        return json.loads(subprocess.check_output(cmd, text=True))

    results = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for path in sorted((ROOT / "validation/sql").glob("*.sql")):
        if args.only and path.name != args.only:
            continue
        # Los archivos versionados no contienen punto y coma en literales.
        source = "\n".join(line for line in path.read_text().splitlines()
                               if not line.lstrip().startswith("--"))
        for index, sql in enumerate(source.split(";"), 1):
            if not any(line.strip() and not line.lstrip().startswith("--") for line in sql.splitlines()):
                continue
            response = api("post", "/api/2.0/sql/statements", {
                "warehouse_id": args.warehouse_id, "catalog": args.catalog, "schema": args.schema,
                "statement": sql, "wait_timeout": "50s", "on_wait_timeout": "CONTINUE"})
            deadline = time.monotonic() + 600
            while response["status"]["state"] in ("PENDING", "RUNNING"):
                if time.monotonic() > deadline:
                    raise TimeoutError(f"Consulta {path.name}:{index}; statement_id={response['statement_id']}")
                time.sleep(5)
                response = api("get", f"/api/2.0/sql/statements/{response['statement_id']}")
            if response["status"]["state"] != "SUCCEEDED":
                raise RuntimeError(f"{path.name}:{index}: {response['status']}")
            manifest = response.get("manifest", {})
            if manifest.get("truncated") or manifest.get("total_chunk_count", 1) > 1:
                raise RuntimeError(f"Resultado incompleto: {path.name}:{index}")
            results.append({"file": path.name, "query": index, "statement_id": response["statement_id"],
                            "columns": [c["name"] for c in manifest.get("schema", {}).get("columns", [])],
                            "rows": response.get("result", {}).get("data_array", [])})
            args.output.write_text(json.dumps({"catalog": args.catalog, "schema": args.schema,
                                               "results": results}, indent=2, ensure_ascii=False))
            print(f"OK {path.name}:{index}", flush=True)
    if not results:
        raise ValueError("No se seleccionó ninguna consulta")
    print(f"Evidencia completa: {args.output}")


if __name__ == "__main__":
    main()
