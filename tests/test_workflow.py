"""Publicação completa e preservação do ponteiro quando um export falha."""

import json
import shutil
from pathlib import Path

import pytest

from observatorio.ingestao import ingest
from observatorio import workflow


def test_workflow_publica_somente_conjunto_validado(tmp_path, monkeypatch):
    project = tmp_path / "project"
    shutil.copytree(Path(__file__).resolve().parents[1] / "dbt", project / "dbt",
                    ignore=shutil.ignore_patterns("target", "logs", ".user.yml"))
    monkeypatch.setattr(workflow, "REPO_ROOT", project)
    monkeypatch.setenv("DBT_SEND_ANONYMOUS_USAGE_STATS", "false")
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    root = tmp_path / "data"
    ingest("2025-01", root, Path(__file__).parent / "fixtures/vra_sintetico.csv")

    evidence = workflow.run(root)
    previous = (root / "exports/CURRENT.json").read_bytes()
    exports = workflow.published_exports(root)
    assert evidence["summary"]["etapas"] == 4
    assert len(evidence["dbt_results"]) == 33
    assert all(item["status"] == "success" or item["status"] == "pass"
               for item in evidence["dbt_results"])
    for name in ("dim_companhia", "dim_aeroporto", "dim_data", "fct_voos",
                 "mart_rotas_mensal"):
        assert (exports / f"{name}.csv").stat().st_size > 0
    assert json.loads((exports / "evidencias.json").read_text()) == evidence
    assert (project / "dbt/target/static_index.html").is_file()

    def fail_export(_root):
        raise RuntimeError("falha simulada de exportação")

    monkeypatch.setattr(workflow, "export_results", fail_export)
    with pytest.raises(RuntimeError, match="falha simulada"):
        workflow.run(root)
    assert (root / "exports/CURRENT.json").read_bytes() == previous
    assert workflow.published_exports(root) == exports
