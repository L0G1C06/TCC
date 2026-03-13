from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.cepim import CEPIM
from apps.portal_da_transparencia.models.silver import CEPIMRecord


class Command(BaseImportCommand):
    help = "Importa N registros de CEPIM (S3) para o banco Django"

    duckdb_model = CEPIM
    django_model = CEPIMRecord
    default_ano  = "2026"
    default_mes  = "03"

    field_map = {
        "CNPJ ENTIDADE":                           "cnpj_entidade",
        "NOME ENTIDADE":                           "nome_entidade",
        "NÚMERO CONVÊNIO":                         "numero_convenio",
        "ÓRGÃO CONCEDENTE":                        "orgao_concedente",
        "MOTIVO DO IMPEDIMENTO":                   "motivo_impedimento",
    }
