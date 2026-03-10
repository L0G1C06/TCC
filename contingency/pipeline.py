import os
from dotenv import load_dotenv

load_dotenv("dev.env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "contingency.settings")

from apps.portal_da_transparencia.models.cpgf import CPGF
from apps.portal_da_transparencia.models.ceis import CEIS
import polars as pl
import pandas as pd
import duckdb

from mathCore.benfordLaw import detectar_fraude, imprimir_relatorio

# ════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ════════════════════════════════════════════════════════════════

S3_BUCKET = os.getenv("DATALAKE_BUCKET", "storage-rumolog")
S3_BASE   = f"s3://{S3_BUCKET}/data/portal_da_transparencia/parquet"
S3_BNDES  = f"s3://{S3_BUCKET}/data/bndes/parquet"

ANOS_CPGF = [str(a) for a in range(2019, 2025)]
MESES     = [f"{m:02d}" for m in range(1, 13)]

ANOS_LICITACOES = [str(a) for a in range(2013, 2025)]
ANOS_COMPRAS    = [str(a) for a in range(2013, 2025)]
ANOS_VIAGENS    = [str(a) for a in range(2011, 2025)]
CEIS_ANO, CEIS_MES = "2026", "03"

BNDES_FIN_FILES = [
    f"{S3_BNDES}/modulo=operacoes-de-financiamento/operacoes-financiamento-operacoes-indiretas-automaticas.parquet",
    f"{S3_BNDES}/modulo=operacoes-de-financiamento/operacoes-financiamento-operacoes-nao-automaticas.parquet",
]
BNDES_EXP_PREFIXES = [
    "operacoes-de-exportacao-pre-e-pos-embarque",
    "operacoes-de-exportacaoo-pre-e-pos-embarque",
    "operacoes-de-exportacao",
]

COLUNA_VALOR      = "valor"
COLUNA_ORGAO      = "orgao"
COLUNA_ANO        = "ano"
COLUNA_FUNCAO     = "funcao"
COLUNA_FONTE      = "fonte"
COLUNA_FAVORECIDO = "favorecido"
COLUNA_CPF_CNPJ   = "cpf_cnpj"
COLUNAS_CLUSTER   = [COLUNA_ORGAO, COLUNA_ANO, COLUNA_FUNCAO]
OUTPUT_CSV        = "resultado_fraude_consolidado.csv"

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

def get_conn():
    conn = duckdb.connect()
    conn.execute(f"""
        INSTALL httpfs; LOAD httpfs;
        SET s3_region='{os.getenv("AWS_DEFAULT_REGION", "sa-east-1")}';
        SET s3_access_key_id='{os.getenv("AWS_ACCESS_KEY_ID", "")}';
        SET s3_secret_access_key='{os.getenv("AWS_SECRET_ACCESS_KEY", "")}';
    """)
    return conn

def col(df, *candidates, default=None):
    """Retorna a primeira coluna que existir no DataFrame."""
    for c in candidates:
        if c in df.columns:
            return df[c]
    return pd.Series(default, index=df.index)

def unificar(df, valor, orgao, ano, funcao, favorecido, cnpj, fonte):
    return pd.DataFrame({
        COLUNA_VALOR:      valor,
        COLUNA_ORGAO:      orgao,
        COLUNA_ANO:        ano,
        COLUNA_FUNCAO:     funcao,
        COLUNA_FAVORECIDO: favorecido,
        COLUNA_CPF_CNPJ:   cnpj,
        COLUNA_FONTE:      fonte,
    })

def duckdb_glob(conn, glob, label=""):
    """Lê glob com union_by_name. Retorna DataFrame vazio em caso de erro."""
    try:
        df = conn.execute(
            f"SELECT * FROM read_parquet('{glob}', union_by_name=true)"
        ).df()
        return df
    except Exception as e:
        print(f"     ⚠️  {label}: {type(e).__name__}")
        return pd.DataFrame()

# ════════════════════════════════════════════════════════════════
# CARGA — CPGF  (usa model ORM — já funciona)
# ════════════════════════════════════════════════════════════════

def carregar_cpgf():
    print(f"\n{'═'*60}\n  CPGF\n{'═'*60}")
    partes = []
    for ano in ANOS_CPGF:
        for mes in MESES:
            print(f"  📥 {ano}/{mes}", end=" ... ", flush=True)
            try:
                df_pl = CPGF.polars(ano=ano, mes=mes).collect()
                if df_pl.is_empty():
                    print("vazio"); continue
                df = df_pl.to_pandas()
                out = unificar(df,
                    valor      = normalizar_br(df["VALOR TRANSAÇÃO"]),
                    orgao      = col(df, "NOME ÓRGÃO SUPERIOR"),
                    ano        = pd.to_numeric(df["ANO EXTRATO"], errors="coerce").astype("Int64"),
                    funcao     = col(df, "NOME ÓRGÃO"),
                    favorecido = col(df, "NOME FAVORECIDO"),
                    cnpj       = col(df, "CNPJ OU CPF FAVORECIDO"),
                    fonte      = "CPGF",
                )
                partes.append(out)
                print(f"{len(out):,} registros")
            except Exception as e:
                print(f"ignorado ({type(e).__name__}: {e})")
    if not partes:
        return pd.DataFrame()
    result = pd.concat(partes, ignore_index=True)
    print(f"\n  ✅ CPGF: {len(result):,} registros")
    return result

# ════════════════════════════════════════════════════════════════
# CARGA — CEIS  (usa model ORM — snapshot único)
# ════════════════════════════════════════════════════════════════

def carregar_ceis():
    print(f"\n{'═'*60}\n  CEIS\n{'═'*60}")
    print(f"  📥 Snapshot {CEIS_ANO}/{CEIS_MES}", end=" ... ", flush=True)
    try:
        df = CEIS.polars(ano=CEIS_ANO, mes=CEIS_MES).collect().to_pandas()
        print(f"{len(df):,} registros")
        out = unificar(df,
            valor      = pd.Series(1.0, index=df.index),   # sentinel — sem valor monetário
            orgao      = col(df, "ÓRGÃO SANCIONADOR"),
            ano        = extrair_ano(col(df, "DATA INÍCIO SANÇÃO").astype(str)),
            funcao     = col(df, "CATEGORIA DA SANÇÃO"),
            favorecido = col(df, "NOME DO SANCIONADO"),
            cnpj       = col(df, "CPF OU CNPJ DO SANCIONADO"),
            fonte      = "CEIS",
        )
        print(f"  ✅ CEIS: {len(out):,} registros")
        return out
    except Exception as e:
        print(f"ignorado ({type(e).__name__}: {e})")
        return pd.DataFrame()

# ════════════════════════════════════════════════════════════════
# CARGA — LICITAÇÕES
# Cada pasta ano/mes contém múltiplos arquivos com schemas distintos.
# Carregamos arquivo por arquivo e acumulamos só os que têm colunas úteis.
# ════════════════════════════════════════════════════════════════

def _listar_parquets(conn, prefix) -> list[str]:
    """Lista todos os .parquet sob um prefix S3."""
    try:
        rows = conn.execute(
            f"SELECT file FROM glob('{prefix}/**/*.parquet')"
        ).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []

def _ler_arquivo(conn, path) -> pd.DataFrame:
    try:
        return conn.execute(f"SELECT * FROM read_parquet('{path}')").df()
    except Exception:
        return pd.DataFrame()

def carregar_licitacoes():
    print(f"\n{'═'*60}\n  LICITAÇÕES\n{'═'*60}")
    conn = get_conn()
    partes = []
    for ano in ANOS_LICITACOES:
        for mes in MESES:
            prefix = f"{S3_BASE}/modulo=licitacoes/ano={ano}/mes={mes}"
            arquivos = _listar_parquets(conn, prefix)
            if not arquivos:
                continue
            print(f"  📥 {ano}/{mes} ({len(arquivos)} arquivos)", end=" ... ", flush=True)
            sub = []
            for arq in arquivos:
                df = _ler_arquivo(conn, arq)
                if df.empty:
                    continue
                # só arquivos com coluna de participante (tabela de licitantes)
                if not any(c in df.columns for c in ["Código Participante", "Nome Participante"]):
                    continue
                # filtrar vencedores se disponível
                if "Flag Vencedor" in df.columns:
                    df = df[df["Flag Vencedor"].astype(str).str.upper().isin(["S", "SIM", "1", "TRUE"])]
                if df.empty:
                    continue
                val_series = None
                for vc in ["Valor Licitação", "Valor Empenho (R$)"]:
                    if vc in df.columns:
                        val_series = normalizar_br(df[vc])
                        break
                if val_series is None:
                    val_series = pd.Series(1.0, index=df.index)
                sub.append(unificar(df,
                    valor      = val_series,
                    orgao      = col(df, "Nome Órgão", "Nome Órgão Superior"),
                    ano        = pd.Series([int(ano)] * len(df), dtype="Int64"),
                    funcao     = col(df, "Modalidade Compra"),
                    favorecido = col(df, "Nome Participante"),
                    cnpj       = col(df, "Código Participante"),
                    fonte      = "LICITACOES",
                ))
            if sub:
                parte = pd.concat(sub, ignore_index=True)
                partes.append(parte)
                print(f"{len(parte):,} registros")
            else:
                print("sem tabela de participantes")

    conn.close()
    if not partes:
        print("  ⚠️  Nenhuma partição carregada.")
        return pd.DataFrame()
    result = pd.concat(partes, ignore_index=True)
    print(f"\n  ✅ Licitações: {len(result):,} registros")
    return result

# ════════════════════════════════════════════════════════════════
# CARGA — VIAGENS
# Cada ano tem: {ano}_Pagamento.parquet + _Viagem + _Trecho + _Passagem
# Só o arquivo _Pagamento tem Valor + CPF viajante — os demais têm schema diferente.
# ════════════════════════════════════════════════════════════════

def carregar_viagens():
    print(f"\n{'═'*60}\n  VIAGENS\n{'═'*60}")
    conn = get_conn()
    partes = []
    for ano in ANOS_VIAGENS:
        path = f"{S3_BASE}/modulo=viagens/ano={ano}/{ano}_Pagamento.parquet"
        print(f"  📥 {ano}", end=" ... ", flush=True)
        df = _ler_arquivo(conn, path)
        if df.empty:
            print("não encontrado"); continue

        val_series = None
        for vc in ["Valor", "Valor diárias", "Valor passagens"]:
            if vc in df.columns:
                val_series = normalizar_br(df[vc])
                break
        if val_series is None:
            print("sem coluna de valor"); continue

        out = unificar(df,
            valor      = val_series,
            orgao      = col(df, "Nome do órgão superior", "Nome do órgao pagador"),
            ano        = pd.Series([int(ano)] * len(df), dtype="Int64"),
            funcao     = col(df, "Tipo de pagamento"),
            favorecido = col(df, "Nome"),
            cnpj       = col(df, "CPF viajante"),
            fonte      = "VIAGENS",
        )
        partes.append(out)
        print(f"{len(out):,} registros")

    conn.close()
    if not partes:
        print("  ⚠️  Nenhuma partição carregada.")
        return pd.DataFrame()
    result = pd.concat(partes, ignore_index=True)
    print(f"\n  ✅ Viagens: {len(result):,} registros")
    return result

# ════════════════════════════════════════════════════════════════
# CARGA — COMPRAS
# Cada pasta ano/mes mistura: itens de compra, apostilamentos, contratos.
# Cada arquivo tem schema diferente — lemos um por um e filtramos pelo conteúdo.
# ════════════════════════════════════════════════════════════════

# Colunas de valor por tipo de arquivo de compras
_COMPRAS_VALOR_COLS = [
    "Valor Item",           # itens
    "Valor Inicial Compra", # contratos
    "Valor Final Compra",   # contratos
    "Valor Apostilamento",  # apostilamentos
    "Valor Licitação",      # licitações dentro de compras
]

def carregar_compras():
    print(f"\n{'═'*60}\n  COMPRAS\n{'═'*60}")
    conn = get_conn()
    partes = []
    for ano in ANOS_COMPRAS:
        for mes in MESES:
            prefix = f"{S3_BASE}/modulo=compras/ano={ano}/mes={mes}"
            arquivos = _listar_parquets(conn, prefix)
            if not arquivos:
                continue
            print(f"  📥 {ano}/{mes} ({len(arquivos)} arquivos)", end=" ... ", flush=True)
            sub = []
            for arq in arquivos:
                df = _ler_arquivo(conn, arq)
                if df.empty:
                    continue
                val_series = None
                for vc in _COMPRAS_VALOR_COLS:
                    if vc in df.columns:
                        val_series = normalizar_br(df[vc])
                        break
                if val_series is None:
                    continue   # arquivo sem valor (ex: só metadados)
                sub.append(unificar(df,
                    valor      = val_series,
                    orgao      = col(df, "Nome Órgão", "Nome Órgão Superior"),
                    ano        = pd.Series([int(ano)] * len(df), dtype="Int64"),
                    funcao     = col(df, "Descrição Item Compra", "Modalidade Compra Licitação",
                                       "Modalidade Compra", "Objeto"),
                    favorecido = col(df, "Nome Contratado"),
                    cnpj       = col(df, "Código Contratado", "Código UG"),
                    fonte      = "COMPRAS",
                ))
            if sub:
                parte = pd.concat(sub, ignore_index=True)
                partes.append(parte)
                print(f"{len(parte):,} registros")
            else:
                print("sem arquivo com valor")

    conn.close()
    if not partes:
        print("  ⚠️  Nenhuma partição carregada.")
        return pd.DataFrame()
    result = pd.concat(partes, ignore_index=True)
    print(f"\n  ✅ Compras: {len(result):,} registros")
    return result

# ════════════════════════════════════════════════════════════════
# CARGA — BNDES Financiamento
# ════════════════════════════════════════════════════════════════

def carregar_bndes_financiamento():
    print(f"\n{'═'*60}\n  BNDES — FINANCIAMENTO\n{'═'*60}")
    print("  📥 Carregando...", end=" ", flush=True)
    try:
        files = "', '".join(BNDES_FIN_FILES)
        conn = get_conn()
        df = conn.execute(
            f"SELECT * FROM read_parquet(['{files}'], union_by_name=true)"
        ).df()
        conn.close()
        print(f"{len(df):,} registros")

        val = None
        for vc in ["valor_desembolsado_reais", "valor_contratado_reais", "valor_da_operacao_em_reais"]:
            if vc in df.columns:
                candidate = normalizar_br(df[vc])
                if candidate.notna().sum() > 0:
                    val = candidate
                    print(f"  ℹ️  Valor: {vc}")
                    break
        if val is None:
            raise ValueError("Nenhuma coluna de valor encontrada")

        cnpj = col(df, "cpf_cnpj", "cnpj")
        out = unificar(df,
            valor      = val,
            orgao      = col(df, "setor_bndes"),
            ano        = extrair_ano(df["data_da_contratacao"].astype(str)),
            funcao     = col(df, "subsetor_bndes"),
            favorecido = col(df, "cliente"),
            cnpj       = cnpj,
            fonte      = "BNDES_FINANCIAMENTO",
        )
        print(f"  ✅ BNDES Financiamento: {len(out):,} registros")
        return out
    except Exception as e:
        print(f"\n  ⚠️  Ignorado ({type(e).__name__}: {e})")
        return pd.DataFrame()

# ════════════════════════════════════════════════════════════════
# CARGA — BNDES Exportação
# ════════════════════════════════════════════════════════════════

def carregar_bndes_exportacao():
    print(f"\n{'═'*60}\n  BNDES — EXPORTAÇÃO\n{'═'*60}")
    conn = get_conn()
    df = pd.DataFrame()
    for prefix in BNDES_EXP_PREFIXES:
        glob = f"{S3_BNDES}/modulo={prefix}/**/*.parquet"
        print(f"  🔍 {prefix}")
        df = duckdb_glob(conn, glob, label=prefix)
        if not df.empty:
            print(f"  ✅ Encontrado: {len(df):,} registros"); break
    conn.close()

    if df.empty:
        print("  ⚠️  Não encontrado — pulando.")
        return pd.DataFrame()

    val = None
    for vc in ["valor_desembolsado_em_reais", "valor_da_operacao_em_reais", "valor_desembolsado_em_um"]:
        if vc in df.columns:
            candidate = normalizar_br(df[vc])
            if candidate.notna().sum() > 0:
                val = candidate
                print(f"  ℹ️  Valor: {vc}"); break
    if val is None:
        print("  ⚠️  Sem coluna de valor — ignorado.")
        return pd.DataFrame()

    out = unificar(df,
        valor      = val,
        orgao      = col(df, "setor_bndes"),
        ano        = extrair_ano(df["data_da_contratacao"].astype(str)),
        funcao     = col(df, "subsetor_bndes"),
        favorecido = col(df, "exportador", "cliente"),
        cnpj       = col(df, "cnpj_do_exportador", "cpf_cnpj"),
        fonte      = "BNDES_EXPORTACAO",
    )
    print(f"  ✅ BNDES Exportação: {len(out):,} registros")
    return out

# ════════════════════════════════════════════════════════════════
# CONSOLIDAÇÃO
# ════════════════════════════════════════════════════════════════

cargas = [
    carregar_cpgf(),
    carregar_ceis(),
    carregar_licitacoes(),
    carregar_viagens(),
    carregar_compras(),
    carregar_bndes_financiamento(),
    carregar_bndes_exportacao(),
]

fontes = [d for d in cargas if not d.empty]
if not fontes:
    raise RuntimeError("Nenhuma fonte carregada.")

df = pd.concat(fontes, ignore_index=True)

print("\n" + "═"*60)
print("  RESUMO DA BASE CONSOLIDADA")
print("═"*60)
print(f"  Total              : {len(df):,} registros")
print(f"  Período            : {df[COLUNA_ANO].min()} → {df[COLUNA_ANO].max()}")
vals = df[COLUNA_VALOR].dropna()
vals = vals[vals > 1.0]   # excluir sentinels
if len(vals):
    print(f"  Valor mín/máx      : R$ {vals.min():.2f} / R$ {vals.max():,.2f}")
print(f"\n  Por fonte:")
for fonte, grp in df.groupby(COLUNA_FONTE):
    print(f"    {fonte:30s} {len(grp):>10,} registros")

# ════════════════════════════════════════════════════════════════
# PIPELINE  (excluir sentinels do Benford)
# ════════════════════════════════════════════════════════════════

FONTES_SENTINEL = {"CEIS"}   # licitações agora têm valor real quando disponível
df_benford = df[~df[COLUNA_FONTE].isin(FONTES_SENTINEL)].copy()
print(f"\n  Para Benford: {len(df_benford):,} registros")

print("\n🔍 Iniciando pipeline de detecção de fraude...")

df_result, metricas = detectar_fraude(
    df_benford,
    coluna_valor=COLUNA_VALOR,
    colunas_cluster=[c for c in COLUNAS_CLUSTER if c in df_benford.columns],
)

imprimir_relatorio(df_result, metricas)

df_result.to_csv(OUTPUT_CSV, index=False)
print(f"✅ Exportado: {OUTPUT_CSV}  ({len(df_result):,} registros)")