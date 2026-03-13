from django.db import models


class BolsaFamiliaPagamentosRecord(models.Model):
    """
    Amostra de beneficiários do Bolsa Família - Pagamentos extraídos do S3.
    """

    # ── Competência e Referência ──────────────────────────────────────
    mes_competencia = models.CharField(max_length=7, blank=True, null=True)
    mes_referencia = models.CharField(max_length=7, blank=True, null=True)

    # ── Geográfico ────────────────────────────────────────────────────
    uf = models.CharField(max_length=2, blank=True, null=True)
    codigo_municipio_siafi = models.CharField(max_length=10, blank=True, null=True)
    nome_municipio = models.CharField(max_length=100, blank=True, null=True)

    # ── Favorecido ────────────────────────────────────────────────────
    cpf_favorecido = models.CharField(max_length=11, blank=True, null=True)
    nis_favorecido = models.CharField(max_length=15, blank=True, null=True)
    nome_favorecido = models.CharField(max_length=300, blank=True, null=True)

    # ── Valor ─────────────────────────────────────────────────────────
    valor_parcela = models.CharField(max_length=50, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bolsa_familia_pagamentos_records"
        verbose_name = "Bolsa Família Pagamentos — Registro"
        verbose_name_plural = "Bolsa Família Pagamentos — Registros"

    def __str__(self):
        return f"{self.nome_favorecido} ({self.nis_favorecido})"
