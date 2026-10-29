import json

import pyarrow.parquet as pq
import pytest

from observatorio.ingestao import current_files, ingest, parse_source, prepare_duckdb, source_url


@pytest.mark.parametrize("competencia", ["2025-00", "2025-13", "25-01", "../2025", "2025-1"])
def test_rejeita_competencia_invalida(competencia):
    with pytest.raises(ValueError):
        source_url(competencia)


@pytest.mark.parametrize("encoding", ["utf-8-sig", "cp1252"])
def test_codificacoes_e_voo_alfanumerico(voo, csv_bytes, encoding):
    voo["numero_voo"] = "Z8117"
    voo["empresa_nome"] = "Companhia Aérea"
    accepted, rejected, report = parse_source(csv_bytes([voo], encoding), "2025-01")
    assert len(accepted) == 1 and not rejected and report["reconciliation_ok"]
    assert accepted[0]["numero_voo"] == "Z8117"
    assert accepted[0]["empresa_nome"] == "Companhia Aérea"


def test_schema_invalido_falha_sem_carga(voo, csv_bytes):
    with pytest.raises(ValueError, match="Coluna obrigatória ausente"):
        parse_source(csv_bytes([voo], remove="origem_icao"), "2025-01")


def test_duplicatas_exatas_e_conflitos_sao_reconciliados(voo, csv_bytes):
    other = voo | {"numero_voo": "0002"}
    correction = other | {"chegada_real": "01/01/2025 11:30"}
    accepted, quarantine, report = parse_source(csv_bytes([voo, voo, other, correction]), "2025-01")
    assert len(accepted) == 1
    assert len(quarantine) == 2
    assert report["exact_duplicate_rows"] == 1
    assert report["source_rows"] == 4
    assert report["quarantine_reasons"] == {"chave_conflitante": 2}


@pytest.mark.parametrize("change,reason", [
    ({"partida_real": "32/01/2025 10:00"}, "partida_real_invalida"),
    ({"origem_icao": "???"}, "origem_icao_invalido"),
    ({"partida_prevista": "01/02/2025 10:00", "chegada_prevista": "01/02/2025 11:00",
      "partida_real": "", "chegada_real": ""}, "fora_competencia"),
    ({"situacao": "DESCONHECIDA"}, "situacao_desconhecida"),
    ({"chegada_real": "01/01/2025 09:00"}, "duracao_real_negativa"),
])
def test_quarentena_preserva_linha_invalida(voo, csv_bytes, change, reason):
    accepted, quarantine, report = parse_source(csv_bytes([voo, voo | change]), "2025-01")
    assert len(accepted) == 1 and len(quarantine) == 1
    assert reason in quarantine[0]["motivos"]
    assert report["source_rows"] == report["accepted_rows"] + report["quarantine_rows"]


def test_chave_estavel_com_correcao_de_horario_real(voo, csv_bytes):
    before, _, _ = parse_source(csv_bytes([voo]), "2025-01")
    after, _, _ = parse_source(csv_bytes([voo | {"chegada_real": "01/01/2025 11:30"}]), "2025-01")
    assert before[0]["voo_id"] == after[0]["voo_id"]
    assert before[0]["payload_sha256"] != after[0]["payload_sha256"]


def test_virada_de_dia_e_antecipacao(voo, csv_bytes):
    night = voo | {"partida_prevista": "01/01/2025 23:55", "partida_real": "02/01/2025 00:10",
                   "chegada_prevista": "02/01/2025 02:00", "chegada_real": "02/01/2025 01:50"}
    accepted, _, _ = parse_source(csv_bytes([night]), "2025-01")
    assert accepted[0]["atraso_partida_min"] == 15
    assert accepted[0]["atraso_chegada_min"] == -10


def test_reprocessamento_e_correcao_substituem_so_o_mes(tmp_path, voo, csv_bytes):
    file = tmp_path / "source.csv"
    root = tmp_path / "data"
    file.write_bytes(csv_bytes([voo]))
    first = ingest("2025-01", root, file)
    first_path = current_files(root)[0]
    assert ingest("2025-01", root, file) == first
    file.write_bytes(csv_bytes([voo | {"chegada_real": "01/01/2025 11:30"}]))
    second = ingest("2025-01", root, file)
    assert second["source_sha256"] != first["source_sha256"]
    assert first_path.exists() and len(current_files(root)) == 1
    assert pq.read_table(current_files(root)[0]).num_rows == 1
    assert pq.read_table(current_files(root)[0])["atraso_chegada_min"].to_pylist() == [30]
    prepare_duckdb(root)
    current = (root / "releases/2025-01/CURRENT.json").read_bytes()
    file.write_text("<html>Erro</html>")
    with pytest.raises(ValueError):
        ingest("2025-01", root, file)
    assert (root / "releases/2025-01/CURRENT.json").read_bytes() == current
    assert json.loads(current)["sha256"] == current_files(root)[0].parent.name
