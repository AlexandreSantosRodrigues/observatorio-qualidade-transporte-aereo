"""Carga mensal idempotente. CSV original é conservado por hash; conflitos não são escolhidos."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

BASE_URL = "https://siros.anac.gov.br/siros/registros/diversos/vra"
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024


def normalizar(text: str) -> str:
    return " ".join(
        "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
        .upper()
        .split()
    )


HEADERS = {
    "empresa_icao": ["Sigla ICAO Empresa Aérea", "ICAO Empresa Aérea"],
    "numero_voo": ["Número Voo"],
    "codigo_di": ["Código DI"],
    "tipo_linha": ["Código Tipo Linha"],
    "origem_icao": ["Sigla ICAO Aeroporto Origem", "ICAO Aeródromo Origem"],
    "destino_icao": ["Sigla ICAO Aeroporto Destino", "ICAO Aeródromo Destino"],
    "partida_prevista": ["Partida Prevista"],
    "partida_real": ["Partida Real"],
    "chegada_prevista": ["Chegada Prevista"],
    "chegada_real": ["Chegada Real"],
    "situacao": ["Situação Voo", "Situação do voo"],
}
OPTIONAL_HEADERS = {
    "empresa_nome": ["Empresa Aérea"],
    "origem_descricao": ["Descrição Aeroporto Origem"],
    "destino_descricao": ["Descrição Aeroporto Destino"],
    "justificativa": ["Justificativa", "Código Justificativa"],
}
DATES = ("partida_prevista", "partida_real", "chegada_prevista", "chegada_real")
TEXT_FIELDS = list(HEADERS) + list(OPTIONAL_HEADERS) + [
    "voo_id", "data_voo", "competencia", "source_sha256", "payload_sha256"
]
SCHEMA = pa.schema(
    [(name, pa.string()) for name in TEXT_FIELDS]
    + [("source_line", pa.int64()), ("atraso_partida_min", pa.float64()),
       ("atraso_chegada_min", pa.float64())]
)


def validar_competencia(competencia: str) -> None:
    if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", competencia):
        raise ValueError("Competência deve ser AAAA-MM, entre 2000 e 2099.")


def source_url(competencia: str) -> str:
    validar_competencia(competencia)
    ano, mes = competencia.split("-")
    return f"{BASE_URL}/{ano}/VRA_{ano}_{mes}.csv"


def download(competencia: str, root: Path) -> tuple[bytes, str]:
    """Falha em HTML, corpo truncado e resposta acima do orçamento; nunca usa mirrors."""
    url = source_url(competencia)
    request = urllib.request.Request(url, headers={"User-Agent": "ObservatorioVRA/0.1"})
    with urllib.request.urlopen(request, timeout=90) as response:
        size = response.headers.get("Content-Length")
        if size and int(size) > MAX_DOWNLOAD_BYTES:
            raise ValueError("Arquivo excede o limite de 100 MiB por mês.")
        content = response.read(MAX_DOWNLOAD_BYTES + 1)
        if size and len(content) != int(size):
            raise ValueError("Download incompleto; nenhuma carga foi publicada.")
    if len(content) > MAX_DOWNLOAD_BYTES:
        raise ValueError("Arquivo excede o limite de 100 MiB por mês.")
    if b"<html" in content[:512].lower() or b"<!doctype" in content[:512].lower():
        raise ValueError("Fonte retornou HTML em vez de CSV.")
    return content, url


def parse_datetime(value: str) -> datetime | None:
    if not value.strip():
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Data inválida: {value!r}")


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def parse_source(content: bytes, competencia: str) -> tuple[list[dict], list[dict], dict]:
    validar_competencia(competencia)
    try:
        text = content.decode("utf-8-sig")
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        text = content.decode("cp1252")
        encoding = "cp1252"
    reader = csv.DictReader(io.StringIO(text), delimiter=";", strict=True)
    if not reader.fieldnames:
        raise ValueError("CSV vazio.")
    original = reader.fieldnames
    lookup = {normalizar(h): h for h in original}
    if len(lookup) != len(original):
        raise ValueError("Cabeçalhos duplicados após normalização.")
    mapping = {}
    for target, aliases in (HEADERS | OPTIONAL_HEADERS).items():
        matches = [lookup[normalizar(a)] for a in aliases if normalizar(a) in lookup]
        if len(matches) > 1:
            raise ValueError(f"Cabeçalho ambíguo: {target}")
        if not matches and target in HEADERS:
            raise ValueError(f"Coluna obrigatória ausente: {aliases[0]}")
        mapping[target] = matches[0] if matches else None

    source_hash = hashlib.sha256(content).hexdigest()
    candidates, quarantine = [], []
    total = 0
    for raw in reader:
        total += 1
        line = reader.line_num
        reasons = []
        if None in raw or any(v is None for v in raw.values()):
            reasons.append("largura_csv_invalida")
        row = {k: (raw.get(v) or "").strip() if v else "" for k, v in mapping.items()}
        for name in ("empresa_icao", "numero_voo", "codigo_di", "tipo_linha",
                     "origem_icao", "destino_icao", "situacao"):
            row[name] = normalizar(row[name])
        for name, regex in (("empresa_icao", r"[A-Z0-9]{3}"),
                            ("origem_icao", r"[A-Z0-9]{4}"),
                            ("destino_icao", r"[A-Z0-9]{4}"),
                            ("numero_voo", r"[A-Z0-9]{1,8}"),
                            ("codigo_di", r"[A-Z0-9]"),
                            ("tipo_linha", r"[A-Z]")):
            if not re.fullmatch(regex, row[name]):
                reasons.append(f"{name}_invalido")
        if row["situacao"] not in {"REALIZADO", "CANCELADO", "NAO INFORMADO"}:
            reasons.append("situacao_desconhecida")
        timestamps = {}
        for name in DATES:
            try:
                timestamps[name] = parse_datetime(row[name])
            except ValueError:
                timestamps[name] = None
                reasons.append(f"{name}_invalida")
        date_ref = timestamps["partida_prevista"] or timestamps["partida_real"]
        if date_ref is None:
            reasons.append("sem_data_referencia")
        elif date_ref.strftime("%Y-%m") != competencia:
            reasons.append("fora_competencia")
        for kind in ("prevista", "real"):
            start, end = timestamps[f"partida_{kind}"], timestamps[f"chegada_{kind}"]
            if start and end and end < start:
                reasons.append(f"duracao_{kind}_negativa")
        for name in DATES:
            row[name] = timestamps[name].isoformat(sep=" ") if timestamps[name] else None
        row["numero_voo"] = row["numero_voo"].zfill(4)
        row.update(source_line=line, source_sha256=source_hash, competencia=competencia)
        row["data_voo"] = date_ref.date().isoformat() if date_ref else None
        row["payload_sha256"] = digest(sorted((k, v) for k, v in raw.items() if k))
        row["voo_id"] = digest([row[k] for k in (
            "empresa_icao", "numero_voo", "codigo_di", "tipo_linha", "origem_icao",
            "destino_icao", "partida_prevista"
        )] + [None if row["partida_prevista"] else row["partida_real"]])
        for label in ("partida", "chegada"):
            planned, actual = timestamps[f"{label}_prevista"], timestamps[f"{label}_real"]
            row[f"atraso_{label}_min"] = (
                (actual - planned).total_seconds() / 60 if planned and actual else None
            )
        if reasons:
            quarantine.append({"source_line": line, "motivos": sorted(set(reasons)), "dados": row})
        else:
            candidates.append(row)

    groups = {}
    for row in candidates:
        groups.setdefault(row["voo_id"], []).append(row)
    accepted = []
    duplicates = 0
    for rows in groups.values():
        if len({r["payload_sha256"] for r in rows}) > 1:
            quarantine.extend({"source_line": r["source_line"], "motivos": ["chave_conflitante"],
                               "dados": r} for r in rows)
        else:
            accepted.append(rows[0])
            duplicates += len(rows) - 1
    reasons = Counter(reason for r in quarantine for reason in r["motivos"])
    if not accepted:
        raise ValueError("Nenhuma linha válida; publicação anterior foi preservada.")
    assert total == len(accepted) + len(quarantine) + duplicates
    report = {
        "competencia": competencia, "source_sha256": source_hash, "source_bytes": len(content),
        "encoding": encoding, "source_columns": original, "source_rows": total,
        "accepted_rows": len(accepted), "quarantine_rows": len(quarantine),
        "exact_duplicate_rows": duplicates, "quarantine_reasons": dict(reasons),
        "reconciliation_ok": True,
        "status_counts": dict(Counter(r["situacao"] for r in accepted)),
    }
    return accepted, quarantine, report


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def ingest(competencia: str, root: Path, local_file: Path | None = None) -> dict:
    """Substitui apenas a competência, sem append. O caller declara a origem local, se usada."""
    validar_competencia(competencia)
    root = root.resolve()
    content, url = (local_file.read_bytes(), "arquivo_local") if local_file else download(competencia, root)
    accepted, quarantine, report = parse_source(content, competencia)
    contract_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report.update(source_url=url, ingested_at=datetime.now(timezone.utc).isoformat(),
                  contract_sha256=contract_hash)
    archive = root / "raw" / competencia / f"{report['source_sha256']}.csv"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        archive.write_bytes(content)
    # Versão imutável; CURRENT.json é o único ponto de publicação por competência.
    release_id = digest([report["source_sha256"], contract_hash])
    release = root / "releases" / competencia / release_id
    release.mkdir(parents=True, exist_ok=True)
    if not (release / "manifesto.json").exists():
        pq.write_table(pa.Table.from_pylist(accepted, schema=SCHEMA), release / "voos.parquet",
                       compression="zstd")
        report["parquet_sha256"] = hashlib.sha256((release / "voos.parquet").read_bytes()).hexdigest()
        atomic_json(release / "quarentena.json", quarantine)
        atomic_json(release / "manifesto.json", report)
    else:
        report = json.loads((release / "manifesto.json").read_text())
        validate_release(release)
    atomic_json(root / "releases" / competencia / "CURRENT.json", {"sha256": release_id})
    return report


def validate_release(release: Path) -> None:
    report = json.loads((release / "manifesto.json").read_text())
    path = release / "voos.parquet"
    if (not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != report["parquet_sha256"]
            or pq.read_metadata(path).num_rows != report["accepted_rows"]):
        raise ValueError("Release ausente ou corrompido; carga bloqueada.")


def current_files(root: Path) -> list[Path]:
    result = []
    for pointer in sorted((root / "releases").glob("*/CURRENT.json")):
        sha = json.loads(pointer.read_text())["sha256"]
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("Manifesto CURRENT inválido.")
        release = pointer.parent / sha
        validate_release(release)
        result.append(release / "voos.parquet")
    if not result:
        raise ValueError("Nenhuma competência carregada.")
    return result


def prepare_duckdb(root: Path) -> Path:
    root = root.resolve()
    database = root / "observatorio.duckdb"
    files = [str(p) for p in current_files(root)]
    with duckdb.connect(str(database)) as con:
        con.execute("SET checkpoint_threshold='1TB'")
        con.execute("BEGIN TRANSACTION")
        con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        con.execute("CREATE OR REPLACE TABLE bronze.voos AS SELECT * FROM read_parquet(?)", [files])
        con.execute("COMMIT")
        con.execute("CHECKPOINT")
    return database
