from django.db import models


class ViagensRecord(models.Model):
    """
    Amostra de registros de Viagens a Serviço extraídos do S3.
    """

    # ── Identificação do processo ─────────────────────────────────────
    identificador_processo_viagem = models.BigIntegerField(blank=True, null=True)
    numero_proposta_pcdp          = models.CharField(max_length=100, blank=True, null=True)
    situacao                      = models.CharField(max_length=100, blank=True, null=True)
    viagem_urgente                = models.CharField(max_length=10,  blank=True, null=True)
    justificativa_urgencia        = models.TextField(blank=True, null=True)
    missao                        = models.CharField(max_length=300, blank=True, null=True)

    # ── Órgão superior ────────────────────────────────────────────────
    codigo_orgao_superior = models.CharField(max_length=20,  blank=True, null=True)
    nome_orgao_superior   = models.CharField(max_length=300, blank=True, null=True)

    # ── Órgão pagador ─────────────────────────────────────────────────
    codigo_orgao_pagador  = models.CharField(max_length=20,  blank=True, null=True)
    nome_orgao_pagador    = models.CharField(max_length=300, blank=True, null=True)
    codigo_ug_pagadora    = models.CharField(max_length=20,  blank=True, null=True)
    nome_ug_pagadora      = models.CharField(max_length=300, blank=True, null=True)

    # ── Órgão solicitante ─────────────────────────────────────────────
    codigo_orgao_solicitante = models.CharField(max_length=20,  blank=True, null=True)
    nome_orgao_solicitante   = models.CharField(max_length=300, blank=True, null=True)

    # ── Viajante ──────────────────────────────────────────────────────
    cpf_viajante      = models.CharField(max_length=20,  blank=True, null=True)
    nome_viajante     = models.CharField(max_length=300, blank=True, null=True)
    cargo             = models.CharField(max_length=200, blank=True, null=True)
    funcao            = models.CharField(max_length=200, blank=True, null=True)
    descricao_funcao  = models.CharField(max_length=200, blank=True, null=True)

    # ── Período e destinos ────────────────────────────────────────────
    periodo_data_inicio = models.CharField(max_length=20,  blank=True, null=True)
    periodo_data_fim    = models.CharField(max_length=20,  blank=True, null=True)
    destinos            = models.TextField(blank=True, null=True)
    motivo              = models.TextField(blank=True, null=True)

    # ── Pagamento ─────────────────────────────────────────────────────
    tipo_de_pagamento = models.CharField(max_length=100, blank=True, null=True)
    valor             = models.CharField(max_length=50,  blank=True, null=True)

    # ── Valores consolidados ──────────────────────────────────────────
    valor_diarias       = models.CharField(max_length=50, blank=True, null=True)
    valor_passagens     = models.CharField(max_length=50, blank=True, null=True)
    valor_devolucao     = models.CharField(max_length=50, blank=True, null=True)
    valor_outros_gastos = models.CharField(max_length=50, blank=True, null=True)
    numero_diarias      = models.CharField(max_length=20, blank=True, null=True)

    # ── Passagem: emissão ─────────────────────────────────────────────
    meio_de_transporte  = models.CharField(max_length=100, blank=True, null=True)
    valor_da_passagem   = models.CharField(max_length=50,  blank=True, null=True)
    taxa_de_servico     = models.CharField(max_length=50,  blank=True, null=True)
    data_emissao_compra = models.CharField(max_length=20,  blank=True, null=True)
    hora_emissao_compra = models.CharField(max_length=10,  blank=True, null=True)
    sequencia_trecho    = models.BigIntegerField(blank=True, null=True)

    # ── Passagem: origem/destino agregado ─────────────────────────────
    pais_origem_ida      = models.CharField(max_length=100, blank=True, null=True)
    uf_origem_ida        = models.CharField(max_length=2,   blank=True, null=True)
    cidade_origem_ida    = models.CharField(max_length=100, blank=True, null=True)
    pais_destino_ida     = models.CharField(max_length=100, blank=True, null=True)
    uf_destino_ida       = models.CharField(max_length=2,   blank=True, null=True)
    cidade_destino_ida   = models.CharField(max_length=100, blank=True, null=True)
    pais_origem_volta    = models.CharField(max_length=100, blank=True, null=True)
    uf_origem_volta      = models.CharField(max_length=2,   blank=True, null=True)
    cidade_origem_volta  = models.CharField(max_length=100, blank=True, null=True)
    pais_destino_volta   = models.CharField(max_length=100, blank=True, null=True)
    uf_destino_volta     = models.CharField(max_length=2,   blank=True, null=True)
    cidade_destino_volta = models.CharField(max_length=100, blank=True, null=True)

    # ── Passagem: trecho detalhado ────────────────────────────────────
    origem_data   = models.CharField(max_length=20,  blank=True, null=True)
    origem_pais   = models.CharField(max_length=100, blank=True, null=True)
    origem_uf     = models.CharField(max_length=2,   blank=True, null=True)
    origem_cidade = models.CharField(max_length=100, blank=True, null=True)
    destino_data  = models.CharField(max_length=20,  blank=True, null=True)
    destino_pais  = models.CharField(max_length=100, blank=True, null=True)
    destino_uf    = models.CharField(max_length=2,   blank=True, null=True)
    destino_cidade = models.CharField(max_length=100, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "viagens_records"
        verbose_name = "Viagens — Registro"
        verbose_name_plural = "Viagens — Registros"

    def __str__(self):
        return f"{self.nome_viajante} ({self.numero_proposta_pcdp})"