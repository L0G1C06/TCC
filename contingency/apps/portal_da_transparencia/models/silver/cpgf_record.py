from django.db import models


class CPGFRecord(models.Model):
    """
    Amostra de registros do CPGF extraídos do S3.
    """

    # ── Órgão ─────────────────────────────────────────────────────────
    codigo_orgao_superior  = models.CharField(max_length=20,  blank=True, null=True)
    nome_orgao_superior    = models.CharField(max_length=300, blank=True, null=True)
    codigo_orgao           = models.CharField(max_length=20,  blank=True, null=True)
    nome_orgao             = models.CharField(max_length=300, blank=True, null=True)
    codigo_unidade_gestora = models.CharField(max_length=20,  blank=True, null=True)
    nome_unidade_gestora   = models.CharField(max_length=300, blank=True, null=True)

    # ── Período ───────────────────────────────────────────────────────
    ano_extrato = models.CharField(max_length=4,  blank=True, null=True)
    mes_extrato = models.CharField(max_length=2,  blank=True, null=True)

    # ── Portador ──────────────────────────────────────────────────────
    cpf_portador  = models.CharField(max_length=20,  blank=True, null=True)
    nome_portador = models.CharField(max_length=300, blank=True, null=True)

    # ── Favorecido ────────────────────────────────────────────────────
    cnpj_ou_cpf_favorecido = models.CharField(max_length=20,  blank=True, null=True)
    nome_favorecido        = models.CharField(max_length=300, blank=True, null=True)

    # ── Transação ─────────────────────────────────────────────────────
    transacao       = models.TextField(blank=True, null=True)
    data_transacao  = models.CharField(max_length=20,  blank=True, null=True)
    valor_transacao = models.CharField(max_length=50,  blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cpgf_records"
        verbose_name = "CPGF — Registro"
        verbose_name_plural = "CPGF — Registros"

    def __str__(self):
        return f"{self.nome_portador} → {self.nome_favorecido} ({self.data_transacao})"