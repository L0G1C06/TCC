"""Static configuration for each Portal da Transparência module.

NOTE ON TYPES: All columns in the parquet files are stored as VARCHAR,
including monetary and quantity fields. The numeric_columns list contains
columns whose *content* is numeric — conversion is handled downstream
by check_benford_eligibility.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModuleConfig:
    name: str
    numeric_columns: list[str]
    description: str = ""
    skip_truncation_check: bool = False
    min_samples: int = 500


# fmt: off
MODULE_CONFIGS: dict[str, ModuleConfig] = {

    # ── Transferências sociais (padrão: VALOR PARCELA) ────────────────────────

    "auxilio-brasil": ModuleConfig(
        name="auxilio-brasil",
        numeric_columns=["VALOR PARCELA"],
        description="Auxílio Brasil — pagamentos mensais por beneficiário",
        skip_truncation_check=True,
    ),
    "auxilio-emergencial": ModuleConfig(
        name="auxilio-emergencial",
        numeric_columns=["VALOR BENEFÍCIO"],
        description="Auxílio Emergencial COVID-19",
        skip_truncation_check=True,
    ),
    "auxilio-reconstrucao": ModuleConfig(
        name="auxilio-reconstrucao",
        numeric_columns=["VALOR PARCELA"],
        description="Auxílio Reconstrução — desastres naturais",
        skip_truncation_check=True,
    ),
    "bolsa-familia-pagamentos": ModuleConfig(
        name="bolsa-familia-pagamentos",
        numeric_columns=["VALOR PARCELA"],
        description="Bolsa Família — pagamentos mensais",
        skip_truncation_check=True,
    ),
    "bolsa-familia-saques": ModuleConfig(
        name="bolsa-familia-saques",
        numeric_columns=["VALOR PARCELA"],
        description="Bolsa Família — saques realizados",
        skip_truncation_check=True,
    ),
    "bpc": ModuleConfig(
        name="bpc",
        numeric_columns=["VALOR PARCELA"],
        description="Benefício de Prestação Continuada",
        skip_truncation_check=True,
    ),
    "garantia-safra": ModuleConfig(
        name="garantia-safra",
        numeric_columns=["VALOR PARCELA"],
        description="Garantia Safra — agricultores familiares",
        skip_truncation_check=True,
    ),
    "novo-bolsa-familia": ModuleConfig(
        name="novo-bolsa-familia",
        numeric_columns=["VALOR PARCELA"],
        description="Novo Bolsa Família (a partir de 2023)",
        skip_truncation_check=True,
    ),
    "pe-de-meia": ModuleConfig(
        name="pe-de-meia",
        numeric_columns=["VALOR PARCELA"],
        description="Pé-de-Meia — poupança estudantil",
        skip_truncation_check=True,  # valor fixo por etapa de ensino
    ),
    "peti": ModuleConfig(
        name="peti",
        numeric_columns=["VALOR PARCELA"],
        description="Programa de Erradicação do Trabalho Infantil",
        skip_truncation_check=True,  # valor fixo por criança
    ),
    "seguro-defeso": ModuleConfig(
        name="seguro-defeso",
        numeric_columns=["VALOR PARCELA"],
        description="Seguro Defeso — pescadores artesanais",
        skip_truncation_check=True,  # valor fixo por período de defeso
    ),

    # ── Compras e contratos ───────────────────────────────────────────────────

    "compras": ModuleConfig(
        name="compras",
        numeric_columns=[
            "Quantidade Item",
            "Valor Item",
            "Valor Inicial Compra",
            "Valor Final Compra",
        ],
        description="Contratos e itens de compras públicas",
    ),
    "licitacoes": ModuleConfig(
        name="licitacoes",
        numeric_columns=[
            "Valor Licitação",
            "Valor Empenho (R$)",
            "Quantidade Item",
            "Valor Item",
        ],
        description="Licitações — itens e empenhos",
    ),
    "notas-fiscais": ModuleConfig(
        name="notas-fiscais",
        numeric_columns=[
            "VALOR NOTA FISCAL",
            "QUANTIDADE",
            "VALOR UNITÁRIO",
            "VALOR TOTAL",
        ],
        description="Notas fiscais eletrônicas emitidas para órgãos federais",
    ),

    # ── Despesas ──────────────────────────────────────────────────────────────

    "despesas": ModuleConfig(
        name="despesas",
        numeric_columns=[
            # --- Pagamento (22–25 arquivos) ---
            "Valor Pago (R$)",

            # --- Liquidação (30 arquivos) ---
            "Valor Liquidado (R$)",

            # --- Restos a Pagar (52 arquivos) ---
            "Valor Restos a Pagar Inscritos (R$)",
            "Valor Restos a Pagar Cancelado (R$)",
            "Valor Restos a Pagar Pagos (R$)",

            # --- Empenho (29 arquivos) ---
            "Valor Original do Empenho",
            "Valor Atual",
            "Valor Total",

            # --- Itens de empenho (29 arquivos) ---
            "Quantidade Item",
            "Valor Unitário Item",
            "Valor Total Item",

            # --- Conversão cambial (29–32 arquivos) ---
            "Valor Utilizado na Conversão",
            "Valor do Empenho Convertido pra R$",
        ],
        description="Execução de despesas — empenho, liquidação, pagamento e restos a pagar",
    ),
    "despesas-execucao": ModuleConfig(
        name="despesas-execucao",
        numeric_columns=[
            "Valor Empenhado (R$)",
            "Valor Liquidado (R$)",
            "Valor Pago (R$)",
            "Valor Restos a Pagar Inscritos (R$)",
            "Valor Restos a Pagar Cancelado (R$)",
            "Valor Restos a Pagar Pagos (R$)",
        ],
        description="Execução orçamentária detalhada por ação/programa",
    ),
    "despesas-favorecidos": ModuleConfig(
        name="despesas-favorecidos",
        numeric_columns=["Valor Recebido"],
        description="Despesas agrupadas por favorecido",
    ),
    "orcamento-despesa": ModuleConfig(
        name="orcamento-despesa",
        numeric_columns=[
            "ORÇAMENTO INICIAL (R$)",
            "ORÇAMENTO ATUALIZADO (R$)",
            "ORÇAMENTO EMPENHADO (R$)",
            "ORÇAMENTO REALIZADO (R$)",
        ],
        description="Orçamento de despesas — LOA e execução anual",
    ),

    # ── Cartões de pagamento ──────────────────────────────────────────────────

    "cpgf": ModuleConfig(
        name="cpgf",
        numeric_columns=["VALOR TRANSAÇÃO"],
        description="Cartão de Pagamento do Governo Federal",
        skip_truncation_check=True,
    ),
    "cpdc": ModuleConfig(
        name="cpdc",
        numeric_columns=["VALOR TRANSAÇÃO"],
        description="Cartão de Pagamento de Defesa Civil",
        skip_truncation_check=True,
    ),
    "cpcc": ModuleConfig(
        name="cpcc",
        numeric_columns=["VALOR TRANSAÇÃO"],
        description="Cartão de Pagamento de Combustíveis e Lubrificantes",
        skip_truncation_check=True,
    ),

    # ── Transferências e convênios ────────────────────────────────────────────

    "transferencias": ModuleConfig(
        name="transferencias",
        numeric_columns=["VALOR TRANSFERIDO"],
        description="Transferências a estados, municípios e entidades",
    ),
    "convenios": ModuleConfig(
        name="convenios",
        numeric_columns=[
            "VALOR LIBERADO",
            "VALOR CONVÊNIO",
            "VALOR CONTRAPARTIDA",
            "VALOR ÚLTIMA LIBERAÇÃO",
        ],
        description="Convênios federais — liberações e valores",
        skip_truncation_check=True,
    ),

    # ── Emendas parlamentares ─────────────────────────────────────────────────

    "emendas-parlamentares": ModuleConfig(
        name="emendas-parlamentares",
        numeric_columns=[
            "Valor Convênio",
            "Valor Recebido",
            "Valor Empenhado",
            "Valor Liquidado",
            "Valor Pago",
            "Valor Restos A Pagar Inscritos",
            "Valor Restos A Pagar Cancelados",
            "Valor Restos A Pagar Pagos",
        ],
        description="Emendas parlamentares — execução e convênios",
    ),
    "emendas-parlamentares-documentos": ModuleConfig(
        name="emendas-parlamentares-documentos",
        numeric_columns=[
            "Valor Empenhado",
            "Valor Pago",
        ],
        description="Emendas parlamentares — documentos de execução",
    ),
    "apoiamento-emendas-parlamentares-documentos": ModuleConfig(
        name="apoiamento-emendas-parlamentares-documentos",
        numeric_columns=[
            "Valor Empenhado",
            "Valor Cancelado",
            "Valor Pago",
        ],
        description="Apoiamento de emendas parlamentares — documentos",
    ),

    # ── Servidores ────────────────────────────────────────────────────────────

    "servidores": ModuleConfig(
        name="servidores",
        numeric_columns=[
            # Colunas em R$ — as colunas U$ são conversões e distorceriam Benford
            "REMUNERAÇÃO BÁSICA BRUTA (R$)",
            "REMUNERAÇÃO APÓS DEDUÇÕES OBRIGATÓRIAS (R$)",
            "OUTRAS REMUNERAÇÕES EVENTUAIS (R$)",
            "GRATIFICAÇÃO NATALINA (R$)",
            "FÉRIAS (R$)",
            "TOTAL DE VERBAS INDENIZATÓRIAS (R$)(*)",
        ],
        description="Servidores públicos federais — remuneração mensal",
    ),

    # ── Receitas ──────────────────────────────────────────────────────────────

    "receitas": ModuleConfig(
        name="receitas",
        numeric_columns=[
            "VALOR PREVISTO ATUALIZADO",
            "VALOR LANÇADO",
            "VALOR REALIZADO",
        ],
        description="Arrecadação de receitas federais",
    ),

    # ── Renúncias fiscais ─────────────────────────────────────────────────────

    "renuncias": ModuleConfig(
        name="renuncias",
        numeric_columns=["Valor Renúncia Fiscal (R$)"],
        description="Renúncias fiscais por empresa/benefício",
    ),

    # ── Viagens ───────────────────────────────────────────────────────────────

    "viagens": ModuleConfig(
        name="viagens",
        numeric_columns=[
            # Sub-tipo: passagens (1/3 arquivos)
            "Valor da passagem",
            "Taxa de serviço",

            # Sub-tipo: pagamento geral (1/3 arquivos)
            "Valor",

            # Sub-tipo: diárias (1/3 arquivos)
            "Número Diárias",
        ],
        description="Viagens a serviço — diárias, passagens e pagamentos",
    ),

    # ── Sanções (sem colunas numéricas relevantes para Benford) ──────────────

    "acordos-leniencia": ModuleConfig(
        name="acordos-leniencia",
        numeric_columns=[],
        description="Acordos de leniência — sem valores monetários estruturados",
    ),
    "ceaf": ModuleConfig(
        name="ceaf",
        numeric_columns=[],
        description="CEAF — cadastro de servidores afastados",
    ),
    "ceis": ModuleConfig(
        name="ceis",
        numeric_columns=[],
        description="CEIS — cadastro de inidôneos e suspensos",
    ),
    "cepim": ModuleConfig(
        name="cepim",
        numeric_columns=[],
        description="CEPIM — entidades privadas impedidas",
    ),
    "cnep": ModuleConfig(
        name="cnep",
        numeric_columns=["VALOR DA MULTA"],
        description="CNEP — cadastro nacional de empresas punidas",
    ),

    # ── Cadastros (sem colunas numéricas relevantes para Benford) ────────────

    "favorecidos-pj": ModuleConfig(
        name="favorecidos-pj",
        numeric_columns=[],
        description="Cadastro de favorecidos pessoa jurídica — sem valores",
    ),
    "imoveis-funcionais": ModuleConfig(
        name="imoveis-funcionais",
        numeric_columns=[],
        description="Imóveis funcionais — dados cadastrais sem valores",
    ),
    "pep": ModuleConfig(
        name="pep",
        numeric_columns=[],
        description="Pessoas Expostas Politicamente — sem valores monetários",
    ),
}


def get_module_config(module_path: str) -> ModuleConfig:
    """
    Resolve module config from a path or plain name.

    Args:
        module_path: e.g. '/data/parquet/modulo=compras', 'modulo=compras', or 'compras'

    Raises:
        ValueError: if module is not registered in MODULE_CONFIGS
    """
    path_str = str(module_path)
    for key in MODULE_CONFIGS:
        if f"modulo={key}" in path_str or path_str.endswith(key):
            return MODULE_CONFIGS[key]

    registered = sorted(MODULE_CONFIGS.keys())
    raise ValueError(
        f"No config found for '{module_path}'.\n"
        f"Registered modules ({len(registered)}): {registered}"
    )
