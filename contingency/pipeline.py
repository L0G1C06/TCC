import os
from dotenv import load_dotenv

load_dotenv("dev.env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "contingency.settings")

# ── projeto ─────────────────────────────────────────────────────
from apps.portal_da_transparencia.models.cpgf import CPGF
import polars as pl
import pandas as pd

# ── pipeline genérico de detecção de fraude ─────────────────────
from mathCore.benfordLaw import detectar_fraude, imprimir_relatorio

# ════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ════════════════════════════════════════════════════════════════

ANOS  = [str(a) for a in range(2019, 2025)]   # 2019 → 2024
MESES = [f"{m:02d}" for m in range(1, 13)]    # 01 → 12

COLUNA_VALOR    = "VALOR TRANSAÇÃO"
COLUNA_ORGAO    = "NOME ÓRGÃO SUPERIOR"
COLUNA_ANO      = "ANO EXTRATO"
COLUNA_FUNCAO   = "NOME ÓRGÃO"
COLUNAS_CLUSTER = [COLUNA_ORGAO, COLUNA_ANO, COLUNA_FUNCAO]

OUTPUT_CSV = "resultado_fraude_cpgf_completo.csv"

# ════════════════════════════════════════════════════════════════
# CARGA DE TODA A BASE
# ════════════════════════════════════════════════════════════════

def normalizar_valor(series: pd.Series) -> pd.Series:
    """Converte formato BR '1.290,00' → float 1290.0"""
    return (
        series
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace(r"[^\d.]", "", regex=True)
        .pipe(pd.to_numeric, errors="coerce")
    )

def carregar_particao(ano: str, mes: str) -> pd.DataFrame | None:
    """Tenta carregar uma partição; retorna None se não existir."""
    try:
        df_pl = CPGF.polars(ano=ano, mes=mes).collect()
        if df_pl.is_empty():
            return None
        df = df_pl.to_pandas()
        df[COLUNA_VALOR] = normalizar_valor(df[COLUNA_VALOR])
        return df
    except Exception as e:
        print(f"   ⚠️  {ano}/{mes} — ignorado ({type(e).__name__}: {e})")
        return None

print("═" * 60)
print("  CARREGANDO BASE COMPLETA DO CPGF")
print("═" * 60)

partições = []
total_particoes = 0

for ano in ANOS:
    for mes in MESES:
        print(f"  📥 {ano}/{mes}", end=" ... ", flush=True)
        df_part = carregar_particao(ano, mes)
        if df_part is not None:
            partições.append(df_part)
            total_particoes += 1
            print(f"{len(df_part):,} registros")
        else:
            print("vazio / inexistente")

if not partições:
    raise RuntimeError("Nenhuma partição carregada. Verifique a conexão com o S3.")

print(f"\n✅ {total_particoes} partições carregadas — concatenando...")
df = pd.concat(partições, ignore_index=True)
print(f"   Total consolidado: {len(df):,} registros")
print(f"   Período: {df[COLUNA_ANO].min()} → {df[COLUNA_ANO].max()}")
print(f"   Valor mín/máx: R$ {df[COLUNA_VALOR].min():.2f} / R$ {df[COLUNA_VALOR].max():,.2f}")

# ════════════════════════════════════════════════════════════════
# PIPELINE DE DETECÇÃO DE FRAUDE
# ════════════════════════════════════════════════════════════════

print("\n🔍 Iniciando pipeline de detecção de fraude...")

df_result, metricas = detectar_fraude(
    df,
    coluna_valor=COLUNA_VALOR,
    colunas_cluster=[c for c in COLUNAS_CLUSTER if c in df.columns],
)

imprimir_relatorio(df_result, metricas)

# ════════════════════════════════════════════════════════════════
# EXPORTAÇÃO
# ════════════════════════════════════════════════════════════════

df_result.to_csv(OUTPUT_CSV, index=False)
print(f"✅ Exportado: {OUTPUT_CSV}  ({len(df_result):,} registros)")