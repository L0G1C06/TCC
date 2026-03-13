from django.db import models


class LicitacoesRecord(models.Model):
    """
    Amostra de participantes de licitações federais extraídas do S3.
    """

    # ── Licitação ─────────────────────────────────────────────────────
    numero_licitacao = models.CharField(max_length=100, blank=True, null=True)
    numero_processo = models.CharField(max_length=100, blank=True, null=True)
    codigo_modalidade_compra = models.CharField(max_length=10, blank=True, null=True)
    modalidade_compra = models.CharField(max_length=100, blank=True, null=True)

    # ── Órgão e Unidade Gestora ───────────────────────────────────────
    codigo_orgao = models.CharField(max_length=20, blank=True, null=True)
    nome_orgao = models.CharField(max_length=300, blank=True, null=True)
    codigo_ug = models.CharField(max_length=20, blank=True, null=True)
    nome_ug = models.CharField(max_length=300, blank=True, null=True)

    # ── Item ──────────────────────────────────────────────────────────
    codigo_item_compra = models.CharField(max_length=50, blank=True, null=True)
    descricao_item_compra = models.CharField(max_length=500, blank=True, null=True)

    # ── Participante ──────────────────────────────────────────────────
    codigo_participante = models.CharField(max_length=50, blank=True, null=True)
    nome_participante = models.CharField(max_length=300, blank=True, null=True)
    flag_vencedor = models.CharField(max_length=10, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "licitacoes_records"
        verbose_name = "Licitações — Registro"
        verbose_name_plural = "Licitações — Registros"

    def __str__(self):
        return f"{self.nome_participante} - {self.descricao_item_compra} (Licitação: {self.numero_licitacao})"
