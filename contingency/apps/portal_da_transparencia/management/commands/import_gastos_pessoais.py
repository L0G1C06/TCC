from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.gastos_pessoais import GastosPessoais
from apps.portal_da_transparencia.models.silver import GastosPessoaisRecord


class Command(BaseImportCommand):
    help = "Importa N registros de Gastos Pessoais (S3) para o banco Django"

    duckdb_model = GastosPessoais
    django_model = GastosPessoaisRecord
    default_ano  = "2022"
    default_mes  = "05"

    field_map = {
        "Código Órgão Superior":                   "codigo_orgao_superior",
        "Órgão Superior":                           "orgao_superior",
        "Código Órgão":                            "codigo_orgao",
        "Órgão":                                    "orgao",
        "Código Unidade Gestora":                  "codigo_unidade_gestora",
        "Unidade Gestora":                          "unidade_gestora",
        "CPF viajante":                             "cpf_viajante",
        "Nome viajante":                            "nome_viajante",
        "Cargo":                                    "cargo",
        "Tipo Despesa":                             "tipo_despesa",
        "Descrição Despesa":                        "descricao_despesa",
        "Data Despesa":                             "data_despesa",
        "Valor Despesa":                            "valor_despesa",
    }
