from apps.datalake.management.commands._base_import import BaseImportCommand
from apps.portal_da_transparencia.models.viagens import Viagens
from apps.portal_da_transparencia.models.silver import ViagensRecord
import duckdb
import polars as pl
class Command(BaseImportCommand):
    help = "Importa N registros de Viagens (S3) para o banco Django"

    duckdb_model = Viagens
    django_model = ViagensRecord
    default_ano  = "2024"
    default_mes = None

    field_map = {
        "Identificador do processo de viagem":  "identificador_processo_viagem",
        "Número da Proposta (PCDP)":            "numero_proposta_pcdp",
        "Situação":                             "situacao",
        "Viagem Urgente":                       "viagem_urgente",
        "Justificativa Urgência Viagem":        "justificativa_urgencia",
        "Missao?":                              "missao",          # ⚠️ com '?'
        "Código do órgão superior":             "codigo_orgao_superior",
        "Nome do órgão superior":               "nome_orgao_superior",
        "Codigo do órgão pagador":              "codigo_orgao_pagador",  # ⚠️ sem acento
        "Nome do órgao pagador":                "nome_orgao_pagador",    # ⚠️ sem til
        "Código da unidade gestora pagadora":   "codigo_ug_pagadora",
        "Nome da unidade gestora pagadora":     "nome_ug_pagadora",
        "Código órgão solicitante":             "codigo_orgao_solicitante",
        "Nome órgão solicitante":               "nome_orgao_solicitante",
        "CPF viajante":                         "cpf_viajante",
        "Nome":                                 "nome_viajante",
        "Cargo":                                "cargo",
        "Função":                               "funcao",
        "Descrição Função":                     "descricao_funcao",
        "Período - Data de início":             "periodo_data_inicio",
        "Período - Data de fim":                "periodo_data_fim",
        "Destinos":                             "destinos",
        "Motivo":                               "motivo",
        "Tipo de pagamento":                    "tipo_de_pagamento",
        "Valor":                                "valor",
        "Valor diárias":                        "valor_diarias",
        "Valor passagens":                      "valor_passagens",
        "Valor devolução":                      "valor_devolucao",
        "Valor outros gastos":                  "valor_outros_gastos",
        "Número Diárias":                       "numero_diarias",
        "Meio de transporte":                   "meio_de_transporte",
        "Valor da passagem":                    "valor_da_passagem",
        "Taxa de serviço":                      "taxa_de_servico",
        "Data da emissão/compra":               "data_emissao_compra",
        "Hora da emissão/compra":               "hora_emissao_compra",
        "Sequência Trecho":                     "sequencia_trecho",
        "País - Origem ida":                    "pais_origem_ida",
        "UF - Origem ida":                      "uf_origem_ida",
        "Cidade - Origem ida":                  "cidade_origem_ida",
        "País - Destino ida":                   "pais_destino_ida",
        "UF - Destino ida":                     "uf_destino_ida",
        "Cidade - Destino ida":                 "cidade_destino_ida",
        "País - Origem volta":                  "pais_origem_volta",
        "UF - Origem volta":                    "uf_origem_volta",
        "Cidade - Origem volta":                "cidade_origem_volta",
        "Pais - Destino volta":                 "pais_destino_volta",  # ⚠️ sem acento
        "UF - Destino volta":                   "uf_destino_volta",
        "Cidade - Destino volta":               "cidade_destino_volta",
        "Origem - Data":                        "origem_data",
        "Origem - País":                        "origem_pais",
        "Origem - UF":                          "origem_uf",
        "Origem - Cidade":                      "origem_cidade",
        "Destino - Data":                       "destino_data",
        "Destino - País":                       "destino_pais",
        "Destino - UF":                         "destino_uf",
        "Destino - Cidade":                     "destino_cidade",
    }

    def _read_data(self, ano, mes, limit):
        """
        Viagens não tem partição de mês — os parquets ficam em:
            s3://<bucket>/data/portal_da_transparencia/parquet/modulo=viagens/ano=XXXX/*.parquet
        """
        from django.conf import settings

        bucket = settings.DATALAKE_BUCKET
        path = f"s3://{bucket}/data/portal_da_transparencia/parquet/modulo=viagens/ano={ano}/**/*.parquet"

        conn = duckdb.connect()
        conn.execute(f"SET s3_region='{settings.AWS_DEFAULT_REGION}'")
        conn.execute(f"SET s3_access_key_id='{settings.AWS_ACCESS_KEY_ID}'")
        conn.execute(f"SET s3_secret_access_key='{settings.AWS_SECRET_ACCESS_KEY}'")

        arrow = conn.execute(
            f"SELECT * FROM read_parquet('{path}', union_by_name=true) LIMIT {limit}"
        ).fetch_arrow_table()

        conn.close()
        return pl.from_arrow(arrow)