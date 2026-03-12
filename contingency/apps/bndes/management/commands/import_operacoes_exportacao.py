from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.bndes.models.operacoes_exportacao import OperacoesExportacao
from apps.bndes.models.silver import OperacoesExportacaoRecord


class Command(BaseImportCommand):
    help = "Importa N registros de Operações de Exportação BNDES (S3) para o banco Django"

    duckdb_model = OperacoesExportacao
    django_model = OperacoesExportacaoRecord
    default_ano  = None
    default_mes  = None

    field_map = {
        "exportador":                                   "exportador",
        "cnpj_do_exportador":                           "cnpj_do_exportador",
        "porte_do_exportador":                          "porte_do_exportador",
        "pais_destino_das_exportacoes":                 "pais_destino_das_exportacoes",
        "cliente":                                      "cliente",
        "cpf_cnpj":                                     "cpf_cnpj",
        "porte_do_cliente":                             "porte_do_cliente",
        "natureza_do_cliente":                          "natureza_do_cliente",
        "uf":                                           "uf",
        "municipio":                                    "municipio",
        "municipio_codigo":                             "municipio_codigo",
        "numero_da_operacao":                           "numero_da_operacao",
        "descricao_da_operacao":                        "descricao_da_operacao",
        "data_da_contratacao":                          "data_da_contratacao",
        "situacao_da_operacao":                         "situacao_da_operacao",
        "tipo_de_garantia":                             "tipo_de_garantia",
        "categoria":                                    "categoria",
        "area_operacional":                             "area_operacional",
        "modalidade_de_apoio":                          "modalidade_de_apoio",
        "forma_de_apoio":                               "forma_de_apoio",
        "produto":                                      "produto",
        "modalidade_operacional":                       "modalidade_operacional",
        "instrumento_financeiro":                       "instrumento_financeiro",
        "inovacao":                                     "inovacao",
        "setor_subsetor_de_atividade":                  "setor_subsetor_de_atividade",
        "setor_cnae":                                   "setor_cnae",
        "subsetor_cnae_agrupado":                       "subsetor_cnae_agrupado",
        "subsetor_cnae_codigo":                         "subsetor_cnae_codigo",
        "subsetor_cnae_nome":                           "subsetor_cnae_nome",
        "setor_bndes":                                  "setor_bndes",
        "subsetor_bndes":                               "subsetor_bndes",
        "instituicao_financeira_credenciada":           "instituicao_financeira_credenciada",
        "cnpj_do_agente_financeiro":                    "cnpj_do_agente_financeiro",
        "moeda_sigla":                                  "moeda_sigla",
        "fonte_de_recursos_desembolsos":                "fonte_de_recursos_desembolsos",
        "fonte_de_recurso_desembolsos":                 "fonte_de_recurso_desembolsos",
        "custo_financeiro":                             "custo_financeiro",
        "mutuario":                                     "mutuario",
        "valor_da_operacao_em_um":                      "valor_da_operacao_em_um",
        "valor_desembolsado_em_um":                     "valor_desembolsado_em_um",
        "valor_da_operacao_em_reais":                   "valor_da_operacao_em_reais",
        "valor_desembolsado_em_reais":                  "valor_desembolsado_em_reais",
        "juros":                                        "juros",
        "prazo_total_meses":                            "prazo_total_meses",
    }
