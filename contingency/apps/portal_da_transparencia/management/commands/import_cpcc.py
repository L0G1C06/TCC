from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.cpcc import CPCC
from apps.portal_da_transparencia.models.silver import CPCCRecord


class Command(BaseImportCommand):
    help = "Importa N registros de CPC-C (S3) para o banco Django"

    duckdb_model = CPCC
    django_model = CPCCRecord
    default_ano  = "2022"
    default_mes  = "05"

    field_map = {
        "CÓDIGO ÓRGÃO SUPERIOR":                   "codigo_orgao_superior",
        "NOME ÓRGÃO SUPERIOR":                     "nome_orgao_superior",
        "CÓDIGO ÓRGÃO":                            "codigo_orgao",
        "NOME ÓRGÃO":                              "nome_orgao",
        "CÓDIGO UNIDADE GESTORA":                  "codigo_unidade_gestora",
        "NOME UNIDADE GESTORA":                    "nome_unidade_gestora",
        "ANO EXTRATO":                             "ano_extrato",
        "MÊS EXTRATO":                             "mes_extrato",
        "TIPO AQUISIÇÃO":                          "tipo_aquisicao",
        "CNPJ OU CPF FAVORECIDO":                  "cnpj_ou_cpf_favorecido",
        "NOME FAVORECIDO":                         "nome_favorecido",
        "TRANSAÇÃO":                               "transacao",
        "DATA TRANSAÇÃO":                          "data_transacao",
        "VALOR TRANSAÇÃO":                         "valor_transacao",
    }
