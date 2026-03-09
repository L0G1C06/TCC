# apps/bndes/models/operacoes_exportacao.py
"""
BNDES — Operações de Exportação (Pré e Pós-Embarque)

Fonte   : BNDES Dados Abertos
S3      : bndes/parquet/modulo=operacoes-de-exportacaoo-pre-e-pos-embarque/
Arquivos:
    operacoes-exportacao-operacoes-de-exportacao-pre-embarque.parquet
    operacoes-exportacao-operacoes-de-exportacao-pos-embarque-bens.parquet
    operacoes-exportacao-operacoes-de-exportacao-pos-embarque-servicos-de-engenharia.parquet

Schema resultante é a union dos 3 arquivos (union_by_name=true).
Colunas ausentes num arquivo ficam nulas nas linhas daquele arquivo.

Chaves de correlação:
    cnpj_do_exportador          → favorecidos-pj, notas-fiscais
    cnpj_do_agente_financeiro   → favorecidos-pj
    cpf_cnpj                    → servidores.CPF, favorecidos-pj.CNPJ
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


class OperacoesExportacao(DuckDBModel):
    """
    Exportação pré e pós-embarque — camada Bronze.
    União dos 3 arquivos do módulo via union_by_name.
    Campos exclusivos de um subconjunto de arquivos são nullable.
    """

    dataset_path = "bndes/parquet/"
    modulo       = "operacoes-de-exportacaoo-pre-e-pos-embarque"

    # ── Exportador (pré/pós-embarque) ─────────────────────────────────
    exportador = StringField(
        source_name = "exportador",
        description = "Razão social do exportador. Nulo em linhas de financiamento.",
        nullable    = True,
    )
    cnpj_do_exportador = CNPJField(
        source_name = "cnpj_do_exportador",
        nullable    = True,
    )
    porte_do_exportador = StringField(
        source_name = "porte_do_exportador",
        nullable    = True,
    )
    pais_destino_das_exportacoes = StringField(
        source_name = "pais_destino_das_exportacoes",
        nullable    = True,
    )

    # ── Cliente / Tomador (presente em todos os arquivos) ─────────────
    cliente = StringField(
        source_name = "cliente",
        description = "Razão social do tomador do crédito",
        nullable    = True,
    )
    cpf_cnpj = CPFCNPJField(
        source_name = "cpf_cnpj",
        description = (
            "CPF (PF) ou CNPJ (PJ) do tomador. "
            "Silver: separar pelo tamanho após limpeza."
        ),
        nullable    = True,
    )
    porte_do_cliente = StringField(source_name="porte_do_cliente", nullable=True)
    natureza_do_cliente = StringField(source_name="natureza_do_cliente", nullable=True)

    # ── Localização ───────────────────────────────────────────────────
    uf = UFField(source_name="uf")
    municipio = StringField(
        source_name = "municipio",
        description = "Nome do município — não usar como chave",
        nullable    = True,
    )
    municipio_codigo = BigIntField(
        source_name = "municipio_codigo",
        description = "Código IBGE do município (BIGINT). Silver: zero-fill para 7 dígitos.",
        nullable    = True,
    )

    # ── Operação ──────────────────────────────────────────────────────
    numero_da_operacao = StringField(
        source_name = "numero_da_operacao",
        is_join_key = True,
        nullable    = True,
    )
    descricao_da_operacao = StringField(source_name="descricao_da_operacao", nullable=True)
    data_da_contratacao = DateVarcharField(
        source_name = "data_da_contratacao",
        description = "Silver: normalizar para Date",
    )
    situacao_da_operacao = StringField(source_name="situacao_da_operacao")
    tipo_de_garantia = StringField(source_name="tipo_de_garantia", nullable=True)
    categoria = StringField(source_name="categoria", nullable=True)

    # ── Classificação ─────────────────────────────────────────────────
    area_operacional = StringField(source_name="area_operacional")
    modalidade_de_apoio = StringField(source_name="modalidade_de_apoio")
    forma_de_apoio = StringField(source_name="forma_de_apoio")
    produto = StringField(source_name="produto")
    modalidade_operacional = StringField(source_name="modalidade_operacional", nullable=True)
    instrumento_financeiro = StringField(source_name="instrumento_financeiro", nullable=True)
    inovacao = StringField(source_name="inovacao", nullable=True)
    setor_subsetor_de_atividade = StringField(source_name="setor_subsetor_de_atividade", nullable=True)

    # ── Setorial / CNAE ───────────────────────────────────────────────
    setor_cnae = StringField(source_name="setor_cnae", nullable=True)
    subsetor_cnae_agrupado = StringField(source_name="subsetor_cnae_agrupado", nullable=True)
    subsetor_cnae_codigo = StringField(
        source_name = "subsetor_cnae_codigo",
        description = "Código CNAE — chave com Receita Federal (CNPJ aberto)",
        nullable    = True,
    )
    subsetor_cnae_nome = StringField(source_name="subsetor_cnae_nome", nullable=True)
    setor_bndes = StringField(source_name="setor_bndes", nullable=True)
    subsetor_bndes = StringField(source_name="subsetor_bndes", nullable=True)

    # ── Agente financeiro ─────────────────────────────────────────────
    instituicao_financeira_credenciada = StringField(
        source_name = "instituicao_financeira_credenciada",
        nullable    = True,
    )
    cnpj_do_agente_financeiro = CNPJField(
        source_name = "cnpj_do_agente_financeiro",
        nullable    = True,
    )

    # ── Financeiro / Valores ──────────────────────────────────────────
    moeda_sigla = StringField(
        source_name = "moeda_sigla",
        description = "Ex: USD, EUR. Nulo em operações em reais.",
        nullable    = True,
    )
    fonte_de_recursos_desembolsos = StringField(
        source_name = "fonte_de_recursos_desembolsos",
        description = "⚠️ Grafia com 's' — exclusivo do módulo exportação",
        nullable    = True,
    )
    fonte_de_recurso_desembolsos = StringField(
        source_name = "fonte_de_recurso_desembolsos",
        description = "⚠️ Grafia sem 's' — compartilhado com financiamento",
        nullable    = True,
    )
    custo_financeiro = StringField(source_name="custo_financeiro", nullable=True)
    mutuario = StringField(
        source_name = "mutuario",
        description = "Tomador do crédito no pré/pós-embarque",
        nullable    = True,
    )
    valor_da_operacao_em_um = MoneyField(
        source_name = "valor_da_operacao_em_um",
        description = "Valor contratado em USD (UM). Nulo no pré-embarque.",
        nullable    = True,
    )
    valor_desembolsado_em_um = MoneyField(
        source_name = "valor_desembolsado_em_um",
        description = "Valor liberado em USD. Nulo no pré-embarque.",
        nullable    = True,
    )
    valor_da_operacao_em_reais = MoneyField(
        source_name = "valor_da_operacao_em_reais",
        description = "Valor contratado em BRL — VARCHAR neste módulo",
        nullable    = True,
    )
    valor_desembolsado_em_reais = MoneyField(
        source_name = "valor_desembolsado_em_reais",
        nullable    = True,
    )
    juros = StringField(
        source_name = "juros",
        description = "Taxa de juros — Silver: normalizar para Float",
        nullable    = True,
    )
    prazo_total_meses = BigIntField(
        source_name = "prazo_total_meses",
        description = "Prazo total em meses (BIGINT)",
        nullable    = True,
    )

    # ── Partição ─────────────────────────────────────────────────────
    partition_modulo = PartitionModuloField()