"""
pipeline.py — Lê do DuckDB local e executa o pipeline de detecção de fraude.

Pré-requisito: rodar ingest.py ao menos uma vez.

Uso:
    python3 pipeline.py
    python3 pipeline.py --fonte CPGF VIAGENS   # filtra fontes
    python3 pipeline.py --ano 2022 2023         # filtra anos
    python3 pipeline.py --chunk-size 300000     # ajusta RAM por chunk (padrão 500k)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Iterator

import duckdb
import pandas as pd
from dotenv import load_dotenv

# ── Bootstrap ─────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

load_dotenv(PROJECT_ROOT / "dev.env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "contingency.settings")

from mathCore.benfordLaw import (
    CHUNK_SIZE,
    detectar_fraude_chunked,
    imprimir_relatorio,
)

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Configuração ─────────────────────────────────────────────────────────────

DB_PATH    = PROJECT_ROOT / "pipeline.duckdb"
OUTPUT_CSV = PROJECT_ROOT / "resultado_fraude_consolidado.csv"

COLUNA_VALOR    = "valor"
COLUNA_FONTE    = "fonte"
COLUNAS_CLUSTER = ["orgao", "ano", "funcao"]

# CEIS não tem valor monetário real — excluída da análise de Benford
FONTES_SEM_VALOR_MONETARIO: frozenset[str] = frozenset({"CEIS"})


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline Benford sobre DuckDB local")
    parser.add_argument("--fonte", nargs="+", metavar="FONTE",
                        help="Filtrar por fonte (ex: CPGF VIAGENS).")
    parser.add_argument("--ano", nargs="+", type=int, metavar="ANO",
                        help="Filtrar por ano (ex: 2022 2023).")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE,
                        dest="chunk_size",
                        help=f"Registros por chunk (padrão {CHUNK_SIZE:,}). "
                             "Reduza se a RAM esgotar.")
    return parser.parse_args()


# ── Query builder ─────────────────────────────────────────────────────────────

def _build_where(fontes: list[str] | None, anos: list[int] | None) -> tuple[str, list]:
    clauses = [
        "valor IS NOT NULL",
        "valor > 0",
        f"fonte NOT IN ({', '.join(repr(f) for f in FONTES_SEM_VALOR_MONETARIO)})",
    ]
    params: list = []

    if fontes:
        placeholders = ", ".join(["?"] * len(fontes))
        clauses.append(f"fonte IN ({placeholders})")
        params.extend([f.upper() for f in fontes])

    if anos:
        placeholders = ", ".join(["?"] * len(anos))
        clauses.append(f"ano IN ({placeholders})")
        params.extend(anos)

    return "WHERE " + " AND ".join(clauses), params


# ── Gerador de chunks direto do DuckDB ────────────────────────────────────────

def _chunks_do_db(
    where_clause: str,
    params: list,
    chunk_size: int,
) -> Iterator[pd.DataFrame]:
    """
    Lê o DuckDB em chunks via fetchmany — nunca carrega tudo na RAM de uma vez.
    Cada chunk é um DataFrame independente; o anterior pode ser coletado pelo GC.
    """
    query = f"""
        SELECT valor, orgao, ano, funcao, fonte, favorecido, cpf_cnpj
        FROM dados
        {where_clause}
    """
    with duckdb.connect(str(DB_PATH), read_only=True) as db:
        rel    = db.execute(query, params)
        colunas = [desc[0] for desc in rel.description]
        while True:
            rows = rel.fetchmany(chunk_size)
            if not rows:
                break
            yield pd.DataFrame(rows, columns=colunas)


# ── Resumo do DB ──────────────────────────────────────────────────────────────

def _log_resumo_db(where_clause: str, params: list) -> None:
    with duckdb.connect(str(DB_PATH), read_only=True) as db:
        # Fontes disponíveis
        fontes = [r[0] for r in db.execute(
            "SELECT DISTINCT fonte FROM dados ORDER BY fonte"
        ).fetchall()]
        if not fontes:
            log.error("DB vazio. Execute: python3 ingest.py")
            sys.exit(1)

        # Contagem por fonte no filtro atual
        count_query = f"SELECT fonte, COUNT(*) FROM dados {where_clause} GROUP BY fonte ORDER BY fonte"
        rows = db.execute(count_query, params).fetchall()

    log.info("Fontes no filtro atual:")
    total = 0
    for fonte, n in rows:
        sufixo = " (excluída do Benford)" if fonte in FONTES_SEM_VALOR_MONETARIO else ""
        log.info("  %-28s %10d registros%s", fonte, n, sufixo)
        total += n
    log.info("  %-28s %10d registros", "TOTAL", total)
    return total


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()

    if not DB_PATH.exists():
        log.error("DB não encontrado: %s", DB_PATH)
        log.error("Execute primeiro: python3 ingest.py")
        sys.exit(1)

    where_clause, params = _build_where(args.fonte, args.ano)

    log.info("DB: %s", DB_PATH)
    log.info("Chunk size: %d registros (~%.0f MB por chunk estimado)",
             args.chunk_size, args.chunk_size * 7 * 8 / 1e6)  # 7 colunas float64

    total = _log_resumo_db(where_clause, params)
    if total == 0:
        log.error("Nenhum dado após filtros. Verifique --fonte e --ano.")
        sys.exit(1)

    log.info("Iniciando pipeline chunked — saída: %s", OUTPUT_CSV)

    # chunks_fn é um callable que reinicia o gerador (necessário para 2 passagens)
    def chunks_fn() -> Iterator[pd.DataFrame]:
        return _chunks_do_db(where_clause, params, args.chunk_size)

    metricas = detectar_fraude_chunked(
        chunks_fn       = chunks_fn,
        output_csv      = str(OUTPUT_CSV),
        colunas_cluster = COLUNAS_CLUSTER,
        coluna_valor    = COLUNA_VALOR,
        chunk_size      = args.chunk_size,
    )

    imprimir_relatorio(df_result=None, metricas=metricas)
    log.info("Resultado salvo em: %s", OUTPUT_CSV)


if __name__ == "__main__":
    main()