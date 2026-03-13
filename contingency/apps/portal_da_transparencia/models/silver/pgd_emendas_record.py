from django.db import models


class PGDEmendasRecord(models.Model):
    """
    Amostra de emendas do PGD extraídas do S3.
    """

    # ── Emenda ────────────────────────────────────────────────────────
    codigo_da_emenda = models.CharField(max_length=50, blank=True, null=True)
    numero_da_emenda = models.CharField(max_length=50, blank=True, null=True)
    tipo_de_emenda = models.CharField(max_length=50, blank=True, null=True)

    # ── Autor ─────────────────────────────────────────────────────────
    codigo_do_autor = models.CharField(max_length=50, blank=True, null=True)
    nome_do_autor = models.CharField(max_length=100, blank=True, null=True)
    sigla_do_partido = models.CharField(max_length=10, blank=True, null=True)
    uf_do_autor = models.CharField(max_length=2, blank=True, null=True)

    # ── Valor ─────────────────────────────────────────────────────────
    valor_emenda = models.CharField(max_length=50, blank=True, null=True)
    valor_empenhado = models.CharField(max_length=50, blank=True, null=True)
    valor_pago = models.CharField(max_length=50, blank=True, null=True)

    # ── Situação ──────────────────────────────────────────────────────
    situacao_da_emenda = models.CharField(max_length=50, blank=True, null=True)

    # ── Localidade ────────────────────────────────────────────────────
    localidade_de_aplicacao = models.CharField(max_length=100, blank=True, null=True)
    codigo_municipio_siafi = models.CharField(max_length=10, blank=True, null=True)
    nome_municipio = models.CharField(max_length=100, blank=True, null=True)
    uf_municipio = models.CharField(max_length=2, blank=True, null=True)

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
        db_table = "pgd_emendas_records"
        verbose_name = "PGD Emenda — Registro"
        verbose_name_plural = "PGD Emendas — Registros"

    def __str__(self):
        return f"{self.codigo_da_emenda} - {self.nome_do_autor} ({self.valor_emenda})"
