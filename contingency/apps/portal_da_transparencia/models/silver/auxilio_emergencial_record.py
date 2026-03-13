from django.db import models


class AuxilioEmergencialRecord(models.Model):
    """
    Amostra de beneficiários do Auxílio Emergencial extraídos do S3.
    """

    # ── Disponibilização ──────────────────────────────────────────────
    mes_disponibilizacao = models.CharField(max_length=7, blank=True, null=True)

    # ── Geográfico ────────────────────────────────────────────────────
    uf = models.CharField(max_length=2, blank=True, null=True)
    codigo_municipio_ibge = models.CharField(max_length=7, blank=True, null=True)
    nome_municipio = models.CharField(max_length=100, blank=True, null=True)

    # ── Beneficiário ──────────────────────────────────────────────────
    nis_beneficiario = models.CharField(max_length=15, blank=True, null=True)
    cpf_beneficiario = models.CharField(max_length=11, blank=True, null=True)
    nome_beneficiario = models.CharField(max_length=300, blank=True, null=True)

    # ── Responsável ───────────────────────────────────────────────────
    nis_responsavel = models.CharField(max_length=15, blank=True, null=True)
    cpf_responsavel = models.CharField(max_length=11, blank=True, null=True)
    nome_responsavel = models.CharField(max_length=300, blank=True, null=True)

    # ── Enquadramento ─────────────────────────────────────────────────
    enquadramento = models.CharField(max_length=100, blank=True, null=True)

    # ── Parcela ───────────────────────────────────────────────────────
    parcela = models.CharField(max_length=10, blank=True, null=True)

    # ── Observação ────────────────────────────────────────────────────
    observacao = models.TextField(blank=True, null=True)

    # ── Valor ─────────────────────────────────────────────────────────
    valor_beneficio = models.CharField(max_length=50, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auxilio_emergencial_records"
        verbose_name = "Auxílio Emergencial — Registro"
        verbose_name_plural = "Auxílio Emergencial — Registros"

    def __str__(self):
        return f"{self.nome_beneficiario} ({self.nis_beneficiario})"
