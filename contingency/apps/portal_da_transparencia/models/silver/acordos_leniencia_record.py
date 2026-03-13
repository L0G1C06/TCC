from django.db import models


class AcordosLenienciaRecord(models.Model):
    """
    Amostra de acordos de leniência extraídos do S3.
    """

    # ── Acordo ─────────────────────────────────────────────────────────
    id_do_acordo = models.CharField(max_length=100, blank=True, null=True)
    efeito_do_acordo = models.CharField(max_length=200, blank=True, null=True)
    complemento = models.TextField(blank=True, null=True)

    # ── Sancionado ────────────────────────────────────────────────────
    cnpj_do_sancionado = models.CharField(max_length=20, blank=True, null=True)
    razao_social_receita = models.CharField(max_length=300, blank=True, null=True)
    nome_fantasia_receita = models.CharField(max_length=300, blank=True, null=True)

    # ── Datas ─────────────────────────────────────────────────────────
    data_inicio_acordo = models.CharField(max_length=20, blank=True, null=True)
    data_fim_acordo = models.CharField(max_length=20, blank=True, null=True)

    # ── Situação ──────────────────────────────────────────────────────
    situacao_acordo = models.CharField(max_length=100, blank=True, null=True)
    data_informacao = models.CharField(max_length=20, blank=True, null=True)

    # ── Processo ──────────────────────────────────────────────────────
    numero_processo = models.CharField(max_length=100, blank=True, null=True)

    # ── Termos ────────────────────────────────────────────────────────
    termos_do_acordo = models.TextField(blank=True, null=True)

    # ── Órgão Sancionador ─────────────────────────────────────────────
    orgao_sancionador = models.CharField(max_length=300, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "acordos_leniencia_records"
        verbose_name = "Acordo de Leniência — Registro"
        verbose_name_plural = "Acordos de Leniência — Registros"

    def __str__(self):
        return f"{self.razao_social_receita} - Acordo {self.id_do_acordo}"
