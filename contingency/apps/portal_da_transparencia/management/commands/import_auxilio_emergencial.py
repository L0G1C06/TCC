from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.auxilio_emergencial import AuxilioEmergencial
from apps.portal_da_transparencia.models.silver import AuxilioEmergencialRecord


class Command(BaseImportCommand):
    help = "Importa N registros de Auxílio Emergencial (S3) para o banco Django"

    duckdb_model = AuxilioEmergencial
    django_model = AuxilioEmergencialRecord
    default_ano  = "2020"
    default_mes  = "04"

    field_map = {
        "MÊS DISPONIBILIZAÇÃO":                     "mes_disponibilizacao",
        "UF":                                       "uf",
        "CÓDIGO MUNICÍPIO IBGE":                    "codigo_municipio_ibge",
        "NOME MUNICÍPIO":                           "nome_municipio",
        "NIS BENEFICIÁRIO":                         "nis_beneficiario",
        "CPF BENEFICIÁRIO":                         "cpf_beneficiario",
        "NOME BENEFICIÁRIO":                        "nome_beneficiario",
        "NIS RESPONSÁVEL":                          "nis_responsavel",
        "CPF RESPONSÁVEL":                          "cpf_responsavel",
        "NOME RESPONSÁVEL":                         "nome_responsavel",
        "ENQUADRAMENTO":                            "enquadramento",
        "PARCELA":                                  "parcela",
        "OBSERVAÇÃO":                               "observacao",
        "VALOR BENEFÍCIO":                          "valor_beneficio",
    }
