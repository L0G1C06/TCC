# apps/portal_da_transparencia/models/cepim.py
"""
CEPIM — Cadastro de Entidades Impedidas de Contratar

Fonte    : Portal da Transparência — CGU / SENEP
S3       : portal_da_transparencia/parquet/modulo=cepim/
Histórico: snapshot único (ano=2026/mes=03 — 1 arquivo)

Entidades (ONGs, instituições, etc.) impedidas de receber convênios ou
parcerias com a Administração Pública Federal.

Chaves de correlação:
    CNPJ ENTIDADE → convenios.Código Convenente,
                    cpdc.Código Convenente
    NÚMERO CONVÊNIO → convenios.NÚMERO CONVÊNIO
"""

from apps.datalake.orm.fields import (
    CNPJField,
    StringField,
    BigIntField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class CEPIM(DuckDBModel):
    """
    Cadastro de Entidades Impedidas de Contratar — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    ⚠️  Snapshot — não usar partição como dimensão temporal do impedimento.

    Uso:
        CEPIM.scan(ano="2026", mes="03").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "cepim"

    # ── Entidade ──────────────────────────────────────────────────────
    CNPJ_ENTIDADE = CNPJField(
        source_name = "CNPJ ENTIDADE",
        description = "CNPJ da entidade impedida. Chave: convenios, cpdc",
    )
    NOME_ENTIDADE = StringField(
        source_name = "NOME ENTIDADE",
        description = "Nome da entidade impedida",
    )

    # ── Convênio ──────────────────────────────────────────────────────
    NUMERO_CONVENIO = StringField(
        source_name = "NÚMERO CONVÊNIO",
        description = "Número do convênio que motivou o impedimento",
    )

    # ── Órgão ─────────────────────────────────────────────────────────
    ORGAO_CONCEDENTE = StringField(
        source_name = "ÓRGÃO CONCEDENTE",
        description = "Nome do órgão que concedeu o convênio",
    )

    # ── Motivo ────────────────────────────────────────────────────────
    MOTIVO_IMPEDIMENTO = StringField(
        source_name = "MOTIVO DO IMPEDIMENTO",
        description = "Texto livre — candidato a NLP",
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
