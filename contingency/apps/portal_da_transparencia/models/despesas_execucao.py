# apps/portal_da_transparencia/models/despesas_execucao.py
"""
Despesas — Execução

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=despesas-execucao/
Histórico: 2013 → 2026 (múltiplos arquivos/mês)

Detalhamento da execução orçamentária com informações sobre pagamentos,
empenhos e restos a pagar por programa, ação e elemento de despesa.

Chaves de correlação:
    Código Pagamento     → despesas.Código Pagamento
    Código Empenho       → despesas.Código Empenho
    Código Órgão         → compras.Código Órgão,
                           cpgf.CÓDIGO ÓRGÃO
    Código UG            → compras.Código UG,
                           cpgf.CÓDIGO UG
"""

from apps.datalake.orm.fields import (
    CodigoOrgaoSuperiorField,
    CodigoOrgaoField,
    CodigoUGField,
    CodigoFuncaoField,
    CodigoSubfuncaoField,
    CodigoProgramaField,
    CodigoAcaoField,
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


class DespesasExecucao(DuckDBModel):
    """
    Despesas — Execução — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        DespesasExecucao.scan(ano="2022", mes="05").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "despesas-execucao"

    # ── Pagamento ─────────────────────────────────────────────────────
    CODIGO_PAGAMENTO = StringField(
        source_name = "Código Pagamento",
        description = "Código único do pagamento. Chave: despesas",
    )
    CODIGO_PAGAMENTO_RESUMIDO = StringField(
        source_name = "Código Pagamento Resumido",
        description = "Código resumido do pagamento",
    )

    # ── Empenho ───────────────────────────────────────────────────────
    CODIGO_EMPENHO = StringField(
        source_name = "Código Empenho",
        description = "Código do empenho. Chave: despesas",
    )
    ID_EMPENHO = StringField(
        source_name = "Id Empenho",
        description = "ID interno do empenho",
    )

    # ── Orçamentário ──────────────────────────────────────────────────
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

    # ── Sequencial ────────────────────────────────────────────────────
    SEQUENCIAL = StringField(
        source_name = "Sequencial",
        description = "Sequencial do registro",
    )
    VALOR_ATUAL = MoneyField(
        source_name = "Valor Atual",
        description = "Valor atualizado — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
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

    # ── Função, Subfunção, Programa, Ação ─────────────────────────────
    CODIGO_FUNCAO = CodigoFuncaoField(
        source_name = "Código Função",
        description = "Código da função orçamentária LOA",
    )
    FUNCAO = StringField(
        source_name = "Função",
        description = "Nome da função orçamentária",
    )
    CODIGO_SUBFUNCAO = CodigoSubfuncaoField(
        source_name = "Código Subfunção",
        description = "Código da subfunção orçamentária",
    )
    SUBFUNCAO = StringField(
        source_name = "Subfunção",
        description = "Nome da subfunção orçamentária",
    )
    CODIGO_PROGRAMA = CodigoProgramaField(
        source_name = "Código Programa",
        description = "Código do programa orçamentário PPA",
    )
    PROGRAMA = StringField(
        source_name = "Programa",
        description = "Nome do programa orçamentário",
    )
    CODIGO_ACAO = CodigoAcaoField(
        source_name = "Código Ação",
        description = "Código da ação orçamentária LOA",
    )
    ACAO = StringField(
        source_name = "Ação",
        description = "Nome da ação orçamentária",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
