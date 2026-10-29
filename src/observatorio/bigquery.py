"""Integração opcional real, bloqueada se o projeto tem faturamento ou a checagem falha."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from .ingestao import atomic_json, current_files
from .workflow import dbt_command

MAX_UPLOAD_BYTES = 150 * 1024 * 1024


def require_sandbox(project: str, session) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project):
        raise ValueError("ID de projeto GCP inválido.")
    response = session.get(
        f"https://cloudbilling.googleapis.com/v1/projects/{project}/billingInfo", timeout=30
    )
    response.raise_for_status()
    body = response.json()
    if body.get("billingEnabled") is not False:
        raise RuntimeError("Somente projeto com billingEnabled=false é permitido nesta versão.")


def load(root: Path, project: str) -> dict:
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    from google.cloud import bigquery

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    require_sandbox(project, AuthorizedSession(credentials))
    files = current_files(root)
    if sum(p.stat().st_size for p in files) > MAX_UPLOAD_BYTES:
        raise ValueError("Carga acima de 150 MiB comprimidos. Reduza o escopo.")
    client = bigquery.Client(project=project, credentials=credentials, location="US")
    for name in ("vra_bronze", "vra_analytics"):
        dataset = bigquery.Dataset(f"{project}.{name}")
        dataset.location = "US"
        dataset.labels = {"managed_by": "observatorio_vra"}
        dataset.default_table_expiration_ms = 60 * 24 * 60 * 60 * 1000
        client.create_dataset(dataset, exists_ok=True)
        existing = client.get_dataset(dataset.reference)
        if (existing.labels or {}).get("managed_by") != "observatorio_vra":
            raise ValueError(f"Dataset {name} existente sem identificação deste projeto; carga bloqueada.")
        if existing.location != "US":
            raise ValueError(f"Dataset {name} existente fora da região US.")
    # Uma tabela por competência permite reprocessar sem INSERT/MERGE e sem append.
    receipts = []
    for path in files:
        manifest = json.loads(path.with_name("manifesto.json").read_text())
        month = manifest["competencia"].replace("-", "_")
        table = f"{project}.vra_bronze.voos_{month}"
        current = client.get_table(table) if _table_exists(client, table) else None
        identity = {"source_sha_a": manifest["source_sha256"][:32],
                    "source_sha_b": manifest["source_sha256"][32:],
                    "contract_sha_a": manifest["contract_sha256"][:32],
                    "contract_sha_b": manifest["contract_sha256"][32:]}
        if (current and current.num_rows == manifest["accepted_rows"]
                and all((current.labels or {}).get(k) == v for k, v in identity.items())):
            receipts.append({"table": table, "status": "hash_ja_carregado"})
            continue
        config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
        )
        with path.open("rb") as handle:
            job = client.load_table_from_file(handle, table, job_config=config, location="US")
        job.result(timeout=180)
        saved = client.get_table(table)
        if saved.num_rows != manifest["accepted_rows"]:
            raise RuntimeError("Contagem divergente após carga BigQuery.")
        saved.labels = (saved.labels or {}) | identity
        client.update_table(saved, ["labels"])
        receipts.append({"table": table, "status": "carregado", "job_id": job.job_id,
                         "rows": saved.num_rows})
    selects = [f"SELECT * FROM `{project}.vra_bronze.voos_{p.parent.parent.name.replace('-', '_')}`"
               for p in files]
    sql = f"CREATE OR REPLACE VIEW `{project}.vra_bronze.voos` AS " + " UNION ALL ".join(selects)
    client.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000)).result()
    os.environ["GCP_PROJECT_ID"] = project
    dbt_command(["build"], root.resolve(), "bigquery")
    # Não publicar documentos sobre um build não executado: preservar evidência real da nuvem.
    run_result = json.loads((Path(__file__).resolve().parents[2] / "dbt/target/run_results.json").read_text())
    result = {"project": project, "billing_enabled": False, "loads": receipts,
              "dbt_results": [{"unique_id": r["unique_id"], "status": r["status"]}
                              for r in run_result["results"]]}
    atomic_json(root / "gcp-evidence/bigquery.json", result)
    return result


def _table_exists(client, table):
    from google.api_core.exceptions import NotFound
    try:
        client.get_table(table)
        return True
    except NotFound:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--root", type=Path, default=Path("data"))
    args = parser.parse_args()
    print(json.dumps(load(args.root.resolve(), args.project), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
