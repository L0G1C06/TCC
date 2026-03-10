# apps/portal_da_transparencia/models/compras.py
"""
Compras Públicas Federais

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=compras/
Histórico: 2013 → 2026  |  ~48 arquivos/ano (4 por mês)

Cada linha representa um item de um contrato de compra pública.
A granularidade é item × contrato × UG × mês.

Chaves de correlação:
    Código Órgão        → cpgf, cpdc, cpcc, despesas-execucao, transferencias
    Código UG           → cpgf, cpdc, cpcc, licitacoes, despesas-execucao
    Número Contrato     → licitacoes (via Número Licitação → Número Contrato)
    Código Item Compra  → licitacoes.Código Item Compra
"""

from apps.datalake.orm.fields import (
    CodigoOrgaoField,
    CodigoUGField,
    NumeroContratoField,
    MoneyField,
    StringField,
    BigIntField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class Compras(DuckDBModel):
    """
    Itens de compras públicas federais — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        Compras.scan(ano="2024", mes="01").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "compras"

    # ── Órgão e Unidade Gestora ───────────────────────────────────────
    CODIGO_ORGAO = CodigoOrgaoField(
        source_name = "Código Órgão",
    )
    NOME_ORGAO = StringField(
        source_name = "Nome Órgão",
    )
    CODIGO_UG = CodigoUGField(
        source_name = "Código UG",
        description = "Unidade Gestora executora. Chave: licitacoes, cpgf, despesas-execucao",
    )
    NOME_UG = StringField(
        source_name = "Nome UG",
    )

    # ── Contrato ──────────────────────────────────────────────────────
    NUMERO_CONTRATO = NumeroContratoField(
        source_name = "Número Contrato",
        description = "Número do contrato SIASG. Chave futura com licitacoes.",
    )

    # ── Item ──────────────────────────────────────────────────────────
    CODIGO_ITEM_COMPRA = StringField(
        source_name = "Código Item Compra",
        description = "Código do item no SIASG. Chave: licitacoes.Código Item Compra",
        is_join_key = True,
    )
    DESCRICAO_ITEM_COMPRA = StringField(
        source_name = "Descrição Item Compra",
    )
    DESCRICAO_COMPLEMENTAR_ITEM_COMPRA = StringField(
        source_name = "Descrição Complementar Item Compra",
        description = "Texto livre complementar — candidato a NLP",
        nullable    = True,
    )
    QUANTIDADE_ITEM = StringField(
        source_name = "Quantidade Item",
        description = "VARCHAR no S3. Silver: normalizar para Decimal — pode ter vírgula decimal",
    )
    VALOR_ITEM = MoneyField(
        source_name = "Valor Item",
        description = "Valor unitário ou total do item — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()