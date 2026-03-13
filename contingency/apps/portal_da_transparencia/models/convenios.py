# apps/portal_da_transparencia/models/convenios.py
"""
Convênios

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=convenios/
Histórico: snapshot único (ano=2026/mes=02 — 2 arquivos)

Convênios celebrados entre a Administração Pública Federal e entidades
privadas para execução de atividades de interesse público.

Chaves de correlação:
    NÚMERO CONVÊNIO → cpdc.NÚMERO CONVÊNIO,
                      cepim.NÚMERO CONVÊNIO,
                      apoiamento-emendas-parlamentares-documentos.Código da Emenda
    CÓDIGO CONVENENTE → cpdc.Código Convenente,
                        cepim.CNPJ ENTIDADE
"""

from apps.datalake.orm.fields import (
    NumeroConvenioField,
    UFField,
    CodigoMunicipioSIAFIField,
    NomeMunicipioField,
    CodigoOrgaoField,
    CodigoUGField,
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


class Convenios(DuckDBModel):
    """
    Convênios — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        Convenios.scan(ano="2026", mes="02").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "convenios"

    # ── Convênio ──────────────────────────────────────────────────────
    NUMERO_CONVENIO = NumeroConvenioField(
        source_name = "NÚMERO CONVÊNIO",
        description = "Número do convênio. Chave: cpdc, cepim",
    )
    NUMERO_ORIGINAL = StringField(
        source_name = "NÚMERO ORIGINAL",
        description = "Número original do convênio",
    )

    # ── Ordem Bancária ────────────────────────────────────────────────
    DATA_EMISSAO_OB = DateVarcharField(
        source_name = "DATA EMISSÃO OB",
        description = "Silver: normalizar para Date",
    )
    NUMERO_ORDEM_BANCARIA = StringField(
        source_name = "NÚMERO DA ORDEM BANCÁRIA",
        description = "Número da ordem bancária de liberação",
    )

    # ── Valores ───────────────────────────────────────────────────────
    VALOR_LIBERADO = MoneyField(
        source_name = "VALOR LIBERADO",
        description = "Valor liberado até o momento — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )
    VALOR_CONVENIO = MoneyField(
        source_name = "VALOR CONVÊNIO",
        description = "Valor total do convênio — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )
    VALOR_CONTRAPARTIDA = MoneyField(
        source_name = "VALOR CONTRAPARTIDA",
        description = "Valor da contrapartida — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )

    # ── Geográfico ────────────────────────────────────────────────────
    UF = UFField(
        source_name = "UF",
    )
    CODIGO_SIAFI_MUNICIPIO = CodigoMunicipioSIAFIField(
        source_name = "CÓDIGO SIAFI MUNICÍPIO",
        description = "Código município SIAFI. Chave: cpgf, cpdc, cpcc",
    )
    NOME_MUNICIPIO = NomeMunicipioField(
        source_name = "NOME MUNICÍPIO",
    )

    # ── Situação ──────────────────────────────────────────────────────
    SITUACAO_CONVENIO = StringField(
        source_name = "SITUAÇÃO CONVÊNIO",
        description = "Ex: Ativo, Rescindido, Cancelado",
    )

    # ── Processo ──────────────────────────────────────────────────────
    NUMERO_PROCESSO_CONVENIO = StringField(
        source_name = "NÚMERO PROCESSO DO CONVÊNIO",
        description = "Processo administrativo do convênio",
    )

    # ── Objeto ────────────────────────────────────────────────────────
    OBJETO_CONVENIO = StringField(
        source_name = "OBJETO DO CONVÊNIO",
        description = "Objeto do convênio — texto livre, candidato a NLP",
    )

    # ── Órgão Concedente ──────────────────────────────────────────────
    CODIGO_ORGAO_SUPERIOR = StringField(
        source_name = "CÓDIGO ÓRGÃO SUPERIOR",
        description = "Código órgão superior SIAFI",
    )
    NOME_ORGAO_SUPERIOR = StringField(
        source_name = "NOME ÓRGÃO SUPERIOR",
        description = "Nome órgão superior",
    )
    CODIGO_ORGAO_CONCEDENTE = CodigoOrgaoField(
        source_name = "CÓDIGO ÓRGÃO CONCEDENTE",
        description = "Código órgão concedente SIAFI",
    )
    NOME_ORGAO_CONCEDENTE = StringField(
        source_name = "NOME ÓRGÃO CONCEDENTE",
        description = "Nome órgão concedente",
    )
    CODIGO_UG_CONCEDENTE = CodigoUGField(
        source_name = "CÓDIGO UG CONCEDENTE",
        description = "Código UG concedente. Chave: cpgf, cpdc, cpcc",
    )
    NOME_UG_CONCEDENTE = StringField(
        source_name = "NOME UG CONCEDENTE",
        description = "Nome UG concedente",
    )

    # ── Convenente ────────────────────────────────────────────────────
    CODIGO_CONVENENTE = CNPJField(
        source_name = "CÓDIGO CONVENENTE",
        description = "CNPJ do convenente. Chave: cpdc, cepim",
    )
    TIPO_CONVENENTE = StringField(
        source_name = "TIPO CONVENENTE",
        description = "Ex: ONG, Instituição Pública, Empresa",
    )
    NOME_CONVENENTE = StringField(
        source_name = "NOME CONVENENTE",
        description = "Nome do convenente",
    )
    TIPO_ENTE_CONVENENTE = StringField(
        source_name = "TIPO ENTE CONVENENTE",
        description = "Ex: União, Estado, Município",
    )

    # ── Instrumento ───────────────────────────────────────────────────
    TIPO_INSTRUMENTO = StringField(
        source_name = "TIPO INSTRUMENTO",
        description = "Ex: Convênio, Termo de Parceria",
    )

    # ── Datas ─────────────────────────────────────────────────────────
    DATA_PUBLICACAO = DateVarcharField(
        source_name = "DATA PUBLICAÇÃO",
        description = "Silver: normalizar para Date",
    )
    DATA_INICIO_VIGENCIA = DateVarcharField(
        source_name = "DATA INÍCIO VIGÊNCIA",
        description = "Silver: normalizar para Date",
    )
    DATA_FINAL_VIGENCIA = DateVarcharField(
        source_name = "DATA FINAL VIGÊNCIA",
        description = "Silver: normalizar para Date",
    )
    DATA_ULTIMA_LIBERACAO = DateVarcharField(
        source_name = "DATA ÚLTIMA LIBERAÇÃO",
        description = "Silver: normalizar para Date",
    )

    # ── Última Liberação ──────────────────────────────────────────────
    VALOR_ULTIMA_LIBERACAO = MoneyField(
        source_name = "VALOR ÚLTIMA LIBERAÇÃO",
        description = "Valor da última liberação — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
