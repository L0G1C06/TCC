# apps/portal_da_transparencia/models/pgd_contratos.py
"""
PGD — Contratos

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=pgd-contratos/
Histórico: 2013 → 2026 (múltiplos arquivos/mês)

Informações sobre contratos celebrados pela Administração Pública
Federal com detalhes sobre valores, fornecedores e vigência.

Chaves de correlação:
    Número Contrato     → compras.Número Contrato
    Código Órgão        → compras.Código Órgão,
                          cpgf.CÓDIGO ÓRGÃO
    Código UG           → compras.Código UG,
                          cpgf.CÓDIGO UG
"""

from apps.datalake.orm.fields import (
    CodigoOrgaoSuperiorField,
    CodigoOrgaoField,
    CodigoUGField,
    NumeroContratoField,
    CNPJField,
    DateVarcharField,
    MoneyField,
    StringField,
    BigIntField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class PGDContratos(DuckDBModel):
    """
    PGD — Contratos — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        PGDContratos.scan(ano="2022", mes="05").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "pgd-contratos"

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

    # ── Contrato ──────────────────────────────────────────────────────
    NUMERO_CONTRATO = NumeroContratoField(
        source_name = "Número Contrato",
        description = "Número do contrato SIASG. Chave: compras",
    )
    NUMERO_PROCESSO = StringField(
        source_name = "Número Processo",
        description = "Número do processo administrativo",
    )

    # ── Fornecedor ────────────────────────────────────────────────────
    CNPJ_FORNECEDOR = CNPJField(
        source_name = "CNPJ Fornecedor",
        description = "CNPJ do fornecedor",
    )
    NOME_FORNECEDOR = StringField(
        source_name = "NOME Fornecedor",
        description = "Nome do fornecedor",
    )

    # ── Objeto ────────────────────────────────────────────────────────
    OBJETO_CONTRATO = StringField(
        source_name = "Objeto Contrato",
        description = "Objeto do contrato — texto livre, candidato a NLP",
    )

    # ── Valores ───────────────────────────────────────────────────────
    VALOR_INICIAL = MoneyField(
        source_name = "Valor Inicial",
        description = "Valor inicial do contrato — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )
    VALOR_FINAL = MoneyField(
        source_name = "Valor Final",
        description = "Valor final do contrato — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )

    # ── Datas ─────────────────────────────────────────────────────────
    DATA_ASSINATURA = DateVarcharField(
        source_name = "Data Assinatura",
        description = "Silver: normalizar para Date",
    )
    DATA_PUBLICACAO = DateVarcharField(
        source_name = "Data Publicação",
        description = "Silver: normalizar para Date",
    )
    DATA_INICIO_VIGENCIA = DateVarcharField(
        source_name = "Data Início Vigência",
        description = "Silver: normalizar para Date",
    )
    DATA_FIM_VIGENCIA = DateVarcharField(
        source_name = "Data Fim Vigência",
        description = "Silver: normalizar para Date",
    )

    # ── Situação ──────────────────────────────────────────────────────
    SITUACAO_CONTRATO = StringField(
        source_name = "Situação Contrato",
        description = "Ex: Ativo, Rescindido, Cancelado",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
