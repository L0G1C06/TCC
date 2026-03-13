# apps/portal_da_transparencia/models/pgd_emendas.py
"""
PGD — Emendas Parlamentares

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=pgd-emendas/
Histórico: 2013 → 2026 (múltiplos arquivos/mês)

Informações detalhadas sobre emendas parlamentares inseridas no Plano
Geral de Despesas (PGD), incluindo código, autor, valor e situação.

Chaves de correlação:
    Código da Emenda    → emendas-parlamentares.Código da Emenda,
                          emendas-parlamentares-documentos.Código da Emenda
    Código do Autor     → emendas-parlamentares.Código do Autor,
                          emendas-parlamentares-documentos.Código do Autor
    Código Município SIAFI → cpgf, cpdc, cpcc, convenios
"""

from apps.datalake.orm.fields import (
    CodigoEmendaField,
    CodigoAutorEmendaField,
    UFField,
    CodigoMunicipioSIAFIField,
    NomeMunicipioField,
    CodigoFuncaoField,
    CodigoSubfuncaoField,
    CodigoProgramaField,
    CodigoAcaoField,
    MoneyField,
    StringField,
    BigIntField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class PGDEmendas(DuckDBModel):
    """
    PGD — Emendas Parlamentares — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        PGDEmendas.scan(ano="2022", mes="05").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "pgd-emendas"

    # ── Emenda ────────────────────────────────────────────────────────
    CODIGO_DA_EMENDA = CodigoEmendaField(
        source_name = "Código da Emenda",
        description = "Código único da emenda. Chave: emendas-parlamentares, emendas-parlamentares-documentos",
    )
    NUMERO_DA_EMENDA = StringField(
        source_name = "Número da Emenda",
        description = "Número da emenda parlamentar",
    )
    TIPO_DE_EMENDA = StringField(
        source_name = "Tipo de Emenda",
        description = "Ex: Impositiva, Relatorias",
    )

    # ── Autor ─────────────────────────────────────────────────────────
    CODIGO_DO_AUTOR = CodigoAutorEmendaField(
        source_name = "Código do Autor",
        description = "Código do autor da emenda. Chave: emendas-parlamentares, emendas-parlamentares-documentos, TSE",
    )
    NOME_DO_AUTOR = StringField(
        source_name = "Nome do Autor",
        description = "Nome do parlamentar autor da emenda",
    )
    SIGLA_DO_PARTIDO = StringField(
        source_name = "Sigla do Partido",
        description = "Sigla do partido do autor",
    )
    UF_DO_AUTOR = UFField(
        source_name = "UF do Autor",
    )

    # ── Valor ─────────────────────────────────────────────────────────
    VALOR_EMENDA = MoneyField(
        source_name = "Valor da Emenda",
        description = "Valor da emenda — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )
    VALOR_EMPENHADO = MoneyField(
        source_name = "Valor Empenhado",
        description = "Valor empenhado — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )
    VALOR_PAGO = MoneyField(
        source_name = "Valor Pago",
        description = "Valor pago — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )

    # ── Situação ──────────────────────────────────────────────────────
    SITUACAO_DA_EMENDA = StringField(
        source_name = "Situação da Emenda",
        description = "Ex: Ativa, Inativa, Cancelada",
    )

    # ── Localidade ────────────────────────────────────────────────────
    LOCALIDADE_DE_APLICACAO = StringField(
        source_name = "Localidade de Aplicação",
        description = "Município onde o recurso será aplicado",
    )
    CODIGO_MUNICIPIO_SIAFI = CodigoMunicipioSIAFIField(
        source_name = "Código Município SIAFI",
        description = "Código município SIAFI. Chave: cpgf, cpdc, cpcc, convenios",
    )
    NOME_MUNICIPIO = NomeMunicipioField(
        source_name = "Nome Município",
    )
    UF_MUNICIPIO = UFField(
        source_name = "UF Município",
    )

    # ── Função, Subfunção, Programa, Ação ─────────────────────────────
    CODIGO_FUNCAO = CodigoFuncaoField(
        source_name = "Código Função",
        description = "Código da função orçamentária LOA",
    )
    FUNCAO = StringField(
        source_name = "Função",
        description = "Nome da função orçamentária",
    )
    CODIGO_SUBFUNCAO = CodigoSubfuncaoField(
        source_name = "Código Subfunção",
        description = "Código da subfunção orçamentária",
    )
    SUBFUNCAO = StringField(
        source_name = "Subfunção",
        description = "Nome da subfunção orçamentária",
    )
    CODIGO_PROGRAMA = CodigoProgramaField(
        source_name = "Código Programa",
        description = "Código do programa orçamentário PPA",
    )
    PROGRAMA = StringField(
        source_name = "Programa",
        description = "Nome do programa orçamentário",
    )
    CODIGO_ACAO = CodigoAcaoField(
        source_name = "Código Ação",
        description = "Código da ação orçamentária LOA",
    )
    ACAO = StringField(
        source_name = "Ação",
        description = "Nome da ação orçamentária",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
