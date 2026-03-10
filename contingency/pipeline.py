"""
pipeline.py — Lê do DuckDB local e roda o pipeline de detecção de fraude.

Pré-requisito: rodar ingest.py ao menos uma vez.

Uso:
    python3 pipeline.py
    python3 pipeline.py --fonte CPGF VIAGENS   # filtra fontes
    python3 pipeline.py --ano 2022 2023         # filtra anos
"""

import os
import sys
import argparse
import time
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

load_dotenv(PROJECT_ROOT / "dev.env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "contingency.settings")

import duckdb
import pandas as pd
from mathCore.benfordLaw import detectar_fraude, imprimir_relatorio

# ════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ════════════════════════════════════════════════════════════════

DB_PATH    = str(PROJECT_ROOT / "pipeline.duckdb")
OUTPUT_CSV = "resultado_fraude_consolidado.csv"

COLUNA_VALOR      = "valor"
COLUNA_ORGAO      = "orgao"
COLUNA_ANO        = "ano"
COLUNA_FUNCAO     = "funcao"
COLUNA_FONTE      = "fonte"
COLUNAS_CLUSTER   = [COLUNA_ORGAO, COLUNA_ANO, COLUNA_FUNCAO]

# CEIS não tem valor monetário real — excluída do Benford
FONTES_SENTINEL = {"CEIS"}

# ════════════════════════════════════════════════════════════════
# ARGS
# ════════════════════════════════════════════════════════════════

parser = argparse.ArgumentParser(description="Pipeline Benford sobre DuckDB local")
parser.add_argument("--fonte", nargs="+", metavar="FONTE",
                    help="Filtrar por fonte (ex: CPGF VIAGENS)")
parser.add_argument("--ano", nargs="+", type=int, metavar="ANO",
                    help="Filtrar por ano (ex: 2022 2023)")
args = parser.parse_args()

# ════════════════════════════════════════════════════════════════
# CARGA DO DB LOCAL
# ════════════════════════════════════════════════════════════════

if not os.path.exists(DB_PATH):
    print(f"❌ DB não encontrado: {DB_PATH}")
    print("   Execute primeiro: python3 ingest.py")
    sys.exit(1)

db = duckdb.connect(DB_PATH, read_only=True)

# verificar fontes disponíveis
fontes_db = [r[0] for r in db.execute("SELECT DISTINCT fonte FROM dados ORDER BY fonte").fetchall()]
if not fontes_db:
    print("❌ DB vazio. Execute: python3 ingest.py")
    sys.exit(1)

print("\n" + "═"*60)
print("  LENDO DO DUCKDB LOCAL")
print("═"*60)
print(f"  DB: {DB_PATH}")

# montar filtros
where_clauses = []
params = []

if args.fonte:
    fontes_upper = [f.upper() for f in args.fonte]
    placeholders = ", ".join(["?"] * len(fontes_upper))
    where_clauses.append(f"fonte IN ({placeholders})")
    params.extend(fontes_upper)

if args.ano:
    placeholders = ", ".join(["?"] * len(args.ano))
    where_clauses.append(f"ano IN ({placeholders})")
    params.extend(args.ano)

where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

value_filter = "AND valor IS NOT NULL AND valor > 0" if where_sql else "WHERE valor IS NOT NULL AND valor > 0"

query = f"""
    SELECT valor, orgao, ano, funcao, fonte, favorecido, cpf_cnpj
    FROM dados
    {where_sql}
    {value_filter}
"""

t0 = time.time()
df = db.execute(query, params).df()
db.close()
elapsed = time.time() - t0

print(f"  Leitura: {len(df):,} registros em {elapsed:.2f}s")
print(f"\n  Por fonte:")
for fonte, grp in df.groupby(COLUNA_FONTE):
    sentinal = " (excluída do Benford)" if fonte in FONTES_SENTINEL else ""
    print(f"    {fonte:28s} {len(grp):>10,} registros{sentinal}")

if df.empty:
    print("\n❌ Nenhum dado carregado. Verifique os filtros.")
    sys.exit(1)

# ════════════════════════════════════════════════════════════════
# PIPELINE DE DETECÇÃO DE FRAUDE
# ════════════════════════════════════════════════════════════════

df_benford = df[~df[COLUNA_FONTE].isin(FONTES_SENTINEL)].copy()

print(f"\n  Registros para Benford: {len(df_benford):,}")
print(f"  Período               : {df_benford[COLUNA_ANO].min()} → {df_benford[COLUNA_ANO].max()}")

vals = df_benford[COLUNA_VALOR].dropna()
if len(vals):
    print(f"  Valor mín/máx         : R$ {vals.min():.2f} / R$ {vals.max():,.2f}")

print("\n🔍 Iniciando pipeline de detecção de fraude...")

df_result, metricas = detectar_fraude(
    df_benford,
    coluna_valor=COLUNA_VALOR,
    colunas_cluster=[c for c in COLUNAS_CLUSTER if c in df_benford.columns],
)

imprimir_relatorio(df_result, metricas)

# ════════════════════════════════════════════════════════════════
# EXPORTAÇÃO
# ════════════════════════════════════════════════════════════════

df_result.to_csv(OUTPUT_CSV, index=False)
print(f"✅ Exportado: {OUTPUT_CSV}  ({len(df_result):,} registros)")