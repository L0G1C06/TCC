from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.bolsa_familia_pagamentos import BolsaFamiliaPagamentos
from apps.portal_da_transparencia.models.silver import BolsaFamiliaPagamentosRecord


class Command(BaseImportCommand):
    help = "Importa N registros de Bolsa Família - Pagamentos (S3) para o banco Django"

    duckdb_model = BolsaFamiliaPagamentos
    django_model = BolsaFamiliaPagamentosRecord
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
        "VALOR PARCELA":                            "valor_parcela",
    }
