from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.bolsa_familia_saques import BolsaFamiliaSaques
from apps.portal_da_transparencia.models.silver import BolsaFamiliaSaquesRecord


class Command(BaseImportCommand):
    help = "Importa N registros de Bolsa Família - Saques (S3) para o banco Django"

    duckdb_model = BolsaFamiliaSaques
    django_model = BolsaFamiliaSaquesRecord
    default_ano  = "2020"
    default_mes  = "03"

    field_map = {
        "MÊS COMPETÊNCIA":                          "mes_competencia",
        "MÊS REFERÊNCIA":                           "mes_referencia",
        "UF":                                       "uf",
        "CÓDIGO MUNICÍPIO SIAFI":                   "codigo_municipio_siafi",
        "NOME MUNICÍPIO":                           "nome_municipio",
        "CPF FAVORECIDO":                           "cpf_favorecido",
        "NIS FAVORECIDO":                           "nis_favorecido",
        "NOME FAVORECIDO":                          "nome_favorecido",
        "DATA SAQUE":                               "data_saque",
        "VALOR PARCELA":                            "valor_parcela",
    }
