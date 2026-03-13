from django.db import models


class DespesasExecucaoRecord(models.Model):
    """
    Amostra de despesas em execução extraídas do S3.
    """

    # ── Pagamento ─────────────────────────────────────────────────────
    codigo_pagamento = models.CharField(max_length=100, blank=True, null=True)
    codigo_pagamento_resumido = models.CharField(max_length=50, blank=True, null=True)

    # ── Empenho ───────────────────────────────────────────────────────
    codigo_empenho = models.CharField(max_length=100, blank=True, null=True)
    id_empenho = models.CharField(max_length=100, blank=True, null=True)

    # ── Orçamentário ──────────────────────────────────────────────────
    codigo_categoria_despesa = models.CharField(max_length=10, blank=True, null=True)
    categoria_despesa = models.CharField(max_length=100, blank=True, null=True)
    codigo_grupo_despesa = models.CharField(max_length=10, blank=True, null=True)
    grupo_despesa = models.CharField(max_length=100, blank=True, null=True)
    codigo_modalidade_aplicacao = models.CharField(max_length=10, blank=True, null=True)
    modalidade_aplicacao = models.CharField(max_length=100, blank=True, null=True)
    codigo_elemento_despesa = models.CharField(max_length=10, blank=True, null=True)
    elemento_despesa = models.CharField(max_length=100, blank=True, null=True)
    codigo_subelemento_despesa = models.CharField(max_length=10, blank=True, null=True)
    subelemento_despesa = models.CharField(max_length=100, blank=True, null=True)

    # ── Descrição ─────────────────────────────────────────────────────
    descricao = models.TextField(blank=True, null=True)
    quantidade = models.CharField(max_length=50, blank=True, null=True)
    valor_unitario = models.CharField(max_length=50, blank=True, null=True)
    valor_total = models.CharField(max_length=50, blank=True, null=True)

    # ── Sequencial ────────────────────────────────────────────────────
    sequencial = models.CharField(max_length=50, blank=True, null=True)
    valor_atual = models.CharField(max_length=50, blank=True, null=True)

    # ── Data ──────────────────────────────────────────────────────────
    data_emissao = models.CharField(max_length=20, blank=True, null=True)

    # ── Documento ─────────────────────────────────────────────────────
    codigo_tipo_documento = models.CharField(max_length=10, blank=True, null=True)
    tipo_documento = models.CharField(max_length=100, blank=True, null=True)

    # ── Ordem Bancária ────────────────────────────────────────────────
    tipo_ob = models.CharField(max_length=50, blank=True, null=True)

    # ── Extraorçamentário ─────────────────────────────────────────────
    extraorçamentario = models.CharField(max_length=10, blank=True, null=True)

    # ── Órgão ─────────────────────────────────────────────────────────
    codigo_orgao_superior = models.CharField(max_length=10, blank=True, null=True)
    orgao_superior = models.CharField(max_length=100, blank=True, null=True)
    codigo_orgao = models.CharField(max_length=10, blank=True, null=True)
    orgao = models.CharField(max_length=100, blank=True, null=True)

    # ── UG ────────────────────────────────────────────────────────────
    codigo_ug = models.CharField(max_length=10, blank=True, null=True)
    ug = models.CharField(max_length=100, blank=True, null=True)

    # ── Função, Subfunção, Programa, Ação ─────────────────────────────
    codigo_funcao = models.CharField(max_length=10, blank=True, null=True)
    funcao = models.CharField(max_length=100, blank=True, null=True)
    codigo_subfuncao = models.CharField(max_length=10, blank=True, null=True)
    subfuncao = models.CharField(max_length=100, blank=True, null=True)
    codigo_programa = models.CharField(max_length=10, blank=True, null=True)
    programa = models.CharField(max_length=100, blank=True, null=True)
    codigo_acao = models.CharField(max_length=10, blank=True, null=True)
    acao = models.CharField(max_length=100, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "despesas_execucao_records"
        verbose_name = "Despesa em Execução — Registro"
        verbose_name_plural = "Despesas em Execução — Registros"

    def __str__(self):
        return f"{self.codigo_pagamento} - {self.descricao}"
