from django.db import models


class CPCCRecord(models.Model):
    """
    Amostra de transações do CPC-C (Cartão de Pagamento de Compras e Contratos) extraídas do S3.
    """

    # ── Órgão ─────────────────────────────────────────────────────────
    codigo_orgao_superior = models.CharField(max_length=10, blank=True, null=True)
    nome_orgao_superior = models.CharField(max_length=100, blank=True, null=True)
    codigo_orgao = models.CharField(max_length=10, blank=True, null=True)
    nome_orgao = models.CharField(max_length=100, blank=True, null=True)

    # ── UG ────────────────────────────────────────────────────────────
    codigo_unidade_gestora = models.CharField(max_length=10, blank=True, null=True)
    nome_unidade_gestora = models.CharField(max_length=100, blank=True, null=True)

    # ── Extrato ───────────────────────────────────────────────────────
    ano_extrato = models.CharField(max_length=4, blank=True, null=True)
    mes_extrato = models.CharField(max_length=2, blank=True, null=True)

    # ── Aquisição ─────────────────────────────────────────────────────
    tipo_aquisicao = models.CharField(max_length=50, blank=True, null=True)

    # ── Favorecido ────────────────────────────────────────────────────
    cnpj_ou_cpf_favorecido = models.CharField(max_length=20, blank=True, null=True)
    nome_favorecido = models.CharField(max_length=200, blank=True, null=True)

    # ── Transação ─────────────────────────────────────────────────────
    transacao = models.CharField(max_length=100, blank=True, null=True)
    data_transacao = models.CharField(max_length=20, blank=True, null=True)
    valor_transacao = models.CharField(max_length=50, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cpcc_records"
        verbose_name = "CPC-C — Registro"
        verbose_name_plural = "CPC-C — Registros"

    def __str__(self):
        return f"{self.codigo_orgao} - {self.nome_favorecido} ({self.valor_transacao})"
