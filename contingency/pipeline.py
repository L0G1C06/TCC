import os
from dotenv import load_dotenv

load_dotenv("dev.env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "contingency.settings")

# ── projeto ─────────────────────────────────────────────────────
from apps.portal_da_transparencia.models.cpgf import CPGF
import polars as pl
import pandas as pd
import duckdb

# ── pipeline de detecção de fraude ──────────────────────────────
from mathCore.benfordLaw import detectar_fraude, imprimir_relatorio

# ════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO — CPGF
# ════════════════════════════════════════════════════════════════

ANOS_CPGF  = [str(a) for a in range(2019, 2025)]
MESES_CPGF = [f"{m:02d}" for m in range(1, 13)]

CPGF_VALOR      = "VALOR TRANSAÇÃO"
CPGF_ORGAO      = "NOME ÓRGÃO SUPERIOR"
CPGF_ANO        = "ANO EXTRATO"
CPGF_FUNCAO     = "NOME ÓRGÃO"
CPGF_FAVORECIDO = "NOME FAVORECIDO"
CPGF_CPF_CNPJ   = "CNPJ OU CPF FAVORECIDO"

# ════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO — BNDES (paths S3 diretos)
# ════════════════════════════════════════════════════════════════

S3_BUCKET = os.getenv("DATALAKE_BUCKET", "storage-rumolog")
S3_PREFIX = f"s3://{S3_BUCKET}/data"

BNDES_FIN_FILES = [
    f"{S3_PREFIX}/bndes/parquet/modulo=operacoes-de-financiamento/operacoes-financiamento-operacoes-indiretas-automaticas.parquet",
    f"{S3_PREFIX}/bndes/parquet/modulo=operacoes-de-financiamento/operacoes-financiamento-operacoes-nao-automaticas.parquet",
]

# Exportação: listar variações do typo para achar o path correto
BNDES_EXP_PREFIXES = [
    "operacoes-de-exportacao-pre-e-pos-embarque",   # sem typo
    "operacoes-de-exportacaoo-pre-e-pos-embarque",  # typo duplo-o (original)
    "operacoes-de-exportacao",                       # path curto
]

# ════════════════════════════════════════════════════════════════
# SCHEMA UNIFICADO
# ════════════════════════════════════════════════════════════════

COLUNA_VALOR      = "valor"
COLUNA_ORGAO      = "orgao"
COLUNA_ANO        = "ano"
COLUNA_FUNCAO     = "funcao"
COLUNA_FONTE      = "fonte"
COLUNA_FAVORECIDO = "favorecido"
COLUNA_CPF_CNPJ   = "cpf_cnpj"

COLUNAS_CLUSTER = [COLUNA_ORGAO, COLUNA_ANO, COLUNA_FUNCAO]
OUTPUT_CSV = "resultado_fraude_consolidado.csv"

# ════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════

def normalizar_br(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    return (
        series.astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace(r"[^\d.]", "", regex=True)
        .pipe(pd.to_numeric, errors="coerce")
    )

def extrair_ano(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, dayfirst=True, errors="coerce")
    mask = parsed.isna()
    if mask.any():
        parsed[mask] = pd.to_datetime(series[mask], format="%Y-%m-%d", errors="coerce")
    return parsed.dt.year.astype("Int64")

def get_duckdb_conn():
    """Cria conexão DuckDB com credenciais S3."""
    conn = duckdb.connect()
    conn.execute(f"""
        INSTALL httpfs; LOAD httpfs;
        SET s3_region='{os.getenv("AWS_DEFAULT_REGION", "sa-east-1")}';
        SET s3_access_key_id='{os.getenv("AWS_ACCESS_KEY_ID", "")}';
        SET s3_secret_access_key='{os.getenv("AWS_SECRET_ACCESS_KEY", "")}';
    """)
    return conn

# ════════════════════════════════════════════════════════════════
# CARGA — CPGF
# ════════════════════════════════════════════════════════════════

def carregar_cpgf() -> pd.DataFrame:
    print("\n" + "═" * 60)
    print("  PORTAL DA TRANSPARÊNCIA — CPGF")
    print("═" * 60)
    partes = []
    for ano in ANOS_CPGF:
        for mes in MESES_CPGF:
            print(f"  📥 CPGF {ano}/{mes}", end=" ... ", flush=True)
            try:
                df_pl = CPGF.polars(ano=ano, mes=mes).collect()
                if df_pl.is_empty():
                    print("vazio"); continue
                df = df_pl.to_pandas()
                out = pd.DataFrame({
                    COLUNA_VALOR:      normalizar_br(df[CPGF_VALOR]),
                    COLUNA_ORGAO:      df[CPGF_ORGAO],
                    COLUNA_ANO:        pd.to_numeric(df[CPGF_ANO], errors="coerce").astype("Int64"),
                    COLUNA_FUNCAO:     df[CPGF_FUNCAO],
                    COLUNA_FAVORECIDO: df.get(CPGF_FAVORECIDO, pd.NA),
                    COLUNA_CPF_CNPJ:   df.get(CPGF_CPF_CNPJ, pd.NA),
                    COLUNA_FONTE:      "CPGF",
                })
                partes.append(out)
                print(f"{len(out):,} registros")
            except Exception as e:
                print(f"ignorado ({type(e).__name__}: {e})")
    if not partes:
        print("  ⚠️  Nenhuma partição CPGF carregada.")
        return pd.DataFrame()
    df_cpgf = pd.concat(partes, ignore_index=True)
    print(f"\n  ✅ CPGF consolidado: {len(df_cpgf):,} registros")
    return df_cpgf

# ════════════════════════════════════════════════════════════════
# CARGA — BNDES Financiamento (union_by_name via DuckDB direto)
# ════════════════════════════════════════════════════════════════

def carregar_bndes_financiamento() -> pd.DataFrame:
    print("\n" + "═" * 60)
    print("  BNDES — OPERAÇÕES DE FINANCIAMENTO")
    print("═" * 60)
    print("  📥 Carregando com union_by_name...", end=" ", flush=True)
    try:
        files = "', '".join(BNDES_FIN_FILES)
        conn = get_duckdb_conn()
        df = conn.execute(f"""
            SELECT * FROM read_parquet(['{files}'], union_by_name=true)
        """).df()
        conn.close()
        print(f"{len(df):,} registros")

        # normalizar valor: preferir valor_desembolsado_reais (VARCHAR),
        # fallback para valor_contratado_reais, fallback para valor_da_operacao_em_reais
        val = None
        for col in ["valor_desembolsado_reais", "valor_contratado_reais", "valor_da_operacao_em_reais"]:
            if col in df.columns:
                candidate = normalizar_br(df[col])
                if candidate.notna().sum() > 0:
                    val = candidate
                    print(f"  ℹ️  Usando coluna de valor: {col}")
                    break
        if val is None:
            raise ValueError("Nenhuma coluna de valor encontrada no BNDES Financiamento")

        # cnpj: cpf_cnpj existe só nas indiretas-automaticas, cnpj só nas nao-automaticas
        cnpj_col = df.get("cpf_cnpj", df.get("cnpj", pd.Series(pd.NA, index=df.index)))

        out = pd.DataFrame({
            COLUNA_VALOR:      val,
            COLUNA_ORGAO:      df.get("setor_bndes", pd.NA),
            COLUNA_ANO:        extrair_ano(df["data_da_contratacao"]),
            COLUNA_FUNCAO:     df.get("subsetor_bndes", pd.NA),
            COLUNA_FAVORECIDO: df.get("cliente", pd.NA),
            COLUNA_CPF_CNPJ:   cnpj_col if isinstance(cnpj_col, pd.Series) else pd.NA,
            COLUNA_FONTE:      "BNDES_FINANCIAMENTO",
        })
        print(f"  ✅ BNDES Financiamento: {len(out):,} registros")
        return out
    except Exception as e:
        print(f"\n  ⚠️  Ignorado ({type(e).__name__}: {e})")
        return pd.DataFrame()

# ════════════════════════════════════════════════════════════════
# CARGA — BNDES Exportação (tenta variações do path)
# ════════════════════════════════════════════════════════════════

def carregar_bndes_exportacao() -> pd.DataFrame:
    print("\n" + "═" * 60)
    print("  BNDES — OPERAÇÕES DE EXPORTAÇÃO")
    print("═" * 60)

    conn = get_duckdb_conn()
    df = None

    for prefix in BNDES_EXP_PREFIXES:
        glob = f"{S3_PREFIX}/bndes/parquet/modulo={prefix}/**/*.parquet"
        print(f"  🔍 Tentando: modulo={prefix}")
        try:
            df = conn.execute(f"""
                SELECT * FROM read_parquet('{glob}', union_by_name=true)
            """).df()
            if len(df) > 0:
                print(f"  ✅ Encontrado com prefixo '{prefix}': {len(df):,} registros")
                break
        except Exception as e:
            print(f"     ⚠️  {type(e).__name__}: {e}")

    conn.close()

    if df is None or len(df) == 0:
        print("  ⚠️  Exportação BNDES não encontrada — pulando.")
        return pd.DataFrame()

    # valor: pós-embarque tem valor_desembolsado_em_reais; pré tem valor_da_operacao_em_reais
    val = None
    for col in ["valor_desembolsado_em_reais", "valor_da_operacao_em_reais", "valor_desembolsado_em_um"]:
        if col in df.columns:
            candidate = normalizar_br(df[col])
            if candidate.notna().sum() > 0:
                val = candidate
                print(f"  ℹ️  Usando coluna de valor: {col}")
                break
    if val is None:
        print("  ⚠️  Nenhuma coluna de valor válida — exportação ignorada.")
        return pd.DataFrame()

    out = pd.DataFrame({
        COLUNA_VALOR:      val,
        COLUNA_ORGAO:      df.get("setor_bndes", pd.NA),
        COLUNA_ANO:        extrair_ano(df["data_da_contratacao"]),
        COLUNA_FUNCAO:     df.get("subsetor_bndes", pd.NA),
        COLUNA_FAVORECIDO: df.get("exportador", df.get("cliente", pd.NA)),
        COLUNA_CPF_CNPJ:   df.get("cnpj_do_exportador", df.get("cpf_cnpj", pd.NA)),
        COLUNA_FONTE:      "BNDES_EXPORTACAO",
    })
    print(f"  ✅ BNDES Exportação: {len(out):,} registros")
    return out

# ════════════════════════════════════════════════════════════════
# CONSOLIDAÇÃO
# ════════════════════════════════════════════════════════════════

df_cpgf    = carregar_cpgf()
df_bndes_f = carregar_bndes_financiamento()
df_bndes_e = carregar_bndes_exportacao()

fontes = [df for df in [df_cpgf, df_bndes_f, df_bndes_e] if not df.empty]
if not fontes:
    raise RuntimeError("Nenhuma fonte carregada. Verifique a conexão com o S3.")

df = pd.concat(fontes, ignore_index=True)

print("\n" + "═" * 60)
print("  RESUMO DA BASE CONSOLIDADA")
print("═" * 60)
print(f"  Total de registros : {len(df):,}")
print(f"  Período            : {df[COLUNA_ANO].min()} → {df[COLUNA_ANO].max()}")
print(f"  Valor mín/máx      : R$ {df[COLUNA_VALOR].min():.2f} / R$ {df[COLUNA_VALOR].max():,.2f}")
print(f"\n  Por fonte:")
for fonte, grp in df.groupby(COLUNA_FONTE):
    print(f"    {fonte:30s} {len(grp):>8,} registros")

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