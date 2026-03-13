# apps/portal_da_transparencia/models/bolsa_familia_pagamentos.py
"""
Bolsa Família — Pagamentos

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=bolsa-familia-pagamentos/
Histórico: 2013 → 2021 (múltiplos arquivos/mês)

Beneficiários do programa Bolsa Família com informações sobre parcelas
pagas, CPF/NIS e dados geográficos.

Chaves de correlação:
    CPF FAVORECIDO → cpgf.CPF PORTADOR, cpdc.CPF PORTADOR,
                     auxilio-brasil.CPF FAVORECIDO,
                     auxilio-emergencial.CPF BENEFICIÁRIO
    NIS FAVORECIDO → auxilio-brasil.NIS FAVORECIDO,
                     auxilio-emergencial.NIS BENEFICIÁRIO,
                     bpc.NIS BENEFICIÁRIO
    CÓDIGO MUNICÍPIO SIAFI → cpgf, cpdc, cpcc, convenios
"""

from apps.datalake.orm.fields import (
    CPFField,
    NISField,
    UFField,
    CodigoMunicipioSIAFIField,
    NomeMunicipioField,
    MoneyField,
    StringField,
    BigIntField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class BolsaFamiliaPagamentos(DuckDBModel):
    """
    Bolsa Família — Pagamentos — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        BolsaFamiliaPagamentos.scan(ano="2020", mes="03").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "bolsa-familia-pagamentos"

    # ── Competência e Referência ──────────────────────────────────────
    MES_COMPETENCIA = StringField(
        source_name = "MÊS COMPETÊNCIA",
        description = "Mês de referência da informação",
    )
    MES_REFERENCIA = StringField(
        source_name = "MÊS REFERÊNCIA",
        description = "Mês de referência do pagamento",
    )

    # ── Geográfico ────────────────────────────────────────────────────
    UF = UFField(
        source_name = "UF",
    )
    CODIGO_MUNICIPIO_SIAFI = CodigoMunicipioSIAFIField(
        source_name = "CÓDIGO MUNICÍPIO SIAFI",
        description = "Chave: cpgf, cpdc, cpcc, convenios",
    )
    NOME_MUNICIPIO = NomeMunicipioField(
        source_name = "NOME MUNICÍPIO",
    )

    # ── Favorecido ────────────────────────────────────────────────────
    CPF_FAVORECIDO = CPFField(
        source_name = "CPF FAVORECIDO",
        description = "CPF do beneficiário. Chave: cpgf, cpdc, auxilio-brasil",
    )
    NIS_FAVORECIDO = NISField(
        source_name = "NIS FAVORECIDO",
        description = "NIS do beneficiário. Chave: auxilio-brasil, auxilio-emergencial, bpc",
    )
    NOME_FAVORECIDO = StringField(
        source_name = "NOME FAVORECIDO",
        description = "Nome completo do beneficiário",
    )

    # ── Valor ─────────────────────────────────────────────────────────
    VALOR_PARCELA = MoneyField(
        source_name = "VALOR PARCELA",
        description = "Valor da parcela — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
