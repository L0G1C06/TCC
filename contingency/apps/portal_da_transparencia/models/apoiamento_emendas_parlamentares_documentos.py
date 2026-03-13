# apps/portal_da_transparencia/models/apoiamento_emendas_parlamentares_documentos.py
"""
Apoiamento em Emendas Parlamentares — Documentos

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=apoiamento-emendas-parlamentares-documentos/
Histórico: 2020 → 2026 (ano=unknown — 1 arquivo por ano)

Documentos relacionados ao apoio de emendas parlamentares, incluindo
empenhos, pagamentos e movimentações financeiras.

Chaves de correlação:
    Código Apoiador     → estrutura SIAFI (órgãos)
    Código da Emenda    → emendas-parlamentares.Código da Emenda,
                          emendas-parlamentares-documentos.Código da Emenda
    Código UG           → cpgf, cpdc, cpcc, compras, despesas-execucao
    Código Órgão        → cpgf, cpdc, cpcc, compras, despesas-execucao
"""

from apps.datalake.orm.fields import (
    CodigoOrgaoField,
    CodigoUGField,
    CodigoEmendaField,
    CodigoAutorEmendaField,
    UFField,
    NomeMunicipioField,
    DateVarcharField,
    MoneyField,
    StringField,
    BigIntField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class ApoiamentoEmendasParlamentaresDocumentos(DuckDBModel):
    """
    Apoiamento em Emendas Parlamentares — Documentos — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        ApoiamentoEmendasParlamentaresDocumentos.scan(ano="2024").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "apoiamento-emendas-parlamentares-documentos"

    # ── Apoiador ──────────────────────────────────────────────────────
    CODIGO_APOIADOR = StringField(
        source_name = "Código Apoiador",
        description = "Código do órgão que apoia a emenda",
    )
    APOIADOR = StringField(
        source_name = "Apoiador",
        description = "Nome do órgão que apoia a emenda",
    )

    # ── Data do Apoio ─────────────────────────────────────────────────
    DATA_APOIO = DateVarcharField(
        source_name = "Data do Apoio",
        description = "Silver: normalizar para Date",
    )
    DATA_RETIRADA_APOIO = DateVarcharField(
        source_name = "Data Retirada do Apoio",
        description = "Silver: normalizar para Date",
        nullable    = True,
    )

    # ── Empenho ───────────────────────────────────────────────────────
    EMPENHO = StringField(
        source_name = "Empenho",
        description = "Número do empenho",
    )
    DATA_ULTIMA_MOVIMENTACAO_EMPENHO = DateVarcharField(
        source_name = "Data última movimentação Empenho",
        description = "Silver: normalizar para Date",
    )

    # ── Favorecido ────────────────────────────────────────────────────
    CODIGO_FAVORECIDO = StringField(
        source_name = "Código favorecido",
        description = "Código do favorecido",
    )
    FAVORECIDO = StringField(
        source_name = "Favorecido",
        description = "Nome do favorecido",
    )
    TIPO_FAVORECIDO = StringField(
        source_name = "Tipo Favorecido",
        description = "Ex: Pessoa Física, Pessoa Jurídica",
    )
    UF_FAVORECIDO = UFField(
        source_name = "UF Favorecido",
    )
    MUNICIPIO_FAVORECIDO = NomeMunicipioField(
        source_name = "Município Favorecido",
    )

    # ── Emenda Parlamentar ────────────────────────────────────────────
    CODIGO_DA_EMENDA = CodigoEmendaField(
        source_name = "Código da Emenda",
        description = "Chave: emendas-parlamentares, emendas-parlamentares-documentos",
    )
    TIPO_DE_EMENDA = StringField(
        source_name = "Tipo de Emenda",
        description = "Ex: Impositiva, Relatorias",
    )
    ANO_DA_EMENDA = StringField(
        source_name = "Ano da Emenda",
        description = "Ano da emenda parlamentar",
    )
    CODIGO_AUTOR_EMENDA = CodigoAutorEmendaField(
        source_name = "Código do Autor da Emenda",
        description = "Chave: emendas-parlamentares, TSE (candidatos)",
    )
    NOME_AUTOR_EMENDA = StringField(
        source_name = "Nome do Autor da Emenda",
        description = "Nome do parlamentar autor da emenda",
    )
    NUMERO_DA_EMENDA = StringField(
        source_name = "Número da emenda",
        description = "Número da emenda parlamentar",
    )
    LOCALIDADE_APLICACAO_RECURSO = StringField(
        source_name = "Localidade de aplicação do recurso",
        description = "Município onde o recurso será aplicado",
    )

    # ── UG e Órgão ────────────────────────────────────────────────────
    CODIGO_UG = CodigoUGField(
        source_name = "Código UG",
        description = "Unidade Gestora executora. Chave: cpgf, cpdc, cpcc",
    )
    UG = StringField(
        source_name = "UG",
        description = "Nome da Unidade Gestora",
    )
    CODIGO_UNIDADE_ORCAMENTARIA = StringField(
        source_name = "Código Unidade Orçamentária",
        description = "Código da Unidade Orçamentária SIAFI",
    )
    UNIDADE_ORCAMENTARIA = StringField(
        source_name = "Unidade Orçamentária",
        description = "Nome da Unidade Orçamentária",
    )
    CODIGO_ORGAO_SIAFI = CodigoOrgaoField(
        source_name = "Código Órgão SIAFI",
        description = "Código do órgão SIAFI",
    )
    ORGAO = StringField(
        source_name = "Órgão",
        description = "Nome do órgão",
    )
    CODIGO_ORGAO_SUPERIOR_SIAFI = StringField(
        source_name = "Código Órgão Superior SIAFI",
        description = "Código do órgão superior SIAFI",
    )
    ORGAO_SUPERIOR = StringField(
        source_name = "Órgão Superior",
        description = "Nome do órgão superior",
    )

    # ── Ação Orçamentária ─────────────────────────────────────────────
    CODIGO_ACAO = StringField(
        source_name = "Código Ação",
        description = "Código da ação orçamentária LOA",
    )
    ACAO = StringField(
        source_name = "Ação",
        description = "Nome da ação orçamentária",
    )

    # ── Valores ───────────────────────────────────────────────────────
    VALOR_EMPENHADO = MoneyField(
        source_name = "Valor Empenhado",
        description = "Valor empenhado — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )
    VALOR_CANCELADO = MoneyField(
        source_name = "Valor Cancelado",
        description = "Valor cancelado — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )
    VALOR_PAGO = MoneyField(
        source_name = "Valor Pago",
        description = "Valor pago — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
