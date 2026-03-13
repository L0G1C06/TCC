# apps/portal_da_transparencia/models/auxilio_brasil.py
"""
Auxílio Brasil

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=auxilio-brasil/
Histórico: 2021 → 2023 (11/12 — 6 arquivos/ano)

Beneficiários do programa social Auxílio Brasil com informações sobre
parcelas pagas, CPF/NIS e dados geográficos.

Chaves de correlação:
    CPF FAVORECIDO → cpgf.CPF PORTADOR, cpdc.CPF PORTADOR,
                     auxilio-emergencial.CPF BENEFICIÁRIO,
                     bpc.CPF BENEFICIÁRIO
    NIS FAVORECIDO → bolsa-familia.NIS FAVORECIDO,
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


class AuxilioBrasil(DuckDBModel):
    """
    Auxílio Brasil — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        AuxilioBrasil.scan(ano="2022", mes="03").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "auxilio-brasil"

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
        description = "CPF do beneficiário. Chave: cpgf, cpdc, auxilio-emergencial",
    )
    NIS_FAVORECIDO = NISField(
        source_name = "NIS FAVORECIDO",
        description = "NIS do beneficiário. Chave: bolsa-familia, auxilio-emergencial, bpc",
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
