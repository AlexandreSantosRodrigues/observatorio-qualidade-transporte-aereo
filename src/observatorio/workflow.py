"""Executa dbt e exporta evidências. Uma falha impede a publicação dos novos exports."""

import argparse
import csv
import json
import os
import re
import uuid
from pathlib import Path

import duckdb
from dbt.cli.main import dbtRunner
from dbt.adapters.factory import cleanup_connections

from .ingestao import atomic_json, current_files, prepare_duckdb

REPO_ROOT = Path(__file__).resolve().parents[2]


def dbt_command(command: list[str], root: Path, target: str = "duckdb"):
    profile_dir = root / "profiles"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "profiles.yml").write_text(
        (REPO_ROOT / "dbt/profiles.yml.example").read_text(), encoding="utf-8"
    )
    os.environ["OBS_DUCKDB_PATH"] = str(root / "observatorio.duckdb")
    try:
        result = dbtRunner().invoke(command + [
            "--project-dir", str(REPO_ROOT / "dbt"), "--profiles-dir", str(profile_dir),
            "--target", target,
        ])
    finally:
        cleanup_connections()
    if not result.success:
        raise RuntimeError(f"dbt {' '.join(command)} falhou: {result.exception or 'ver logs'}")
    return result


def published_exports(root: Path) -> Path:
    run_id = json.loads((root / "exports/CURRENT.json").read_text())["run_id"]
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise ValueError("Ponteiro de publicação inválido.")
    return root / "exports" / run_id


def export_results(root: Path) -> tuple[dict, Path]:
    exports = root / "exports" / uuid.uuid4().hex
    exports.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(root / "observatorio.duckdb")) as con:
        for model in ("dim_data", "dim_companhia", "dim_aeroporto", "fct_voos", "mart_rotas_mensal"):
            cursor = con.execute(f'SELECT * FROM analytics."{model}" ORDER BY 1, 2')
            columns = [d[0] for d in cursor.description]
            # Escrita incremental, sem carregar o fato inteiro de novo na memória.
            with (exports / f"{model}.csv.tmp").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(columns)
                while rows := cursor.fetchmany(10000):
                    writer.writerows(rows)
            (exports / f"{model}.csv.tmp").replace(exports / f"{model}.csv")
        row = con.execute("""
            SELECT count(*) as etapas, count(distinct empresa_icao) as companhias,
                   count(distinct data_voo) as dias,
                   sum(case when realizado then 1 else 0 end) as realizadas,
                   sum(case when cancelado then 1 else 0 end) as canceladas,
                   sum(case when planejado then 1 else 0 end) as planejadas,
                   sum(case when cancelado and planejado then 1 else 0 end) as canceladas_planejadas,
                   sum(case when elegivel_chegada then 1 else 0 end) as elegiveis_chegada,
                   sum(case when atraso_chegada_15 then 1 else 0 end) as atrasos_chegada_15,
                   sum(case when envolve_gig_sdu then 1 else 0 end) as etapas_gig_sdu
            FROM analytics.fct_voos
        """).fetchone()
        columns = [d[0] for d in con.description]
        con.execute("CHECKPOINT")
    summary = dict(zip(columns, row))
    summary["taxa_cancelamento"] = (
        summary["canceladas_planejadas"] / summary["planejadas"] if summary["planejadas"] else None
    )
    summary["pontualidade_chegada_15"] = (
        1 - summary["atrasos_chegada_15"] / summary["elegiveis_chegada"]
        if summary["elegiveis_chegada"] else None
    )
    atomic_json(exports / "resumo.json", summary)
    return summary, exports


def run(root: Path) -> dict:
    root = root.resolve()
    prepare_duckdb(root)
    dbt_command(["build"], root)
    results = json.loads((REPO_ROOT / "dbt/target/run_results.json").read_text())
    dbt_command(["docs", "generate", "--static"], root)
    summary, exports = export_results(root)
    manifests = [json.loads(p.with_name("manifesto.json").read_text()) for p in current_files(root)]
    evidence = {
        "engine": "duckdb", "bigquery_executed": False,
        "dbt_generated_at": results["metadata"]["generated_at"],
        "dbt_results": [{"unique_id": r["unique_id"], "status": r["status"],
                         "failures": r.get("failures")} for r in results["results"]],
        "sources": manifests, "summary": summary,
    }
    atomic_json(exports / "evidencias.json", evidence)
    atomic_json(root / "exports/CURRENT.json", {"run_id": exports.name})
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("data"))
    args = parser.parse_args()
    print(json.dumps(run(args.root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
