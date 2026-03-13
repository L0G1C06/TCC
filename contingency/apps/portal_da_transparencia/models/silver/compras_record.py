from django.db import models


class ComprasRecord(models.Model):
    """
    Amostra de itens de compras públicas federais extraídas do S3.
    """

    # ── Órgão e Unidade Gestora ───────────────────────────────────────
    codigo_orgao = models.CharField(max_length=20, blank=True, null=True)
    nome_orgao = models.CharField(max_length=300, blank=True, null=True)
    codigo_ug = models.CharField(max_length=20, blank=True, null=True)
    nome_ug = models.CharField(max_length=300, blank=True, null=True)

    # ── Contrato ──────────────────────────────────────────────────────
    numero_contrato = models.CharField(max_length=100, blank=True, null=True)

    # ── Item ──────────────────────────────────────────────────────────
    codigo_item_compra = models.CharField(max_length=50, blank=True, null=True)
    descricao_item_compra = models.CharField(max_length=500, blank=True, null=True)
    descricao_complementar_item_compra = models.TextField(blank=True, null=True)
    quantidade_item = models.CharField(max_length=50, blank=True, null=True)
    valor_item = models.CharField(max_length=50, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "compras_records"
        verbose_name = "Compras — Registro"
        verbose_name_plural = "Compras — Registros"

    def __str__(self):
        return f"{self.nome_orgao} - {self.descricao_item_compra} (UG: {self.codigo_ug})"
