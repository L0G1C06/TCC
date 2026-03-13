"""
pipeline.py — Lê do DuckDB local e executa o pipeline de detecção de fraude.

Pré-requisito: rodar ingest.py ao menos uma vez.

Uso:
    python3 pipeline.py
    python3 pipeline.py --fonte CPGF VIAGENS       # filtra fontes
    python3 pipeline.py --ano 2022 2023             # filtra anos
    python3 pipeline.py --chunk-size 300000         # ajusta RAM por chunk (padrão 500k)
    python3 pipeline.py --bunching                  # ativa análise de limiares legais
    python3 pipeline.py --sem-sensibilidade         # desativa LHS (mais rápido)
    python3 pipeline.py --grafos                    # ativa análise de redes
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

# ── PATCH: importa os novos símbolos do benfordLaw ────────────────────────────
from mathCore.benfordLaw import (
    CHUNK_SIZE,
    detectar_fraude_chunked,
    imprimir_relatorio,
    construir_grafo_contratacoes,
    detectar_empresa_prateleira,
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
COLUNA_ORGAO    = "orgao"
COLUNA_UF       = "uf"
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
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, dest="chunk_size",
                        help=f"Registros por chunk (padrão {CHUNK_SIZE:,}). "
                             "Reduza se a RAM esgotar.")
    # ── PATCH: novos flags ────────────────────────────────────────────────────
    parser.add_argument("--bunching", action="store_true",
                        help="Ativa análise de bunching/limiares legais (Lei 14.133/2021).")
    parser.add_argument("--sem-sensibilidade", action="store_true", dest="sem_sensibilidade",
                        help="Desativa análise de sensibilidade LHS (mais rápido).")
    parser.add_argument("--grafos", action="store_true",
                        help="Ativa análise de redes de beneficiários (requer networkx).")
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
    incluir_cpf_cnpj: bool = False,   # PATCH: parâmetro para análise de redes
) -> Iterator[pd.DataFrame]:
    """
    Lê o DuckDB em chunks via fetchmany — nunca carrega tudo na RAM de uma vez.
    Cada chunk é um DataFrame independente; o anterior pode ser coletado pelo GC.
    """
    # PATCH: inclui cpf_cnpj quando a análise de redes está ativa
    colunas_extra = ", cpf_cnpj" if incluir_cpf_cnpj else ", cpf_cnpj"
    query = f"""
        SELECT valor, orgao, ano, funcao, fonte, favorecido{colunas_extra}
        FROM dados
        {where_clause}
    """
    with duckdb.connect(str(DB_PATH), read_only=True) as db:
        rel     = db.execute(query, params)
        colunas = [desc[0] for desc in rel.description]
        while True:
            rows = rel.fetchmany(chunk_size)
            if not rows:
                break
            yield pd.DataFrame(rows, columns=colunas)


# ── Resumo do DB ──────────────────────────────────────────────────────────────

def _log_resumo_db(where_clause: str, params: list) -> int:
    with duckdb.connect(str(DB_PATH), read_only=True) as db:
        fontes = [r[0] for r in db.execute(
            "SELECT DISTINCT fonte FROM dados ORDER BY fonte"
        ).fetchall()]
        if not fontes:
            log.error("DB vazio. Execute: python3 ingest.py")
            sys.exit(1)

        rows = db.execute(
            f"SELECT fonte, COUNT(*) FROM dados {where_clause} GROUP BY fonte ORDER BY fonte",
            params,
        ).fetchall()

    log.info("Fontes no filtro atual:")
    total = 0
    for fonte, n in rows:
        sufixo = " (excluída do Benford)" if fonte in FONTES_SEM_VALOR_MONETARIO else ""
        log.info("  %-28s %10d registros%s", fonte, n, sufixo)
        total += n
    log.info("  %-28s %10d registros", "TOTAL", total)
    return total


# ── PATCH M7: análise de redes (pós-pipeline) ────────────────────────────────

def _rodar_analise_grafos(
    where_clause: str,
    params: list,
    chunk_size: int,
) -> None:
    """
    Constrói o grafo bipartido órgão ↔ fornecedor sobre uma amostra do DB
    e imprime o relatório de empresas de prateleira.
    Limitado a 500k registros para não saturar a RAM.
    """
    log.info("Carregando amostra para análise de redes (máx 500k registros)...")
    MAX_GRAFOS = 500_000
    dfs = []
    n   = 0
    for chunk in _chunks_do_db(where_clause, params, chunk_size, incluir_cpf_cnpj=True):
        dfs.append(chunk[["orgao", "cpf_cnpj", "valor"]].dropna())
        n += len(chunk)
        if n >= MAX_GRAFOS:
            break

    if not dfs:
        log.warning("Nenhum dado disponível para análise de redes.")
        return

    df_rede = pd.concat(dfs, ignore_index=True)
    del dfs

    log.info("Construindo grafo bipartido (%d registros)...", len(df_rede))
    try:
        import networkx as nx
        G         = construir_grafo_contratacoes(df_rede)
        n_orgaos  = sum(1 for _, d in G.nodes(data=True) if d.get("type") == "orgao")
        n_fornec  = sum(1 for _, d in G.nodes(data=True) if d.get("type") == "fornecedor")
        vol_total = sum(d["peso"] for _, _, d in G.edges(data=True))
        log.info(
            "Grafo: %d órgãos  %d fornecedores  %d contratos  R$ %.2fM total",
            n_orgaos, n_fornec, G.number_of_edges(), vol_total / 1e6,
        )

        prateleira = detectar_empresa_prateleira(df_rede)
        if prateleira.empty:
            log.info("Nenhuma empresa de prateleira detectada.")
        else:
            n_alto = (prateleira["nivel"] == "alto").sum()
            n_mod  = (prateleira["nivel"] == "moderado").sum()
            log.info("Empresas de prateleira — alto risco: %d  moderado: %d", n_alto, n_mod)
            print("\n🕸️  EMPRESAS DE PRATELEIRA (top 20)")
            print(prateleira.head(20).to_string(index=False))

        grafo_path = PROJECT_ROOT / "grafo_contratacoes.graphml"
        nx.write_graphml(G, str(grafo_path))
        log.info("Grafo exportado: %s", grafo_path)

    except ImportError:
        log.warning("networkx não instalado. pip install networkx")
    except Exception as e:
        log.error("Análise de grafos falhou: %s", e)

    del df_rede


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
             args.chunk_size, args.chunk_size * 7 * 8 / 1e6)

    # ── PATCH: lê e loga os flags ativos ─────────────────────────────────────
    incluir_sensibilidade = not args.sem_sensibilidade
    incluir_bunching      = args.bunching
    incluir_grafos        = args.grafos

    if incluir_sensibilidade:
        log.info("✅ Análise de sensibilidade LHS ativada (500 cenários)")
    if incluir_bunching:
        log.info("✅ Análise de bunching ativada (limiares Lei 14.133/2021)")
    if incluir_grafos:
        log.info("✅ Análise de redes ativada")

    total = _log_resumo_db(where_clause, params)
    if total == 0:
        log.error("Nenhum dado após filtros. Verifique --fonte e --ano.")
        sys.exit(1)

    log.info("Iniciando pipeline chunked — saída: %s", OUTPUT_CSV)

    def chunks_fn() -> Iterator[pd.DataFrame]:
        return _chunks_do_db(where_clause, params, args.chunk_size)

    # ── PATCH: passa novos parâmetros para detectar_fraude_chunked ────────────
    metricas = detectar_fraude_chunked(
        chunks_fn             = chunks_fn,
        output_csv            = str(OUTPUT_CSV),
        colunas_cluster       = COLUNAS_CLUSTER,
        coluna_valor          = COLUNA_VALOR,
        chunk_size            = args.chunk_size,
        incluir_sensibilidade = incluir_sensibilidade,
        incluir_bunching      = incluir_bunching,
        col_uf                = COLUNA_UF,
        col_orgao             = COLUNA_ORGAO,
    )

    imprimir_relatorio(df_result=None, metricas=metricas)
    log.info("Resultado salvo em: %s", OUTPUT_CSV)

    # ── PATCH M7: análise de redes roda após o pipeline principal ────────────
    if incluir_grafos:
        _rodar_analise_grafos(where_clause, params, args.chunk_size)


if __name__ == "__main__":
    main()