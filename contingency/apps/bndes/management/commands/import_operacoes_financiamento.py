from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.bndes.models.operacoes_financiamento import OperacoesFinanciamento
from apps.bndes.models.silver import OperacoesFinanciamentoRecord


class Command(BaseImportCommand):
    help = "Importa N registros de Operações de Financiamento BNDES (S3) para o banco Django"

    duckdb_model = OperacoesFinanciamento
    django_model = OperacoesFinanciamentoRecord
    default_ano  = None
    default_mes  = None

    field_map = {
        "cliente":                                      "cliente",
        "cpf_cnpj":                                     "cpf_cnpj",
        "cnpj":                                         "cnpj",
        "porte_do_cliente":                             "porte_do_cliente",
        "natureza_do_cliente":                          "natureza_do_cliente",
        "uf":                                           "uf",
        "municipio":                                    "municipio",
        "municipio_codigo":                             "municipio_codigo",
        "data_da_contratacao":                          "data_da_contratacao",
        "situacao_da_operacao":                         "situacao_da_operacao",
        "descricao_do_projeto":                         "descricao_do_projeto",
        "numero_do_contrato":                           "numero_do_contrato",
        "situacao_do_contrato":                         "situacao_do_contrato",
        "tipo_de_garantia":                             "tipo_de_garantia",
        "tipo_de_excepcionalidade":                     "tipo_de_excepcionalidade",
        "area_operacional":                             "area_operacional",
        "modalidade_de_apoio":                          "modalidade_de_apoio",
        "forma_de_apoio":                               "forma_de_apoio",
        "produto":                                      "produto",
        "instrumento_financeiro":                       "instrumento_financeiro",
        "inovacao":                                     "inovacao",
        "fonte_de_recurso_desembolsos":                 "fonte_de_recurso_desembolsos",
        "custo_financeiro":                             "custo_financeiro",
        "setor_cnae":                                   "setor_cnae",
        "subsetor_cnae_agrupado":                       "subsetor_cnae_agrupado",
        "subsetor_cnae_codigo":                         "subsetor_cnae_codigo",
        "subsetor_cnae_nome":                           "subsetor_cnae_nome",
        "setor_bndes":                                  "setor_bndes",
        "subsetor_bndes":                               "subsetor_bndes",
        "instituicao_financeira_credenciada":           "instituicao_financeira_credenciada",
        "cnpj_do_agente_financeiro":                    "cnpj_do_agente_financeiro",
        "cnpj_da_instituicao_financeira_credenciada":   "cnpj_da_instituicao_financeira_credenciada",
        "valor_da_operacao_em_reais":                   "valor_da_operacao_em_reais",
        "valor_contratado_reais":                       "valor_contratado_reais",
        "valor_desembolsado_reais":                     "valor_desembolsado_reais",
        "juros":                                        "juros",
        "prazo_carencia_meses":                         "prazo_carencia_meses",
        "prazo_amortizacao_meses":                      "prazo_amortizacao_meses",
    }
