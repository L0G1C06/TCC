# apps/portal_da_transparencia/models/cpdc.py
"""
Cartão de Pagamento de Despesas (CPDC)

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=cpdc/
Histórico: 2013 → 2026 (múltiplos arquivos/mês)

Transações realizadas com cartões de pagamento institucionais de órgãos
e entidades da Administração Pública Federal, incluindo repasses a convênios.

Chaves de correlação:
    CPF PORTADOR         → cpgf.CPF PORTADOR, servidores, viagens
    CNPJ OU CPF FAVORECIDO → cpgf.CNPJ OU CPF FAVORECIDO, cpcc.CNPJ OU CPF FAVORECIDO
    CÓDIGO ÓRGÃO         → compras.Código Órgão, cpgf.CÓDIGO ÓRGÃO
    CÓDIGO UG            → compras.Código UG, cpgf.CÓDIGO UG
    NÚMERO CONVÊNIO      → convenios.NÚMERO CONVÊNIO
"""

from apps.datalake.orm.fields import (
    CodigoOrgaoSuperiorField,
    CodigoOrgaoField,
    CodigoUGField,
    CPFField,
    CNPJField,
    CPFCNPJField,
    DateVarcharField,
    MoneyField,
    StringField,
    BigIntField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class CPDC(DuckDBModel):
    """
    Cartão de Pagamento de Despesas — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        CPDC.scan(ano="2022", mes="05").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "cpdc"

    # ── Órgão ─────────────────────────────────────────────────────────
    CODIGO_ORGAO_SUPERIOR = CodigoOrgaoSuperiorField(
        source_name = "CÓDIGO ÓRGÃO SUPERIOR",
        description = "Código órgão superior SIAFI",
    )
    NOME_ORGAO_SUPERIOR = StringField(
        source_name = "NOME ÓRGÃO SUPERIOR",
        description = "Nome órgão superior",
    )
    CODIGO_ORGAO = CodigoOrgaoField(
        source_name = "CÓDIGO ÓRGÃO",
        description = "Código órgão SIAFI",
    )
    NOME_ORGAO = StringField(
        source_name = "NOME ÓRGÃO",
        description = "Nome órgão",
    )

    # ── UG ────────────────────────────────────────────────────────────
    CODIGO_UNIDADE_GESTORA = CodigoUGField(
        source_name = "CÓDIGO UNIDADE GESTORA",
        description = "Código UG SIAFI",
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

    # ── Portador ──────────────────────────────────────────────────────
    CPF_PORTADOR = CPFField(
        source_name = "CPF PORTADOR",
        description = "CPF do portador. Chave: cpgf.CPF PORTADOR, servidores",
    )
    NOME_PORTADOR = StringField(
        source_name = "NOME PORTADOR",
        description = "Nome do portador",
    )

    # ── Favorecido ────────────────────────────────────────────────────
    CNPJ_OU_CPF_FAVORECIDO = CPFCNPJField(
        source_name = "CNPJ OU CPF FAVORECIDO",
        description = "CNPJ ou CPF do favorecido. Chave: cpgf, cpcc",
    )
    NOME_FAVORECIDO = StringField(
        source_name = "NOME FAVORECIDO",
        description = "Nome do favorecido",
    )

    # ── Execução ──────────────────────────────────────────────────────
    EXECUTOR_DESPESA = StringField(
        source_name = "EXECUTOR DESPESA",
        description = "Executor da despesa",
        nullable    = True,
    )

    # ── Convênio ──────────────────────────────────────────────────────
    NUMERO_CONVENIO = StringField(
        source_name = "NÚMERO CONVÊNIO",
        description = "Número do convênio. Chave: convenios",
        nullable    = True,
    )
    CODIGO_CONVENENTE = StringField(
        source_name = "CÓDIGO CONVENENTE",
        description = "Código do convenente",
        nullable    = True,
    )
    NOME_CONVENENTE = StringField(
        source_name = "NOME CONVENENTE",
        description = "Nome do convenente",
        nullable    = True,
    )

    # ── Repasse ───────────────────────────────────────────────────────
    REPASSE = StringField(
        source_name = "REPASSE",
        description = "Tipo de repasse — VARCHAR",
        nullable    = True,
    )

    # ── Transação ─────────────────────────────────────────────────────
    TRANSACAO = StringField(
        source_name = "TRANSAÇÃO",
        description = "Número da transação",
    )
    DATA_TRANSACAO = DateVarcharField(
        source_name = "DATA TRANSAÇÃO",
        description = "Silver: normalizar para Date",
    )
    VALOR_TRANSACAO = MoneyField(
        source_name = "VALOR TRANSAÇÃO",
        description = "Valor da transação — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
