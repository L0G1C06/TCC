from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.bpc import BPC
from apps.portal_da_transparencia.models.silver import BPCRecord


class Command(BaseImportCommand):
    help = "Importa N registros de BPC (S3) para o banco Django"

    duckdb_model = BPC
    django_model = BPCRecord
    default_ano  = "2022"
    default_mes  = "03"

    field_map = {
        "MÊS COMPETÊNCIA":                          "mes_competencia",
        "MÊS REFERÊNCIA":                           "mes_referencia",
        "UF":                                       "uf",
        "CÓDIGO MUNICÍPIO SIAFI":                   "codigo_municipio_siafi",
        "NOME MUNICÍPIO":                           "nome_municipio",
        "NIS BENEFICIÁRIO":                         "nis_beneficiario",
        "CPF BENEFICIÁRIO":                         "cpf_beneficiario",
        "NOME BENEFICIÁRIO":                        "nome_beneficiario",
        "NIS REPRESENTANTE LEGAL":                  "nis_representante_legal",
        "CPF REPRESENTANTE LEGAL":                  "cpf_representante_legal",
        "NOME REPRESENTANTE LEGAL":                 "nome_representante_legal",
        "NÚMERO BENEFÍCIO":                         "numero_beneficio",
        "BENEFÍCIO CONCEDIDO JUDICIALMENTE":        "beneficio_judicial",
        "VALOR PARCELA":                            "valor_parcela",
    }
