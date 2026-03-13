# apps/portal_da_transparencia/models/auxilio_emergencial.py
"""
Auxílio Emergencial

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=auxilio-emergencial/
Histórico: 2020 → 2024 (múltiplos arquivos/mês)

Beneficiários do Auxílio Emergencial (2020-2021) e Auxílio Emergencial
Extensão (2021-2022) com informações sobre enquadramento, CPF/NIS e valores.

Chaves de correlação:
    CPF BENEFICIÁRIO → cpgf.CPF PORTADOR, cpdc.CPF PORTADOR,
                       auxilio-brasil.CPF FAVORECIDO,
                       bpc.CPF BENEFICIÁRIO
    NIS BENEFICIÁRIO → bolsa-familia.NIS FAVORECIDO,
                       auxilio-brasil.NIS FAVORECIDO,
                       bpc.NIS BENEFICIÁRIO
    CPF RESPONSÁVEL  → bpc.CPF RESPONSÁVEL LEGAL
    NIS RESPONSÁVEL  → bpc.NIS REPRESENTANTE LEGAL
"""

from apps.datalake.orm.fields import (
    CPFField,
    NISField,
    UFField,
    CodigoMunicipioIBGEField,
    NomeMunicipioField,
    EnquadramentoField,
    MoneyField,
    StringField,
    BigIntField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class AuxilioEmergencial(DuckDBModel):
    """
    Auxílio Emergencial — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        AuxilioEmergencial.scan(ano="2020", mes="04").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "auxilio-emergencial"

    # ── Disponibilização ──────────────────────────────────────────────
    MES_DISPONIBILIZACAO = StringField(
        source_name = "MÊS DISPONIBILIZAÇÃO",
        description = "Mês de disponibilização do benefício",
    )

    # ── Geográfico ────────────────────────────────────────────────────
    UF = UFField(
        source_name = "UF",
    )
    CODIGO_MUNICIPIO_IBGE = CodigoMunicipioIBGEField(
        source_name = "CÓDIGO MUNICÍPIO IBGE",
        description = "Código IBGE 7 dígitos. Silver: zero-fill até 7 dígitos",
    )
    NOME_MUNICIPIO = NomeMunicipioField(
        source_name = "NOME MUNICÍPIO",
    )

    # ── Beneficiário ──────────────────────────────────────────────────
    NIS_BENEFICIARIO = NISField(
        source_name = "NIS BENEFICIÁRIO",
        description = "NIS do beneficiário. Chave: bolsa-familia, auxilio-brasil, bpc",
    )
    CPF_BENEFICIARIO = CPFField(
        source_name = "CPF BENEFICIÁRIO",
        description = "CPF do beneficiário. Chave: cpgf, cpdc, auxilio-brasil",
    )
    NOME_BENEFICIARIO = StringField(
        source_name = "NOME BENEFICIÁRIO",
        description = "Nome completo do beneficiário",
    )

    # ── Responsável ───────────────────────────────────────────────────
    NIS_RESPONSAVEL = NISField(
        source_name = "NIS RESPONSÁVEL",
        description = "NIS do responsável legal. Chave: bpc.NIS REPRESENTANTE LEGAL",
        nullable    = True,
    )
    CPF_RESPONSAVEL = CPFField(
        source_name = "CPF RESPONSÁVEL",
        description = "CPF do responsável legal. Chave: bpc.CPF RESPONSÁVEL LEGAL",
        nullable    = True,
    )
    NOME_RESPONSAVEL = StringField(
        source_name = "NOME RESPONSÁVEL",
        description = "Nome completo do responsável legal",
        nullable    = True,
    )

    # ── Enquadramento ─────────────────────────────────────────────────
    ENQUADRAMENTO = EnquadramentoField(
        source_name = "ENQUADRAMENTO",
        description = "Ex: Trabalhador Informal, MEI, Desempregado",
    )

    # ── Parcela ───────────────────────────────────────────────────────
    PARCELA = StringField(
        source_name = "PARCELA",
        description = "Número da parcela (1ª, 2ª, etc.)",
    )

    # ── Observação ────────────────────────────────────────────────────
    OBSERVACAO = StringField(
        source_name = "OBSERVAÇÃO",
        description = "Texto livre — candidato a NLP",
        nullable    = True,
    )

    # ── Valor ─────────────────────────────────────────────────────────
    VALOR_BENEFICIO = MoneyField(
        source_name = "VALOR BENEFÍCIO",
        description = "Valor do benefício — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
