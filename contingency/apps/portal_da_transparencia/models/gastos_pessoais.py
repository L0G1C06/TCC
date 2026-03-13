# apps/portal_da_transparencia/models/gastos_pessoais.py
"""
Gastos Pessoais

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=gastos-pessoais/
Histórico: 2013 → 2026 (múltiplos arquivos/mês)

Informações sobre gastos pessoais de servidores e parlamentares,
incluindo passagens, diárias e outros tipos de despesas.

Chaves de correlação:
    CPF viajante         → viagens.CPF viajante
    Código Órgão         → compras.Código Órgão,
                           cpgf.CÓDIGO ÓRGÃO
    Código UG            → compras.Código UG,
                           cpgf.CÓDIGO UG
"""

from apps.datalake.orm.fields import (
    CodigoOrgaoSuperiorField,
    CodigoOrgaoField,
    CodigoUGField,
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


class GastosPessoais(DuckDBModel):
    """
    Gastos Pessoais — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        GastosPessoais.scan(ano="2022", mes="05").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "gastos-pessoais"

    # ── Órgão ─────────────────────────────────────────────────────────
    CODIGO_ORGAO_SUPERIOR = CodigoOrgaoSuperiorField(
        source_name = "Código Órgão Superior",
        description = "Código órgão superior SIAFI",
    )
    ORGAO_SUPERIOR = StringField(
        source_name = "Órgão Superior",
        description = "Nome órgão superior",
    )
    CODIGO_ORGAO = CodigoOrgaoField(
        source_name = "Código Órgão",
        description = "Código órgão SIAFI",
    )
    ORGAO = StringField(
        source_name = "Órgão",
        description = "Nome órgão",
    )

    # ── UG ────────────────────────────────────────────────────────────
    CODIGO_UG = CodigoUGField(
        source_name = "Código Unidade Gestora",
        description = "Código UG SIAFI",
    )
    UG = StringField(
        source_name = "Unidade Gestora",
        description = "Nome UG",
    )

    # ── Servidor/Parlamentar ──────────────────────────────────────────
    CPF_VIAJANTE = CPFField(
        source_name = "CPF viajante",
        description = "CPF do servidor/parlamentar. Chave: viagens",
    )
    NOME_VIAJANTE = StringField(
        source_name = "Nome viajante",
        description = "Nome do servidor/parlamentar",
    )
    CARGO = StringField(
        source_name = "Cargo",
        description = "Cargo do servidor/parlamentar",
    )

    # ── Despesa ───────────────────────────────────────────────────────
    TIPO_DESPESA = StringField(
        source_name = "Tipo Despesa",
        description = "Ex: Passagens, Diárias, Outros",
    )
    DESCRICAO_DESPESA = StringField(
        source_name = "Descrição Despesa",
        description = "Descrição da despesa — texto livre, candidato a NLP",
    )

    # ── Data ──────────────────────────────────────────────────────────
    DATA_DESPESA = DateVarcharField(
        source_name = "Data Despesa",
        description = "Silver: normalizar para Date",
    )

    # ── Valor ─────────────────────────────────────────────────────────
    VALOR_DESPESA = MoneyField(
        source_name = "Valor Despesa",
        description = "Valor da despesa — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
