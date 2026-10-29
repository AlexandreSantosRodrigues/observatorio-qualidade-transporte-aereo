"""Integração em banco isolado: régua de negócio e prova de que dados ruins falham."""

import json
import os
import shutil
from pathlib import Path

import duckdb
from dbt.cli.main import dbtRunner

from observatorio.ingestao import ingest, prepare_duckdb


def test_dbt_indicadores_e_detecta_corrupcao(tmp_path, voo, csv_bytes, monkeypatch):
    project = tmp_path / "dbt"
    shutil.copytree(Path(__file__).resolve().parents[1] / "dbt", project,
                    ignore=shutil.ignore_patterns("target", "logs", ".user.yml"))
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    shutil.copy(project / "profiles.yml.example", profiles / "profiles.yml")
    rows = [
        voo,  # Exatamente 15 minutos: pontual.
        voo | {"numero_voo": "0002", "chegada_real": "01/01/2025 11:15:01"},
        voo | {"numero_voo": "0003", "situacao": "CANCELADO", "partida_real": "", "chegada_real": ""},
        voo | {"numero_voo": "0004", "chegada_real": ""},
        voo | {"numero_voo": "Z0005", "partida_prevista": "", "chegada_prevista": ""},
        voo | {"numero_voo": "0006", "situacao": "NÃO INFORMADO", "partida_real": "", "chegada_real": ""},
    ]
    file = tmp_path / "synthetic.csv"
    file.write_bytes(csv_bytes(rows))
    root = tmp_path / "data"
    ingest("2025-01", root, file)
    db = prepare_duckdb(root)
    monkeypatch.setenv("OBS_DUCKDB_PATH", str(db))
    monkeypatch.setenv("DBT_SEND_ANONYMOUS_USAGE_STATS", "false")
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    common = ["--project-dir", str(project), "--profiles-dir", str(profiles), "--target", "duckdb"]
    result = dbtRunner().invoke(["build", *common])
    assert result.success, result.exception
    with duckdb.connect(str(db)) as con:
        row = con.execute("SELECT total_etapas, etapas_planejadas, canceladas_planejadas, "
                          "elegiveis_chegada, atrasos_chegada_15, pontualidade_chegada_15 "
                          "FROM analytics.mart_rotas_mensal").fetchone()
        assert row == (6, 5, 1, 2, 1, 0.5)
        con.execute("DELETE FROM analytics.dim_companhia")
        con.execute("UPDATE analytics.fct_voos SET atraso_chegada_15=true WHERE cancelado")
    failed = dbtRunner().invoke(["test", "--select", "test_name:relationships", "elegibilidade", *common])
    assert not failed.success
    result = json.loads((project / "target/run_results.json").read_text())
    failures = [r for r in result["results"] if r["status"] == "fail"]
    assert len(failures) >= 2  # FK órfã e cancelamento indevidamente elegível.
    assert all((r.get("failures") or 0) > 0 for r in failures)
    assert os.environ["OBS_DUCKDB_PATH"] == str(db)
