from django.db import models


class PGDContratosRecord(models.Model):
    """
    Amostra de contratos do PGD extraídos do S3.
    """

    # ── Órgão ─────────────────────────────────────────────────────────
    codigo_orgao_superior = models.CharField(max_length=10, blank=True, null=True)
    orgao_superior = models.CharField(max_length=100, blank=True, null=True)
    codigo_orgao = models.CharField(max_length=10, blank=True, null=True)
    orgao = models.CharField(max_length=100, blank=True, null=True)

    # ── UG ────────────────────────────────────────────────────────────
    codigo_ug = models.CharField(max_length=10, blank=True, null=True)
    ug = models.CharField(max_length=100, blank=True, null=True)

    # ── Contrato ──────────────────────────────────────────────────────
    numero_contrato = models.CharField(max_length=100, blank=True, null=True)
    numero_processo = models.CharField(max_length=100, blank=True, null=True)

    # ── Fornecedor ────────────────────────────────────────────────────
    cnpj_fornecedor = models.CharField(max_length=20, blank=True, null=True)
    nome_fornecedor = models.CharField(max_length=200, blank=True, null=True)

    # ── Objeto ────────────────────────────────────────────────────────
    objeto_contrato = models.TextField(blank=True, null=True)

    # ── Valores ───────────────────────────────────────────────────────
    valor_inicial = models.CharField(max_length=50, blank=True, null=True)
    valor_final = models.CharField(max_length=50, blank=True, null=True)

    # ── Datas ─────────────────────────────────────────────────────────
    data_assinatura = models.CharField(max_length=20, blank=True, null=True)
    data_publicacao = models.CharField(max_length=20, blank=True, null=True)
    data_inicio_vigencia = models.CharField(max_length=20, blank=True, null=True)
    data_fim_vigencia = models.CharField(max_length=20, blank=True, null=True)

    # ── Situação ──────────────────────────────────────────────────────
    situacao_contrato = models.CharField(max_length=50, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pgd_contratos_records"
        verbose_name = "PGD Contrato — Registro"
        verbose_name_plural = "PGD Contratos — Registros"

    def __str__(self):
        return f"{self.numero_contrato} - {self.nome_fornecedor}"
