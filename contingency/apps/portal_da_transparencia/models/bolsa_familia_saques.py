# apps/portal_da_transparencia/models/bolsa_familia_saques.py
"""
Bolsa Família — Saques

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=bolsa-familia-saques/
Histórico: 2013 → 2021 (múltiplos arquivos/mês)

Registros de saques realizados por beneficiários do programa Bolsa Família,
com informações sobre data do saque e valores.

Chaves de correlação:
    CPF FAVORECIDO → cpgf.CPF PORTADOR, cpdc.CPF PORTADOR,
                     bolsa-familia-pagamentos.CPF FAVORECIDO
    NIS FAVORECIDO → auxilio-brasil.NIS FAVORECIDO,
                     bolsa-familia-pagamentos.NIS FAVORECIDO,
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
    DateVarcharField,
    StringField,
    BigIntField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class BolsaFamiliaSaques(DuckDBModel):
    """
    Bolsa Família — Saques — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        BolsaFamiliaSaques.scan(ano="2020", mes="03").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "bolsa-familia-saques"

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
        description = "CPF do beneficiário. Chave: cpgf, cpdc, bolsa-familia-pagamentos",
    )
    NIS_FAVORECIDO = NISField(
        source_name = "NIS FAVORECIDO",
        description = "NIS do beneficiário. Chave: auxilio-brasil, bolsa-familia-pagamentos, bpc",
    )
    NOME_FAVORECIDO = StringField(
        source_name = "NOME FAVORECIDO",
        description = "Nome completo do beneficiário",
    )

    # ── Saque ─────────────────────────────────────────────────────────
    DATA_Saque = DateVarcharField(
        source_name = "DATA SAQUE",
        description = "Silver: normalizar para Date",
    )
    VALOR_PARCELA = MoneyField(
        source_name = "VALOR PARCELA",
        description = "Valor do saque — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
