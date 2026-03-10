# apps/bndes/models/operacoes_financiamento.py
"""
BNDES — Operações de Financiamento (Diretas e Indiretas)

Fonte   : BNDES Dados Abertos
S3      : bndes/parquet/modulo=operacoes-de-financiamento/
Arquivos:
    operacoes-financiamento-operacoes-indiretas-automaticas.parquet
    operacoes-financiamento-operacoes-nao-automaticas.parquet

Schema resultante é a union dos 2 arquivos (union_by_name=true).

Chaves de correlação:
    cpf_cnpj / cnpj             → servidores.CPF, favorecidos-pj.CNPJ
    cnpj_do_agente_financeiro   → favorecidos-pj
    cnpj_da_instituicao_*       → favorecidos-pj
    numero_do_contrato          → contratos SIASG (futuro)
    subsetor_cnae_codigo        → Receita Federal (CNPJ aberto)
    municipio_codigo            → IBGE, outros datasets municipais

Inconsistências identificadas no S3:
    valor_da_operacao_em_reais  → BIGINT (esperado VARCHAR — verificar origem)
    municipio_codigo            → BIGINT (Silver: zero-fill para 7 dígitos)
    prazo_*_meses               → BIGINT
    numero_do_contrato          → BIGINT
"""

from apps.datalake.orm.fields import (
    CNPJField,
    CPFCNPJField,
    UFField,
    DateVarcharField,
    MoneyField,
    BigIntField,
    StringField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class OperacoesFinanciamento(DuckDBModel):
    """
    Financiamento BNDES — camada Bronze.
    União de indiretas-automaticas + nao-automaticas via union_by_name.
    """

    dataset_path = "bndes/parquet/"
    modulo       = "operacoes-de-financiamento"

    # ── Cliente ───────────────────────────────────────────────────────
    cliente = StringField(source_name="cliente")
    cpf_cnpj = CPFCNPJField(
        source_name = "cpf_cnpj",
        description = (
            "CPF (PF) ou CNPJ (PJ) do tomador principal. "
            "Silver: separar pelo tamanho após limpeza."
        ),
    )
    cnpj = CNPJField(
        source_name = "cnpj",
        description = (
            "CNPJ alternativo — presente em operações não-automáticas. "
            "⚠️ Coexiste com cpf_cnpj no mesmo registro. Silver: consolidar."
        ),
        nullable    = True,
    )
    porte_do_cliente = StringField(source_name="porte_do_cliente")
    natureza_do_cliente = StringField(source_name="natureza_do_cliente")

    # ── Localização ───────────────────────────────────────────────────
    uf = UFField(source_name="uf")
    municipio = StringField(
        source_name = "municipio",
        description = "Nome do município — não usar como chave",
    )
    municipio_codigo = BigIntField(
        source_name = "municipio_codigo",
        description = "Código IBGE (BIGINT). Silver: zero-fill para 7 dígitos.",
    )

    # ── Operação ──────────────────────────────────────────────────────
    data_da_contratacao = DateVarcharField(
        source_name = "data_da_contratacao",
        description = "Silver: normalizar para Date",
    )
    situacao_da_operacao = StringField(source_name="situacao_da_operacao")
    descricao_do_projeto = StringField(
        source_name = "descricao_do_projeto",
        description = "Texto livre com objeto do financiamento — candidato a NLP",
        nullable    = True,
    )
    numero_do_contrato = BigIntField(
        source_name = "numero_do_contrato",
        description = "Identificador do contrato (BIGINT). Silver: chave com SIASG.",
        is_join_key = True,
        nullable    = True,
    )
    situacao_do_contrato = StringField(
        source_name = "situacao_do_contrato",
        nullable    = True,
    )
    tipo_de_garantia = StringField(source_name="tipo_de_garantia", nullable=True)
    tipo_de_excepcionalidade = StringField(
        source_name = "tipo_de_excepcionalidade",
        description = "Ex: emergencial, calamidade. Nulo em operações normais.",
        nullable    = True,
    )

    # ── Classificação ─────────────────────────────────────────────────
    area_operacional = StringField(source_name="area_operacional")
    modalidade_de_apoio = StringField(source_name="modalidade_de_apoio")
    forma_de_apoio = StringField(source_name="forma_de_apoio")
    produto = StringField(source_name="produto")
    instrumento_financeiro = StringField(source_name="instrumento_financeiro")
    inovacao = StringField(source_name="inovacao")
    fonte_de_recurso_desembolsos = StringField(source_name="fonte_de_recurso_desembolsos")
    custo_financeiro = StringField(source_name="custo_financeiro")

    # ── Setorial / CNAE ───────────────────────────────────────────────
    setor_cnae = StringField(source_name="setor_cnae")
    subsetor_cnae_agrupado = StringField(source_name="subsetor_cnae_agrupado")
    subsetor_cnae_codigo = StringField(
        source_name = "subsetor_cnae_codigo",
        description = "Código CNAE detalhado — chave com Receita Federal (CNPJ aberto)",
    )
    subsetor_cnae_nome = StringField(source_name="subsetor_cnae_nome")
    setor_bndes = StringField(source_name="setor_bndes")
    subsetor_bndes = StringField(source_name="subsetor_bndes")

    # ── Agente financeiro ─────────────────────────────────────────────
    instituicao_financeira_credenciada = StringField(
        source_name = "instituicao_financeira_credenciada",
        description = "Nome do banco repassador — nulo em operações diretas",
        nullable    = True,
    )
    cnpj_do_agente_financeiro = CNPJField(
        source_name = "cnpj_do_agente_financeiro",
        nullable    = True,
    )
    cnpj_da_instituicao_financeira_credenciada = CNPJField(
        source_name = "cnpj_da_instituicao_financeira_credenciada",
        description = (
            "⚠️ Campo distinto de cnpj_do_agente_financeiro — "
            "presente em operações não-automáticas. Silver: consolidar os dois."
        ),
        nullable    = True,
    )

    # ── Valores ───────────────────────────────────────────────────────
    valor_da_operacao_em_reais = BigIntField(
        source_name = "valor_da_operacao_em_reais",
        description = (
            "⚠️ BIGINT no S3 — incomum para valor monetário. "
            "Provavelmente valor em centavos ou truncado. Silver: investigar escala."
        ),
    )
    valor_contratado_reais = MoneyField(
        source_name = "valor_contratado_reais",
        description = "Valor contratado em BRL — VARCHAR. Presente em não-automáticas.",
        nullable    = True,
    )
    valor_desembolsado_reais = MoneyField(
        source_name = "valor_desembolsado_reais",
        description = (
            "⚠️ Grafia sem '_em_' — exclusiva deste módulo. "
            "Diferente de valor_desembolsado_em_reais do módulo exportação."
        ),
    )
    juros = StringField(
        source_name = "juros",
        description = "Taxa de juros — Silver: normalizar para Float",
    )
    prazo_carencia_meses = BigIntField(
        source_name = "prazo_carencia_meses",
        description = "Prazo de carência em meses (BIGINT)",
    )
    prazo_amortizacao_meses = BigIntField(
        source_name = "prazo_amortizacao_meses",
        description = "Prazo de amortização em meses (BIGINT)",
    )

    # ── Partição ─────────────────────────────────────────────────────
    partition_modulo = PartitionModuloField()