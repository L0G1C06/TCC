from django.db import models


class CPDCRecord(models.Model):
    """
    Amostra de transações do CPC-D (Cartão de Pagamento de Despesas) extraídas do S3.
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

    # ── Portador ──────────────────────────────────────────────────────
    cpf_portador = models.CharField(max_length=11, blank=True, null=True)
    nome_portador = models.CharField(max_length=100, blank=True, null=True)

    # ── Favorecido ────────────────────────────────────────────────────
    cnpj_ou_cpf_favorecido = models.CharField(max_length=20, blank=True, null=True)
    nome_favorecido = models.CharField(max_length=200, blank=True, null=True)

    # ── Execução ──────────────────────────────────────────────────────
    executor_despesa = models.CharField(max_length=100, blank=True, null=True)

    # ── Convênio ──────────────────────────────────────────────────────
    numero_convenio = models.CharField(max_length=100, blank=True, null=True)
    codigo_convenente = models.CharField(max_length=20, blank=True, null=True)
    nome_convenente = models.CharField(max_length=200, blank=True, null=True)

    # ── Repasse ───────────────────────────────────────────────────────
    repasse = models.CharField(max_length=50, blank=True, null=True)

    # ── Transação ─────────────────────────────────────────────────────
    transacao = models.CharField(max_length=100, blank=True, null=True)
    data_transacao = models.CharField(max_length=20, blank=True, null=True)
    valor_transacao = models.CharField(max_length=50, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cpdc_records"
        verbose_name = "CPC-D — Registro"
        verbose_name_plural = "CPC-D — Registros"

    def __str__(self):
        return f"{self.codigo_orgao} - {self.nome_portador} ({self.valor_transacao})"
