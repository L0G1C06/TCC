# apps/portal_da_transparencia/models/cpcc.py
"""
CPC-C — Cartão de Pagamento de Compras e Contratos

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=cpcc/
Histórico: 2014 → 2026 (múltiplos arquivos/mês)

Transações realizadas com cartões de pagamento institucionais de órgãos
e entidades da Administração Pública Federal.

Chaves de correlação:
    CNPJ OU CPF FAVORECIDO → cpgf.CNPJ OU CPF FAVORECIDO,
                             cpdc.CNPJ OU CPF FAVORECIDO
    CÓDIGO ÓRGÃO           → compras.Código Órgão,
                             cpgf.CÓDIGO ÓRGÃO
    CÓDIGO UG              → compras.Código UG,
                             cpgf.CÓDIGO UG
"""

from apps.datalake.orm.fields import (
    CodigoOrgaoSuperiorField,
    CodigoOrgaoField,
    CodigoUGField,
    CNPJField,
    CPFField,
    DateVarcharField,
    MoneyField,
    StringField,
    BigIntField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class CPCC(DuckDBModel):
    """
    Cartão de Pagamento de Compras e Contratos — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        CPCC.scan(ano="2022", mes="05").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "cpcc"

    # ── Órgão ─────────────────────────────────────────────────────────
    CODIGO_ORGAO_SUPERIOR = CodigoOrgaoSuperiorField(
        source_name = "CÓDIGO ÓRGÃO SUPERIOR",
        description = "Código órgão superior SIAFI. Chave entre módulos",
    )
    NOME_ORGAO_SUPERIOR = StringField(
        source_name = "NOME ÓRGÃO SUPERIOR",
        description = "Nome órgão superior",
    )
    CODIGO_ORGAO = CodigoOrgaoField(
        source_name = "CÓDIGO ÓRGÃO",
        description = "Código órgão SIAFI. Chave: compras, cpgf",
    )
    NOME_ORGAO = StringField(
        source_name = "NOME ÓRGÃO",
        description = "Nome órgão",
    )

    # ── UG ────────────────────────────────────────────────────────────
    CODIGO_UNIDADE_GESTORA = CodigoUGField(
        source_name = "CÓDIGO UNIDADE GESTORA",
        description = "Código UG SIAFI. Chave: compras, cpgf",
    )
    NOME_UNIDADE_GESTORA = StringField(
        source_name = "NOME UNIDADE GESTORA",
        description = "Nome UG",
    )

    # ── Extrato ───────────────────────────────────────────────────────
    ANO_EXTRATO = StringField(
        source_name = "ANO EXTRATO",
        description = "Ano do extrato — VARCHAR de 4 dígitos",
    )
    MES_EXTRATO = StringField(
        source_name = "MÊS EXTRATO",
        description = "Mês do extrato",
    )

    # ── Aquisição ─────────────────────────────────────────────────────
    TIPO_AQUISICAO = StringField(
        source_name = "TIPO AQUISIÇÃO",
        description = "Ex: Compra, Contrato",
    )

    # ── Favorecido ────────────────────────────────────────────────────
    CNPJ_OU_CPF_FAVORECIDO = CNPJField(
        source_name = "CNPJ OU CPF FAVORECIDO",
        description = "CNPJ ou CPF do favorecido. Chave: cpgf, cpdc",
    )
    NOME_FAVORECIDO = StringField(
        source_name = "NOME FAVORECIDO",
        description = "Nome do favorecido",
    )

    # ── Transação ─────────────────────────────────────────────────────
    TRANSACAO = StringField(
        source_name = "TRANSAÇÃO",
        description = "Número da transação",
    )
    DATA_TRANSAÇÃO = DateVarcharField(
        source_name = "DATA TRANSAÇÃO",
        description = "Silver: normalizar para Date",
    )
    VALOR_TRANSAÇÃO = MoneyField(
        source_name = "VALOR TRANSAÇÃO",
        description = "Valor da transação — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
