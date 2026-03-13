# apps/portal_da_transparencia/models/acordos_leniencia.py
"""
Acordos de Leniência

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=acordos-leniencia/
Histórico: snapshot (ano=2026/mes=03 — 2 arquivos)

Empresas e pessoas físicas que firmaram acordos de leniência com órgãos
da Administração Pública Federal.

Chaves de correlação:
    CNPJ DO SANCIONADO → ceis.CPF OU CNPJ DO SANCIONADO,
                         licitacoes.Código Participante,
                         favorecidos-pj
    NÚMERO DO PROCESSO → ceis.NÚMERO DO PROCESSO,
                         licitacoes.Número Processo
"""

from apps.datalake.orm.fields import (
    CNPJField,
    DateVarcharField,
    StringField,
    BigIntField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class AcordosLeniencia(DuckDBModel):
    """
    Acordos de Leniência — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    Uso:
        AcordosLeniencia.scan(ano="2026", mes="03").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "acordos-leniencia"

    # ── Acordo ─────────────────────────────────────────────────────────
    ID_DO_ACORDO = BigIntField(
        source_name = "ID DO ACORDO",
        description = "Identificador único do acordo",
    )
    EFEITO_DO_ACORDO = StringField(
        source_name = "EFEITO DO ACORDO DE LENIENCIA",
        description = "Efeito do acordo (ex: Suspensão condicional)",
    )
    COMPLEMENTO = StringField(
        source_name = "COMPLEMENTO",
        nullable    = True,
    )

    # ── Sancionado ────────────────────────────────────────────────────
    CNPJ_DO_SANCIONADO = CNPJField(
        source_name = "CNPJ DO SANCIONADO",
        description = "CNPJ da empresa sancionada. Chave: ceis, licitacoes",
    )
    RAZAO_SOCIAL_RECEITA = StringField(
        source_name = "RAZÃO SOCIAL – CADASTRO RECEITA",
        description = "Razão social conforme Receita Federal",
    )
    NOME_FANTASIA_RECEITA = StringField(
        source_name = "NOME FANTASIA – CADASTRO RECEITA",
    )

    # ── Datas ─────────────────────────────────────────────────────────
    DATA_INICIO_ACORDO = DateVarcharField(
        source_name = "DATA DE INÍCIO DO ACORDO",
        description = "Silver: normalizar para Date",
    )
    DATA_FIM_ACORDO = DateVarcharField(
        source_name = "DATA DE FIM DO ACORDO",
        description = "Silver: normalizar para Date",
    )

    # ── Situação ──────────────────────────────────────────────────────
    SITUACAO_ACORDO = StringField(
        source_name = "SITUAÇÃO DO ACORDO DE LENIÊNCIA",
        description = "Ex: Ativo, Rescindido, Cumprido",
    )
    DATA_INFORMACAO = DateVarcharField(
        source_name = "DATA DA INFORMAÇÃO",
        description = "Data da última atualização",
    )

    # ── Processo ──────────────────────────────────────────────────────
    NUMERO_PROCESSO = StringField(
        source_name = "NÚMERO DO PROCESSO",
        description = "Processo administrativo. Chave: ceis, licitacoes",
    )

    # ── Termos ────────────────────────────────────────────────────────
    TERMOS_DO_ACORDO = StringField(
        source_name = "TERMOS DO ACORDO",
        description = "Texto livre — candidato a NLP",
    )

    # ── Órgão Sancionador ─────────────────────────────────────────────
    ORGAO_SANCIONADOR = StringField(
        source_name = "ÓRGÃO SANCIONADOR",
        description = "Nome do órgão que firmou o acordo",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
