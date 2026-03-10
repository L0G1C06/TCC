# apps/portal_da_transparencia/models/licitacoes.py
"""
Licitações Federais

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=licitacoes/
Histórico: 2013 → 2024-04  |  ~48 arquivos/ano

Cada linha representa um participante (licitante) em um item de licitação.
A granularidade é item × licitante × licitação × UG × mês.

⚠️  Dataset descontinuado a partir de 2024-05 no Portal.
    Dados de compras mais recentes: módulo compras.

Chaves de correlação:
    Código UG           → compras, cpgf, despesas-execucao
    Código Órgão        → compras, cpgf, despesas-execucao, transferencias
    Código Item Compra  → compras.Código Item Compra
    Número Licitação    → contratos SIASG/ComprasNet (externo)
    Número Processo     → acordos-leniencia, ceis, cnep
"""

from apps.datalake.orm.fields import (
    CodigoOrgaoField,
    CodigoUGField,
    NumeroLicitacaoField,
    NumeroProcessoField,
    StringField,
    BigIntField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class Licitacoes(DuckDBModel):
    """
    Participantes de licitações federais — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    ⚠️  Histórico encerrado em 2024-04. Anos posteriores: usar módulo compras.

    Uso:
        Licitacoes.scan(ano="2023").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "licitacoes"

    # ── Licitação ─────────────────────────────────────────────────────
    NUMERO_LICITACAO = NumeroLicitacaoField(
        source_name = "Número Licitação",
        description = "Identificador da licitação no SIASG. Chave: compras (via item)",
    )
    NUMERO_PROCESSO = NumeroProcessoField(
        source_name = "Número Processo",
        description = "Processo administrativo vinculado. Chave: ceis, cnep, acordos-leniencia",
    )
    CODIGO_MODALIDADE_COMPRA = StringField(
        source_name = "Código Modalidade Compra",
        description = "Ex: '01'=Convite, '02'=Tomada de Preços, '05'=Pregão",
    )
    MODALIDADE_COMPRA = StringField(
        source_name = "Modalidade Compra",
        description = "Descrição da modalidade licitatória",
    )

    # ── Órgão e Unidade Gestora ───────────────────────────────────────
    CODIGO_ORGAO = CodigoOrgaoField(
        source_name = "Código Órgão",
    )
    NOME_ORGAO = StringField(
        source_name = "Nome Órgão",
    )
    CODIGO_UG = CodigoUGField(
        source_name = "Código UG",
        description = "Unidade Gestora licitante. Chave: compras, cpgf, despesas-execucao",
    )
    NOME_UG = StringField(
        source_name = "Nome UG",
    )

    # ── Item ──────────────────────────────────────────────────────────
    CODIGO_ITEM_COMPRA = StringField(
        source_name = "Código Item Compra",
        description = "Código do item licitado. Chave: compras.Código Item Compra",
        is_join_key = True,
    )
    DESCRICAO_ITEM_COMPRA = StringField(
        source_name = "Descrição Item Compra",
    )

    # ── Participante ──────────────────────────────────────────────────
    CODIGO_PARTICIPANTE = StringField(
        source_name = "Código Participante",
        description = (
            "CPF ou CNPJ do licitante — VARCHAR sem máscara. "
            "Silver: detectar PF/PJ pelo tamanho e separar."
        ),
        is_join_key = True,
    )
    NOME_PARTICIPANTE = StringField(
        source_name = "Nome Participante",
    )
    FLAG_VENCEDOR = StringField(
        source_name = "Flag Vencedor",
        description = "Indica se o participante venceu o item. Silver: normalizar para Boolean",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()