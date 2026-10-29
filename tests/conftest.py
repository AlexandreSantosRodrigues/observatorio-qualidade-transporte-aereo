import csv
import io

import pytest

from observatorio.ingestao import HEADERS, OPTIONAL_HEADERS


@pytest.fixture
def voo():
    return {
        "empresa_icao": "TAM", "empresa_nome": "LATAM", "numero_voo": "0001",
        "codigo_di": "0", "tipo_linha": "N", "origem_icao": "SBGL",
        "destino_icao": "SBSP", "partida_prevista": "01/01/2025 10:00",
        "partida_real": "01/01/2025 10:15", "chegada_prevista": "01/01/2025 11:00",
        "chegada_real": "01/01/2025 11:15", "situacao": "REALIZADO",
    }


@pytest.fixture
def csv_bytes():
    def make(rows, encoding="utf-8-sig", remove=None):
        fields = {k: aliases[0] for k, aliases in (HEADERS | OPTIONAL_HEADERS).items() if k != remove}
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(fields.values()), delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(key, "") for key, column in fields.items()})
        return stream.getvalue().encode(encoding)
    return make
