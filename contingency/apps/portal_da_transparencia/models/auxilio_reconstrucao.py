# apps/portal_da_transparencia/models/auxilio_reconstrucao.py
"""
Auxílio Reconstrução

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=auxilio-reconstrucao/
Histórico: 2025 → (múltiplos arquivos/mês)

Beneficiários do Auxílio Reconstrução com informações sobre parcelas pagas,
CPF/NIS, dados geográficos e quantidade de pessoas na família.

Chaves de correlação:
    CPF FAVORECIDO → cpgf.CPF PORTADOR, cpdc.CPF PORTADOR,
                     auxilio-brasil.CPF FAVORECIDO,
                     auxilio-emergencial.CPF BENEFICIÁRIO,
                     bpc.CPF BENEFICIÁRIO
    NIS FAVORECIDO → bolsa-familia.NIS FAVORECIDO,
                     auxilio-brasil.NIS FAVORECIDO,
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


class AuxilioReconstrucao(DuckDBModel):
    """
    Auxílio Reconstrução — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        AuxilioReconstrucao.scan(ano="2025", mes="07").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "auxilio-reconstrucao"

    # ── Referência ────────────────────────────────────────────────────
    MES_REFERENCIA = StringField(
        source_name = "MÊS REFERÊNCIA",
        description = "Mês de referência da informação",
    )

    # ── Geográfico ────────────────────────────────────────────────────
    UF = UFField(
        source_name = "UF",
    )
    CODIGO_MUNICIPIO_SIAFI = CodigoMunicipioSIAFIField(
        source_name = "CÓDIGO MUNICÍPIO SIAFI",
        description = "Código SIAFI. Chave: cpgf, cpdc, cpcc, convenios",
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
        description = "NIS do beneficiário. Chave: bolsa-familia, auxilio-brasil, auxilio-emergencial, bpc",
    )
    NOME_FAVORECIDO = StringField(
        source_name = "NOME FAVORECIDO",
        description = "Nome completo do beneficiário",
    )

    # ── Família ───────────────────────────────────────────────────────
    QUANTIDADE_PESSOAS_FAMILIA = StringField(
        source_name = "QUANTIDADE DE PESSOAS NA FAMÍLIA",
        description = "Número de pessoas na família — VARCHAR. Silver → Integer",
        nullable    = True,
    )

    # ── Parcela ───────────────────────────────────────────────────────
    DATA_EFETIVACAO_PARCELA = StringField(
        source_name = "DATA EFETIVAÇÃO PARCELA",
        description = "Data de efetivação do pagamento — VARCHAR 'DD/MM/YYYY'. Silver → Date",
        nullable    = True,
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
