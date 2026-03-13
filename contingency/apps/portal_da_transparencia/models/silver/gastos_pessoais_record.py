from django.db import models


class GastosPessoaisRecord(models.Model):
    """
    Amostra de gastos pessoais extraídos do S3.
    """

    # ── Órgão ─────────────────────────────────────────────────────────
    codigo_orgao_superior = models.CharField(max_length=10, blank=True, null=True)
    orgao_superior = models.CharField(max_length=100, blank=True, null=True)
    codigo_orgao = models.CharField(max_length=10, blank=True, null=True)
    orgao = models.CharField(max_length=100, blank=True, null=True)

    # ── UG ────────────────────────────────────────────────────────────
    codigo_ug = models.CharField(max_length=10, blank=True, null=True)
    ug = models.CharField(max_length=100, blank=True, null=True)

    # ── Servidor/Parlamentar ──────────────────────────────────────────
    cpf_viajante = models.CharField(max_length=11, blank=True, null=True)
    nome_viajante = models.CharField(max_length=100, blank=True, null=True)
    cargo = models.CharField(max_length=100, blank=True, null=True)

    # ── Despesa ───────────────────────────────────────────────────────
    tipo_despesa = models.CharField(max_length=50, blank=True, null=True)
    descricao_despesa = models.TextField(blank=True, null=True)

    # ── Data ──────────────────────────────────────────────────────────
    data_despesa = models.CharField(max_length=20, blank=True, null=True)

    # ── Valor ─────────────────────────────────────────────────────────
    valor_despesa = models.CharField(max_length=50, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "gastos_pessoais_records"
        verbose_name = "Gasto Pessoal — Registro"
        verbose_name_plural = "Gastos Pessoais — Registros"

    def __str__(self):
        return f"{self.nome_viajante} - {self.tipo_despesa} ({self.valor_despesa})"
