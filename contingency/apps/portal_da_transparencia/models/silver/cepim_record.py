from django.db import models


class CEPIMRecord(models.Model):
    """
    Amostra de entidades impedidas no CEPIM extraídas do S3.
    """

    # ── Entidade ──────────────────────────────────────────────────────
    cnpj_entidade = models.CharField(max_length=20, blank=True, null=True)
    nome_entidade = models.CharField(max_length=300, blank=True, null=True)

    # ── Convênio ──────────────────────────────────────────────────────
    numero_convenio = models.CharField(max_length=100, blank=True, null=True)

    # ── Órgão ─────────────────────────────────────────────────────────
    orgao_concedente = models.CharField(max_length=300, blank=True, null=True)

    # ── Motivo ────────────────────────────────────────────────────────
    motivo_impedimento = models.TextField(blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cepim_records"
        verbose_name = "CEPIM — Registro"
        verbose_name_plural = "CEPIM — Registros"

    def __str__(self):
        return f"{self.nome_entidade} ({self.cnpj_entidade})"
