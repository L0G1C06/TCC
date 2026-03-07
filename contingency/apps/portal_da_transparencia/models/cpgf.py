# apps/portal_da_transparencia/models/cpgf.py
"""
Cartão de Pagamento do Governo Federal (CPGF)

Fonte   : Portal da Transparência — CGU
S3      : portal_da_transparencia/parquet/modulo=cpgf/
Histórico: 2013 → 2026
Arquivos : ~12 por ano (1 por mês)

O CPGF é o cartão corporativo usado por servidores federais para
pequenas despesas no dia a dia. Cada linha representa uma transação.

Chaves de correlação:
    CPF PORTADOR        → servidores, pep, viagens, imoveis-funcionais
    CNPJ OU CPF FAVORECIDO → notas-fiscais, favorecidos-pj, cpdc, cpcc
    CÓDIGO ÓRGÃO SUPERIOR  → despesas-execucao, transferencias, compras
    CÓDIGO UNIDADE GESTORA → compras, licitacoes, despesas-execucao
"""

from apps.datalake.orm.fields import (
    # identificadores
    CPFField,
    CPFCNPJField,
    CodigoOrgaoSuperiorField,
    CodigoOrgaoField,
    CodigoUGField,
    # datas e períodos
    AnoExercicioField,
    DateVarcharField,
    # valores
    MoneyField,
    # texto livre
    StringField,
    # partições
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class CPGF(DuckDBModel):
    """
    Cartão de Pagamento do Governo Federal — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        # DuckDB — todas as transações de 2024
        CPGF.scan(ano="2024").fetchdf()

        # Polars — filtrar por órgão
        CPGF.polars(ano="2024", mes="01")
            .filter(pl.col("CÓDIGO ÓRGÃO SUPERIOR") == "26000")
            .collect()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "cpgf"

    # ── Identificação do órgão ────────────────────────────────────────
    CODIGO_ORGAO_SUPERIOR = CodigoOrgaoSuperiorField(
        source_name = "CÓDIGO ÓRGÃO SUPERIOR",
        description = "Ex: '26000' = MEC, '36000' = MS, '25000' = MF",
    )
    NOME_ORGAO_SUPERIOR = StringField(
        source_name = "NOME ÓRGÃO SUPERIOR",
    )
    CODIGO_ORGAO = CodigoOrgaoField(
        source_name = "CÓDIGO ÓRGÃO",
    )
    NOME_ORGAO = StringField(
        source_name = "NOME ÓRGÃO",
    )
    CODIGO_UNIDADE_GESTORA = CodigoUGField(
        source_name = "CÓDIGO UNIDADE GESTORA",
        description = "Unidade executora da despesa no SIAFI",
    )
    NOME_UNIDADE_GESTORA = StringField(
        source_name = "NOME UNIDADE GESTORA",
    )

    # ── Período do extrato ────────────────────────────────────────────
    ANO_EXTRATO = AnoExercicioField(
        source_name = "ANO EXTRATO",
        description = "Ano do extrato do cartão — VARCHAR '2024'",
    )
    MES_EXTRATO = StringField(
        source_name = "MÊS EXTRATO",
        description = "Mês do extrato — VARCHAR '01' a '12'",
    )

    # ── Portador do cartão ────────────────────────────────────────────
    CPF_PORTADOR = CPFField(
        source_name = "CPF PORTADOR",
        description = (
            "CPF do servidor portador do cartão. "
            "Chave: servidores.CPF, pep.CPF, viagens.'CPF viajante'"
        ),
    )
    NOME_PORTADOR = StringField(
        source_name = "NOME PORTADOR",
    )

    # ── Favorecido (quem recebeu o pagamento) ─────────────────────────
    CNPJ_OU_CPF_FAVORECIDO = CPFCNPJField(
        source_name = "CNPJ OU CPF FAVORECIDO",
        description = (
            "CPF (PF) ou CNPJ (PJ) de quem recebeu o pagamento. "
            "Silver: separar em cpf/cnpj pelo tamanho após limpeza. "
            "Chave PJ: notas-fiscais.CNPJ, favorecidos-pj.CNPJ, renuncias.CNPJ. "
            "Chave PF: servidores.CPF"
        ),
    )
    NOME_FAVORECIDO = StringField(
        source_name = "NOME FAVORECIDO",
    )

    # ── Transação ─────────────────────────────────────────────────────
    TRANSACAO = StringField(
        source_name = "TRANSAÇÃO",
        description = "Descrição da transação — texto livre",
    )
    DATA_TRANSACAO = DateVarcharField(
        source_name = "DATA TRANSAÇÃO",
        description = "Data da transação — VARCHAR 'DD/MM/YYYY'. Silver → Date.",
    )
    VALOR_TRANSACAO = MoneyField(
        source_name = "VALOR TRANSAÇÃO",
        description = (
            "Valor da transação — VARCHAR '1.234,56'. "
            "Pode ser negativo em estornos. Silver → Decimal(15,2)."
        ),
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano = PartitionAnoField()
    partition_mes = PartitionMesField()
    partition_modulo = PartitionModuloField()
