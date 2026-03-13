from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.pgd_contratos import PGDContratos
from apps.portal_da_transparencia.models.silver import PGDContratosRecord


class Command(BaseImportCommand):
    help = "Importa N registros de PGD - Contratos (S3) para o banco Django"

    duckdb_model = PGDContratos
    django_model = PGDContratosRecord
    default_ano  = "2022"
    default_mes  = "05"

    field_map = {
        "Código Órgão Superior":                   "codigo_orgao_superior",
        "Órgão Superior":                           "orgao_superior",
        "Código Órgão":                            "codigo_orgao",
        "Órgão":                                    "orgao",
        "Código Unidade Gestora":                  "codigo_unidade_gestora",
        "Unidade Gestora":                          "unidade_gestora",
        "Número Contrato":                          "numero_contrato",
        "Número Processo":                          "numero_processo",
        "CNPJ Fornecedor":                          "cnpj_fornecedor",
        "NOME Fornecedor":                          "nome_fornecedor",
        "Objeto Contrato":                          "objeto_contrato",
        "Valor Inicial":                            "valor_inicial",
        "Valor Final":                              "valor_final",
        "Data Assinatura":                          "data_assinatura",
        "Data Publicação":                          "data_publicacao",
        "Data Início Vigência":                    "data_inicio_vigencia",
        "Data Fim Vigência":                       "data_fim_vigencia",
        "Situação Contrato":                        "situacao_contrato",
    }
