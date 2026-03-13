# apps/portal_da_transparencia/models/cnep.py
"""
CNEP — Cadastro Nacional de Empresas Penas

Fonte    : Portal da Transparência — CGU / SENEP
S3       : portal_da_transparencia/parquet/modulo=cnep/
Histórico: snapshot único (ano=2026/mes=03 — 1 arquivo)

Empresas e pessoas físicas que foram sancionadas com multas por
irregularidades em contratos com a Administração Pública Federal.

Chaves de correlação:
    CPF OU CNPJ DO SANCIONADO → ceis.CPF OU CNPJ DO SANCIONADO,
                                 licitacoes.Código Participante,
                                 favorecidos-pj, cpgf
    NÚMERO DO PROCESSO        → ceis.NÚMERO DO PROCESSO,
                                 licitacoes.Número Processo
"""

from apps.datalake.orm.fields import (
    CPFCNPJField,
    UFField,
    DateVarcharField,
    CodigoSancaoField,
    TipoPessoaField,
    EsferaOrgaoField,
    FundamentacaoLegalField,
    NumeroProcessoField,
    MoneyField,
    StringField,
    BigIntField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class CNEP(DuckDBModel):
    """
    Cadastro Nacional de Empresas Penas — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    ⚠️  Snapshot — não usar partição como dimensão temporal da sanção.
        Usar DATA INÍCIO SANÇÃO / DATA FINAL SANÇÃO para vigência.

    Uso:
        CNEP.scan(ano="2026", mes="03").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "cnep"

    # ── Cadastro ──────────────────────────────────────────────────────
    CADASTRO = StringField(
        source_name = "CADASTRO",
        description = "Nome do cadastro de origem da sanção (ex: CNEP, CEIS)",
    )

    # ── Sanção ────────────────────────────────────────────────────────
    CODIGO_SANCAO = CodigoSancaoField(
        source_name = "CÓDIGO DA SANÇÃO",
    )
    TIPO_PESSOA = TipoPessoaField(
        source_name = "TIPO DE PESSOA",
        description = "F=Física, J=Jurídica. Silver: guia separação CPF/CNPJ",
    )
    CPF_OU_CNPJ_DO_SANCIONADO = CPFCNPJField(
        source_name = "CPF OU CNPJ DO SANCIONADO",
        description = (
            "CPF (11) ou CNPJ (14) do sancionado. "
            "Silver: separar por TIPO DE PESSOA. "
            "Chave: licitacoes.Código Participante, favorecidos-pj, servidores"
        ),
    )
    NOME_DO_SANCIONADO = StringField(
        source_name = "NOME DO SANCIONADO",
    )
    NOME_INFORMADO_ORGAO = StringField(
        source_name = "NOME INFORMADO PELO ÓRGÃO SANCIONADOR",
        description  = "Nome conforme cadastrado pelo órgão — pode divergir do nome oficial",
    )
    RAZAO_SOCIAL_RECEITA = StringField(
        source_name = "RAZÃO SOCIAL - CADASTRO RECEITA",
        description  = "Razão social conforme Receita Federal — nulo para PF",
        nullable     = True,
    )
    NOME_FANTASIA_RECEITA = StringField(
        source_name = "NOME FANTASIA - CADASTRO RECEITA",
        nullable    = True,
    )

    # ── Processo ──────────────────────────────────────────────────────
    NUMERO_PROCESSO = NumeroProcessoField(
        source_name = "NÚMERO DO PROCESSO",
        description = "Processo administrativo da sanção. Chave: ceis, licitacoes",
    )

    # ── Categoria ─────────────────────────────────────────────────────
    CATEGORIA_SANCAO = StringField(
        source_name = "CATEGORIA DA SANÇÃO",
        description = "Ex: Inidoneidade, Suspensão, Impedimento",
    )

    # ── Valor ─────────────────────────────────────────────────────────
    VALOR_MULTA = MoneyField(
        source_name = "VALOR DA MULTA",
        description = "Valor da multa aplicada — VARCHAR '1.234,56'. Silver → Decimal(15,2)",
    )

    # ── Datas ─────────────────────────────────────────────────────────
    DATA_INICIO_SANCAO = DateVarcharField(
        source_name = "DATA INÍCIO SANÇÃO",
        description = "Silver: normalizar para Date — início da vigência da sanção",
    )
    DATA_FINAL_SANCAO = DateVarcharField(
        source_name = "DATA FINAL SANÇÃO",
        description = "Nulo = sanção por prazo indeterminado",
        nullable    = True,
    )
    DATA_PUBLICACAO = DateVarcharField(
        source_name = "DATA PUBLICAÇÃO",
    )
    DATA_TRANSITO_EM_JULGADO = DateVarcharField(
        source_name = "DATA DO TRÂNSITO EM JULGADO",
        nullable    = True,
    )
    DATA_ORIGEM_INFORMACAO = DateVarcharField(
        source_name = "DATA ORIGEM INFORMAÇÃO",
    )

    # ── Publicação ────────────────────────────────────────────────────
    PUBLICACAO = StringField(
        source_name = "PUBLICAÇÃO",
        description = "Veículo de publicação (ex: DOU, DOE)",
    )
    DETALHAMENTO_MEIO_PUBLICACAO = StringField(
        source_name = "DETALHAMENTO DO MEIO DE PUBLICAÇÃO",
        nullable    = True,
    )

    # ── Abrangência ───────────────────────────────────────────────────
    ABRAGENCIA_SANCAO = StringField(
        source_name = "ABRAGÊNCIA DA SANÇÃO",
        description = "⚠️ Grafia 'ABRAGÊNCIA' (sem N) — nome exato do campo no S3",
    )

    # ── Órgão Sancionador ─────────────────────────────────────────────
    ORGAO_SANCIONADOR = StringField(
        source_name = "ÓRGÃO SANCIONADOR",
        description = "Nome do órgão que aplicou a sanção — texto livre",
    )
    UF_ORGAO_SANCIONADOR = UFField(
        source_name = "UF ÓRGÃO SANCIONADOR",
    )
    ESFERA_ORGAO_SANCIONADOR = EsferaOrgaoField(
        source_name = "ESFERA ÓRGÃO SANCIONADOR",
        description = "Federal, Estadual ou Municipal",
    )

    # ── Complemento ───────────────────────────────────────────────────
    FUNDAMENTACAO_LEGAL = FundamentacaoLegalField(
        source_name = "FUNDAMENTAÇÃO LEGAL",
    )
    ORIGEM_INFORMACOES = StringField(
        source_name = "ORIGEM INFORMAÇÕES",
    )
    OBSERVACOES = StringField(
        source_name = "OBSERVAÇÕES",
        description = "Texto livre — candidato a NLP",
        nullable    = True,
    )

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()
    partition_modulo = PartitionModuloField()
