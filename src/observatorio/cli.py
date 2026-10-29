"""CLI usada no Colab, na integração contínua e para reprodução local opcional."""

import argparse
import json
from pathlib import Path

from .ingestao import ingest, prepare_duckdb


def main():
    parser = argparse.ArgumentParser(description="Observatório VRA/ANAC")
    sub = parser.add_subparsers(dest="command", required=True)
    load = sub.add_parser("ingest", help="Baixar e validar uma competência")
    load.add_argument("--competencia", required=True)
    load.add_argument("--arquivo", type=Path, help="CSV local; origem não será rotulada como download")
    load.add_argument("--root", type=Path, default=Path("data"))
    prepare = sub.add_parser("prepare", help="Reconstituir bronze no DuckDB")
    prepare.add_argument("--root", type=Path, default=Path("data"))
    args = parser.parse_args()
    if args.command == "ingest":
        result = ingest(args.competencia, args.root, args.arquivo)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(prepare_duckdb(args.root))


if __name__ == "__main__":
    main()
