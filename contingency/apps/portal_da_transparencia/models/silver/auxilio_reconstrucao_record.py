from django.db import models


class AuxilioReconstrucaoRecord(models.Model):
    """
    Amostra de beneficiários do Auxílio Reconstrução extraídos do S3.
    """

    # ── Referência ────────────────────────────────────────────────────
    mes_referencia = models.CharField(max_length=7, blank=True, null=True)

    # ── Geográfico ────────────────────────────────────────────────────
    uf = models.CharField(max_length=2, blank=True, null=True)
    codigo_municipio_siafi = models.CharField(max_length=10, blank=True, null=True)
    nome_municipio = models.CharField(max_length=100, blank=True, null=True)

    # ── Favorecido ────────────────────────────────────────────────────
    cpf_favorecido = models.CharField(max_length=11, blank=True, null=True)
    nis_favorecido = models.CharField(max_length=15, blank=True, null=True)
    nome_favorecido = models.CharField(max_length=300, blank=True, null=True)

    # ── Família ───────────────────────────────────────────────────────
    quantidade_pessoas_familia = models.CharField(max_length=10, blank=True, null=True)

    # ── Parcela ───────────────────────────────────────────────────────
    data_efetivacao_parcela = models.CharField(max_length=20, blank=True, null=True)
    valor_parcela = models.CharField(max_length=50, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auxilio_reconstrucao_records"
        verbose_name = "Auxílio Reconstrução — Registro"
        verbose_name_plural = "Auxílio Reconstrução — Registros"

    def __str__(self):
        return f"{self.nome_favorecido} ({self.nis_favorecido})"
