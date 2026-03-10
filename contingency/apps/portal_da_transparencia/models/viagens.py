# apps/portal_da_transparencia/models/viagens.py
"""
Viagens a Serviço e Diárias — Poder Executivo Federal

Fonte    : Portal da Transparência — CGU
S3       : portal_da_transparencia/parquet/modulo=viagens/
Histórico: 2011 → 2024  |  ~4 arquivos/ano  |  mes=unknown (publicação anual)

⚠️  Anos faltando no S3: 2018, 2019, 2021 — ausência real no Portal.
⚠️  Código do órgão superior e Codigo do órgão pagador chegam como DOUBLE
    — provável artifact de anos antigos onde o campo era numérico.
    Silver: converter para VARCHAR com zero-fill.

Cada linha representa um pagamento/trecho dentro de um processo de viagem (PCDP).
A granularidade é pagamento × trecho × viajante × proposta.

Chaves de correlação:
    CPF viajante                    → servidores.CPF, pep.CPF, cpgf.'CPF PORTADOR'
    Número da Proposta (PCDP)       → identificador único do processo no SCDP
    Identificador do processo       → chave interna entre arquivos do mesmo módulo
    Código do órgão superior        → cpgf, cpdc, despesas-execucao, transferencias
    Código da unidade gestora       → compras, licitacoes, cpgf, despesas-execucao
    Código órgão solicitante        → estrutura SIAFI
"""

from apps.datalake.orm.fields import (
    CPFField,
    CodigoOrgaoSuperiorField,
    CodigoUGField,
    UFField,
    DateVarcharField,
    MoneyField,
    BigIntField,
    FloatField,
    StringField,
    CargoField,
    FuncaoConfiancaField,
    PCDPField,
    JustificativaField,
    PartitionAnoField,
    PartitionMesField,
    PartitionModuloField,
)
from apps.datalake.orm.model import DuckDBModel


class Viagens(DuckDBModel):
    """
    Viagens a serviço e diárias — camada Bronze.
    Espelho fiel do parquet no S3. Nenhuma transformação aplicada.

    ⚠️  Dataset anual — partição mes=unknown em todos os anos.
        Não filtrar por mes ao fazer scan.
    ⚠️  Schema consolidado de múltiplos arquivos por ano (union_by_name).
        Campos ausentes em anos mais antigos serão nulos.

    Uso:
        Viagens.scan(ano="2024").fetchdf()
    """

    dataset_path = "portal_da_transparencia/parquet/"
    modulo       = "viagens"

    # ── Identificação do processo ─────────────────────────────────────
    IDENTIFICADOR_PROCESSO_VIAGEM = BigIntField(
        source_name = "Identificador do processo de viagem",
        description = "Chave interna do processo entre arquivos do mesmo módulo",
        is_join_key = True,
    )
    NUMERO_PROPOSTA_PCDP = PCDPField(
        source_name = "Número da Proposta (PCDP)",
        description = "Identificador único do processo no SCDP. Chave principal do módulo.",
    )
    SITUACAO = StringField(
        source_name = "Situação",
        description = "Ex: Realizada, Cancelada, Em andamento",
    )
    VIAGEM_URGENTE = StringField(
        source_name = "Viagem Urgente",
        description = "Silver: normalizar para Boolean",
    )
    JUSTIFICATIVA_URGENCIA = JustificativaField(
        source_name = "Justificativa Urgência Viagem",
        nullable    = True,
    )
    MISSAO = StringField(
        source_name  = "Missao?",
        description  = "⚠️ Nome do campo inclui '?' — nome exato do S3. Silver: renomear.",
        nullable     = True,
    )

    # ── Órgão superior ────────────────────────────────────────────────
    CODIGO_ORGAO_SUPERIOR = FloatField(
        source_name = "Código do órgão superior",
        description = (
            "⚠️ DOUBLE no S3 — artifact de ingestão de anos antigos. "
            "Silver: converter para VARCHAR com zero-fill (ex: 26000.0 → '26000'). "
            "Chave: cpgf, cpdc, despesas-execucao, transferencias"
        ),
    )
    NOME_ORGAO_SUPERIOR = StringField(
        source_name = "Nome do órgão superior",
    )

    # ── Órgão pagador ─────────────────────────────────────────────────
    CODIGO_ORGAO_PAGADOR = FloatField(
        source_name = "Codigo do órgão pagador",
        description = (
            "⚠️ DOUBLE no S3 — mesma situação do órgão superior. "
            "⚠️ Grafia 'Codigo' sem acento — nome exato do S3."
        ),
    )
    NOME_ORGAO_PAGADOR = StringField(
        source_name = "Nome do órgao pagador",
        description = "⚠️ Grafia 'órgao' sem til — nome exato do S3.",
    )
    CODIGO_UG_PAGADORA = BigIntField(
        source_name = "Código da unidade gestora pagadora",
        description = (
            "BIGINT no S3. Silver: converter para VARCHAR com zero-fill. "
            "Chave: compras, licitacoes, cpgf, despesas-execucao"
        ),
    )
    NOME_UG_PAGADORA = StringField(
        source_name = "Nome da unidade gestora pagadora",
    )

    # ── Órgão solicitante ─────────────────────────────────────────────
    CODIGO_ORGAO_SOLICITANTE = BigIntField(
        source_name = "Código órgão solicitante",
        description = "BIGINT no S3. Silver: converter para VARCHAR com zero-fill.",
    )
    NOME_ORGAO_SOLICITANTE = StringField(
        source_name = "Nome órgão solicitante",
    )

    # ── Viajante ──────────────────────────────────────────────────────
    CPF_VIAJANTE = CPFField(
        source_name = "CPF viajante",
        description = (
            "CPF do servidor viajante. "
            "Chave: servidores.CPF, pep.CPF, cpgf.'CPF PORTADOR'"
        ),
    )
    NOME_VIAJANTE = StringField(
        source_name = "Nome",
    )
    CARGO = CargoField(
        source_name = "Cargo",
        nullable    = True,
    )
    FUNCAO = FuncaoConfiancaField(
        source_name = "Função",
        nullable    = True,
    )
    DESCRICAO_FUNCAO = StringField(
        source_name = "Descrição Função",
        nullable    = True,
    )

    # ── Período e destinos (nível proposta) ───────────────────────────
    PERIODO_DATA_INICIO = DateVarcharField(
        source_name = "Período - Data de início",
        description = "Data de início da viagem. Silver: normalizar para Date.",
    )
    PERIODO_DATA_FIM = DateVarcharField(
        source_name = "Período - Data de fim",
        description = "Data de fim da viagem. Silver: normalizar para Date.",
    )
    DESTINOS = StringField(
        source_name = "Destinos",
        description = "Texto livre com destinos da viagem — candidato a NLP",
        nullable    = True,
    )
    MOTIVO = StringField(
        source_name = "Motivo",
        description = "Justificativa da viagem — texto livre",
        nullable    = True,
    )

    # ── Pagamento ─────────────────────────────────────────────────────
    TIPO_DE_PAGAMENTO = StringField(
        source_name = "Tipo de pagamento",
        description = "Ex: Diária, Passagem, Outros",
    )
    VALOR = MoneyField(
        source_name = "Valor",
        description = "Valor do pagamento — VARCHAR. Silver → Decimal(15,2)",
    )

    # ── Valores consolidados (nível proposta) ─────────────────────────
    VALOR_DIARIAS = MoneyField(
        source_name = "Valor diárias",
        description = "Total de diárias da proposta",
        nullable    = True,
    )
    VALOR_PASSAGENS = MoneyField(
        source_name = "Valor passagens",
        nullable    = True,
    )
    VALOR_DEVOLUCAO = MoneyField(
        source_name = "Valor devolução",
        description = "Valor devolvido ao erário — pode ser negativo",
        nullable    = True,
    )
    VALOR_OUTROS_GASTOS = MoneyField(
        source_name = "Valor outros gastos",
        nullable    = True,
    )
    NUMERO_DIARIAS = StringField(
        source_name = "Número Diárias",
        description = "Quantidade de diárias — VARCHAR. Silver: normalizar para Decimal.",
        nullable    = True,
    )

    # ── Passagem: dados de emissão ────────────────────────────────────
    MEIO_DE_TRANSPORTE = StringField(
        source_name = "Meio de transporte",
        description = "Ex: Aéreo, Rodoviário, Ferroviário",
        nullable    = True,
    )
    VALOR_DA_PASSAGEM = MoneyField(
        source_name = "Valor da passagem",
        nullable    = True,
    )
    TAXA_DE_SERVICO = MoneyField(
        source_name = "Taxa de serviço",
        nullable    = True,
    )
    DATA_EMISSAO_COMPRA = DateVarcharField(
        source_name = "Data da emissão/compra",
        nullable    = True,
    )
    HORA_EMISSAO_COMPRA = StringField(
        source_name = "Hora da emissão/compra",
        description = "Hora da emissão — VARCHAR 'HH:MM'. Silver: combinar com data.",
        nullable    = True,
    )
    SEQUENCIA_TRECHO = BigIntField(
        source_name = "Sequência Trecho",
        description = "Ordem do trecho dentro da proposta",
        nullable    = True,
    )

    # ── Passagem: origem/destino agregado ─────────────────────────────
    PAIS_ORIGEM_IDA = StringField(source_name="País - Origem ida", nullable=True)
    UF_ORIGEM_IDA   = UFField(source_name="UF - Origem ida", nullable=True)
    CIDADE_ORIGEM_IDA = StringField(source_name="Cidade - Origem ida", nullable=True)

    PAIS_DESTINO_IDA = StringField(source_name="País - Destino ida", nullable=True)
    UF_DESTINO_IDA   = UFField(source_name="UF - Destino ida", nullable=True)
    CIDADE_DESTINO_IDA = StringField(source_name="Cidade - Destino ida", nullable=True)

    PAIS_ORIGEM_VOLTA = StringField(source_name="País - Origem volta", nullable=True)
    UF_ORIGEM_VOLTA   = UFField(source_name="UF - Origem volta", nullable=True)
    CIDADE_ORIGEM_VOLTA = StringField(source_name="Cidade - Origem volta", nullable=True)

    PAIS_DESTINO_VOLTA = StringField(
        source_name = "Pais - Destino volta",
        description = "⚠️ Grafia 'Pais' sem acento — nome exato do S3.",
        nullable    = True,
    )
    UF_DESTINO_VOLTA   = UFField(source_name="UF - Destino volta", nullable=True)
    CIDADE_DESTINO_VOLTA = StringField(source_name="Cidade - Destino volta", nullable=True)

    # ── Passagem: trecho detalhado ────────────────────────────────────
    ORIGEM_DATA   = DateVarcharField(source_name="Origem - Data", nullable=True)
    ORIGEM_PAIS   = StringField(source_name="Origem - País", nullable=True)
    ORIGEM_UF     = UFField(source_name="Origem - UF", nullable=True)
    ORIGEM_CIDADE = StringField(source_name="Origem - Cidade", nullable=True)

    DESTINO_DATA   = DateVarcharField(source_name="Destino - Data", nullable=True)
    DESTINO_PAIS   = StringField(source_name="Destino - País", nullable=True)
    DESTINO_UF     = UFField(source_name="Destino - UF", nullable=True)
    DESTINO_CIDADE = StringField(source_name="Destino - Cidade", nullable=True)

    # ── Partições Hive ────────────────────────────────────────────────
    partition_ano    = PartitionAnoField()
    partition_mes    = PartitionMesField()   # sempre 'unknown' neste módulo
    partition_modulo = PartitionModuloField()