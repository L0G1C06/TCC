from django.db import models


class BPCRecord(models.Model):
    """
    Amostra de beneficiários do BPC extraídos do S3.
    """

    # ── Competência e Referência ──────────────────────────────────────
    mes_competencia = models.CharField(max_length=7, blank=True, null=True)
    mes_referencia = models.CharField(max_length=7, blank=True, null=True)

    # ── Geográfico ────────────────────────────────────────────────────
    uf = models.CharField(max_length=2, blank=True, null=True)
    codigo_municipio_siafi = models.CharField(max_length=10, blank=True, null=True)
    nome_municipio = models.CharField(max_length=100, blank=True, null=True)

    # ── Beneficiário ──────────────────────────────────────────────────
    nis_beneficiario = models.CharField(max_length=15, blank=True, null=True)
    cpf_beneficiario = models.CharField(max_length=11, blank=True, null=True)
    nome_beneficiario = models.CharField(max_length=300, blank=True, null=True)

    # ── Representante Legal ───────────────────────────────────────────
    nis_representante_legal = models.CharField(max_length=15, blank=True, null=True)
    cpf_representante_legal = models.CharField(max_length=11, blank=True, null=True)
    nome_representante_legal = models.CharField(max_length=300, blank=True, null=True)

    # ── Benefício ─────────────────────────────────────────────────────
    numero_beneficio = models.CharField(max_length=50, blank=True, null=True)
    beneficio_judicial = models.CharField(max_length=10, blank=True, null=True)

    # ── Valor ─────────────────────────────────────────────────────────
    valor_parcela = models.CharField(max_length=50, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bpc_records"
        verbose_name = "BPC — Registro"
        verbose_name_plural = "BPC — Registros"

    def __str__(self):
        return f"{self.nome_beneficiario} ({self.nis_beneficiario})"
