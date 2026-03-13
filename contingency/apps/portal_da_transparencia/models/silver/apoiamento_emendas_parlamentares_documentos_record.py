from django.db import models


class ApoiamentoEmendasParlamentaresDocumentosRecord(models.Model):
    """
    Amostra de documentos de apoio em emendas parlamentares extraídos do S3.
    """

    # ── Apoiador ──────────────────────────────────────────────────────
    codigo_apoiador = models.CharField(max_length=50, blank=True, null=True)
    apoiador = models.CharField(max_length=300, blank=True, null=True)

    # ── Data do Apoio ─────────────────────────────────────────────────
    data_apoio = models.CharField(max_length=20, blank=True, null=True)
    data_retirada_apoio = models.CharField(max_length=20, blank=True, null=True)

    # ── Empenho ───────────────────────────────────────────────────────
    empenho = models.CharField(max_length=100, blank=True, null=True)
    data_ultima_movimentacao_empenho = models.CharField(max_length=20, blank=True, null=True)

    # ── Favorecido ────────────────────────────────────────────────────
    codigo_favorecido = models.CharField(max_length=50, blank=True, null=True)
    favorecido = models.CharField(max_length=300, blank=True, null=True)
    tipo_favorecido = models.CharField(max_length=100, blank=True, null=True)
    uf_favorecido = models.CharField(max_length=2, blank=True, null=True)
    municipio_favorecido = models.CharField(max_length=100, blank=True, null=True)

    # ── Emenda Parlamentar ────────────────────────────────────────────
    codigo_da_emenda = models.CharField(max_length=50, blank=True, null=True)
    tipo_de_emenda = models.CharField(max_length=100, blank=True, null=True)
    ano_da_emenda = models.CharField(max_length=4, blank=True, null=True)
    codigo_autor_emenda = models.CharField(max_length=50, blank=True, null=True)
    nome_autor_emenda = models.CharField(max_length=300, blank=True, null=True)
    numero_da_emenda = models.CharField(max_length=50, blank=True, null=True)
    localidade_aplicacao_recurso = models.CharField(max_length=200, blank=True, null=True)

    # ── UG e Órgão ────────────────────────────────────────────────────
    codigo_ug = models.CharField(max_length=50, blank=True, null=True)
    ug = models.CharField(max_length=300, blank=True, null=True)
    codigo_unidade_orcamentaria = models.CharField(max_length=50, blank=True, null=True)
    unidade_orcamentaria = models.CharField(max_length=300, blank=True, null=True)
    codigo_orgao_siafi = models.CharField(max_length=50, blank=True, null=True)
    orgao = models.CharField(max_length=300, blank=True, null=True)
    codigo_orgao_superior_siafi = models.CharField(max_length=50, blank=True, null=True)
    orgao_superior = models.CharField(max_length=300, blank=True, null=True)

    # ── Ação Orçamentária ─────────────────────────────────────────────
    codigo_acao = models.CharField(max_length=50, blank=True, null=True)
    acao = models.CharField(max_length=300, blank=True, null=True)

    # ── Valores ───────────────────────────────────────────────────────
    valor_empenhado = models.CharField(max_length=50, blank=True, null=True)
    valor_cancelado = models.CharField(max_length=50, blank=True, null=True)
    valor_pago = models.CharField(max_length=50, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "apoiamento_emendas_parlamentares_documentos_records"
        verbose_name = "Apoiamento Emendas Parlamentares — Registro"
        verbose_name_plural = "Apoiamento Emendas Parlamentares — Registros"

    def __str__(self):
        return f"{self.apoiador} - Emenda {self.codigo_da_emenda}"
