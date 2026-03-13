# apps/portal_da_transparencia/models/pgd_servicos.py
"""
PGD — Serviços

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=pgd-servicos/
Histórico: 2013 → 2026 (múltiplos arquivos/mês)

Informações sobre despesas com serviços da Administração Pública Federal,
incluindo contratos, prestação de serviços e outros tipos de despesas.

Chaves de correlação:
    Código Órgão         → compras.Código Órgão,
                           cpgf.CÓDIGO ÓRGÃO
    Código UG            → compras.Código UG,
                           cpgf.CÓDIGO UG
"""

from apps.datalake.orm.fields import (
    CodigoOrgaoSuperiorField,
    CodigoOrgaoField,
    CodigoUGField,
    CodigoCategoriaDespesaField,
    CodigoGrupoDespesaField,
    CodigoModalidadeAplicacaoField,
    CodigoElementoDespesaField,
    CodigoSubElementoDespesaField,
    DateVarcharField,
    MoneyField,
    StringField,
    BigIntField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class PGDServicos(DuckDBModel):
    """
    PGD — Serviços — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        PGDServicos.scan(ano="2022", mes="05").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "pgd-servicos"

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

    # ── Despesa ───────────────────────────────────────────────────────
    CODIGO_CATEGORIA_DESPESA = CodigoCategoriaDespesaField(
        source_name = "Código Categoria de Despesa",
        description = "Código da categoria de despesa",
    )
    CATEGORIA_DESPESA = StringField(
        source_name = "Categoria de Despesa",
        description = "Nome da categoria de despesa",
    )
    CODIGO_GRUPO_DESPESA = CodigoGrupoDespesaField(
        source_name = "Código Grupo de Despesa",
        description = "Código do grupo de despesa",
    )
    GRUPO_DESPESA = StringField(
        source_name = "Grupo de Despesa",
        description = "Nome do grupo de despesa",
    )
    CODIGO_MODALIDADE_APLICACAO = CodigoModalidadeAplicacaoField(
        source_name = "Código Modalidade de Aplicação",
        description = "Código da modalidade de aplicação",
    )
    MODALIDADE_APLICACAO = StringField(
        source_name = "Modalidade de Aplicação",
        description = "Nome da modalidade de aplicação",
    )
    CODIGO_ELEMENTO_DESPESA = CodigoElementoDespesaField(
        source_name = "Código Elemento de Despesa",
        description = "Código do elemento de despesa",
    )
    ELEMENTO_DESPESA = StringField(
        source_name = "Elemento de Despesa",
        description = "Nome do elemento de despesa",
    )
    CODIGO_SUBELEMENTO_DESPESA = CodigoSubElementoDespesaField(
        source_name = "Código SubElemento de Despesa",
        description = "Código do subelemento de despesa",
    )
    SUBELEMENTO_DESPESA = StringField(
        source_name = "SubElemento de Despesa",
        description = "Nome do subelemento de despesa",
    )

    # ── Descrição ─────────────────────────────────────────────────────
    DESCRICAO = StringField(
        source_name = "Descrição",
        description = "Descrição da despesa — texto livre, candidato a NLP",
    )
    QUANTIDADE = StringField(
        source_name = "Quantidade",
        description = "Quantidade da despesa",
    )
    VALOR_UNITARIO = MoneyField(
        source_name = "Valor Unitário",
        description = "Valor unitário — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )
    VALOR_TOTAL = MoneyField(
        source_name = "Valor Total",
        description = "Valor total — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )

    # ── Data ──────────────────────────────────────────────────────────
    DATA_EMISSAO = DateVarcharField(
        source_name = "Data Emissão",
        description = "Silver: normalizar para Date",
    )

    # ── Documento ─────────────────────────────────────────────────────
    CODIGO_TIPO_DOCUMENTO = StringField(
        source_name = "Código Tipo Documento",
        description = "Código do tipo de documento",
    )
    TIPO_DOCUMENTO = StringField(
        source_name = "Tipo Documento",
        description = "Nome do tipo de documento",
    )

    # ── Ordem Bancária ────────────────────────────────────────────────
    TIPO_OB = StringField(
        source_name = "Tipo OB",
        description = "Tipo da ordem bancária",
    )

    # ── Extraorçamentário ─────────────────────────────────────────────
    EXTRAORCAMENTARIO = StringField(
        source_name = "Extraorçamentário",
        description = "Ex: 'Sim'/'Não'",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
