from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.cpgf import CPGF
from apps.portal_da_transparencia.models.silver import CPGFRecord


class Command(BaseImportCommand):
    help = "Importa N registros do CPGF (S3) para o banco Django"

    duckdb_model = CPGF
    django_model = CPGFRecord
    default_ano  = "2024"
    default_mes  = "01"

    field_map = {
        "CÓDIGO ÓRGÃO SUPERIOR":    "codigo_orgao_superior",
        "NOME ÓRGÃO SUPERIOR":      "nome_orgao_superior",
        "CÓDIGO ÓRGÃO":             "codigo_orgao",
        "NOME ÓRGÃO":               "nome_orgao",
        "CÓDIGO UNIDADE GESTORA":   "codigo_unidade_gestora",
        "NOME UNIDADE GESTORA":     "nome_unidade_gestora",
        "ANO EXTRATO":              "ano_extrato",
        "MÊS EXTRATO":              "mes_extrato",
        "CPF PORTADOR":             "cpf_portador",
        "NOME PORTADOR":            "nome_portador",
        "CNPJ OU CPF FAVORECIDO":   "cnpj_ou_cpf_favorecido",
        "NOME FAVORECIDO":          "nome_favorecido",
        "TRANSAÇÃO":                "transacao",
        "DATA TRANSAÇÃO":           "data_transacao",
        "VALOR TRANSAÇÃO":          "valor_transacao",
    }