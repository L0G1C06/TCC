# apps/portal_da_transparencia/models/bpc.py
"""
Benefício de Prestação Continuada (BPC)

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=bpc/
Histórico: 2019 → 2026 (múltiplos arquivos/mês)

Beneficiários do BPC (Loas) com informações sobre benefício, CPF/NIS e dados geográficos.

Chaves de correlação:
    CPF BENEFICIÁRIO → cpgf.CPF PORTADOR, cpdc.CPF PORTADOR,
                       auxilio-brasil.CPF FAVORECIDO,
                       auxilio-emergencial.CPF BENEFICIÁRIO
    NIS BENEFICIÁRIO → bolsa-familia.NIS FAVORECIDO,
                       auxilio-brasil.NIS FAVORECIDO,
                       auxilio-emergencial.NIS BENEFICIÁRIO
    CPF REPRESENTANTE LEGAL → auxilio-emergencial.CPF RESPONSÁVEL
    NIS REPRESENTANTE LEGAL → auxilio-emergencial.NIS RESPONSÁVEL
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


class BPC(DuckDBModel):
    """
    Benefício de Prestação Continuada (BPC) — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        BPC.scan(ano="2022", mes="03").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "bpc"

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

    # ── Beneficiário ──────────────────────────────────────────────────
    NIS_BENEFICIARIO = NISField(
        source_name = "NIS BENEFICIÁRIO",
        description = "NIS do beneficiário. Chave: bolsa-familia, auxilio-brasil, auxilio-emergencial",
    )
    CPF_BENEFICIARIO = CPFField(
        source_name = "CPF BENEFICIÁRIO",
        description = "CPF do beneficiário. Chave: cpgf, cpdc, auxilio-brasil",
    )
    NOME_BENEFICIARIO = StringField(
        source_name = "NOME BENEFICIÁRIO",
        description = "Nome completo do beneficiário",
    )

    # ── Representante Legal ───────────────────────────────────────────
    NIS_REPRESENTANTE_LEGAL = NISField(
        source_name = "NIS REPRESENTANTE LEGAL",
        description = "NIS do representante legal. Chave: auxilio-emergencial.NIS RESPONSÁVEL",
        nullable    = True,
    )
    CPF_REPRESENTANTE_LEGAL = CPFField(
        source_name = "CPF REPRESENTANTE LEGAL",
        description = "CPF do representante legal. Chave: auxilio-emergencial.CPF RESPONSÁVEL",
        nullable    = True,
    )
    NOME_REPRESENTANTE_LEGAL = StringField(
        source_name = "NOME REPRESENTANTE LEGAL",
        description = "Nome completo do representante legal",
        nullable    = True,
    )

    # ── Benefício ─────────────────────────────────────────────────────
    NUMERO_BENEFICIO = StringField(
        source_name = "NÚMERO BENEFÍCIO",
        description = "Número do benefício no INSS/DATAPREV",
    )
    BENEFICIO_JUDICIAL = StringField(
        source_name = "BENEFÍCIO CONCEDIDO JUDICIALMENTE",
        description = "Ex: 'Sim'/'Não'",
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
