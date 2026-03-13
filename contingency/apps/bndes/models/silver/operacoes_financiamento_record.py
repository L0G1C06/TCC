from django.db import models


class OperacoesFinanciamentoRecord(models.Model):
    """
    Amostra de operações de financiamento BNDES extraídas do S3.
    """

    # ── Cliente ───────────────────────────────────────────────────────
    cliente = models.CharField(max_length=300, blank=True, null=True)
    cpf_cnpj = models.CharField(max_length=20, blank=True, null=True)
    cnpj = models.CharField(max_length=20, blank=True, null=True)
    porte_do_cliente = models.CharField(max_length=100, blank=True, null=True)
    natureza_do_cliente = models.CharField(max_length=100, blank=True, null=True)

    # ── Localização ───────────────────────────────────────────────────
    uf = models.CharField(max_length=2, blank=True, null=True)
    municipio = models.CharField(max_length=300, blank=True, null=True)
    municipio_codigo = models.CharField(max_length=10, blank=True, null=True)

    # ── Operação ──────────────────────────────────────────────────────
    data_da_contratacao = models.CharField(max_length=20, blank=True, null=True)
    situacao_da_operacao = models.CharField(max_length=100, blank=True, null=True)
    descricao_do_projeto = models.TextField(blank=True, null=True)
    numero_do_contrato = models.CharField(max_length=100, blank=True, null=True)
    situacao_do_contrato = models.CharField(max_length=100, blank=True, null=True)
    tipo_de_garantia = models.CharField(max_length=100, blank=True, null=True)
    tipo_de_excepcionalidade = models.CharField(max_length=100, blank=True, null=True)

    # ── Classificação ─────────────────────────────────────────────────
    area_operacional = models.CharField(max_length=100, blank=True, null=True)
    modalidade_de_apoio = models.CharField(max_length=100, blank=True, null=True)
    forma_de_apoio = models.CharField(max_length=100, blank=True, null=True)
    produto = models.CharField(max_length=100, blank=True, null=True)
    instrumento_financeiro = models.CharField(max_length=100, blank=True, null=True)
    inovacao = models.CharField(max_length=100, blank=True, null=True)
    fonte_de_recurso_desembolsos = models.CharField(max_length=100, blank=True, null=True)
    custo_financeiro = models.CharField(max_length=100, blank=True, null=True)

    # ── Setorial / CNAE ───────────────────────────────────────────────
    setor_cnae = models.CharField(max_length=100, blank=True, null=True)
    subsetor_cnae_agrupado = models.CharField(max_length=100, blank=True, null=True)
    subsetor_cnae_codigo = models.CharField(max_length=100, blank=True, null=True)
    subsetor_cnae_nome = models.CharField(max_length=300, blank=True, null=True)
    setor_bndes = models.CharField(max_length=100, blank=True, null=True)
    subsetor_bndes = models.CharField(max_length=100, blank=True, null=True)

    # ── Agente financeiro ─────────────────────────────────────────────
    instituicao_financeira_credenciada = models.CharField(max_length=300, blank=True, null=True)
    cnpj_do_agente_financeiro = models.CharField(max_length=20, blank=True, null=True)
    cnpj_da_instituicao_financeira_credenciada = models.CharField(max_length=20, blank=True, null=True)

    # ── Valores ───────────────────────────────────────────────────────
    valor_da_operacao_em_reais = models.CharField(max_length=50, blank=True, null=True)
    valor_contratado_reais = models.CharField(max_length=50, blank=True, null=True)
    valor_desembolsado_reais = models.CharField(max_length=50, blank=True, null=True)
    juros = models.CharField(max_length=100, blank=True, null=True)
    prazo_carencia_meses = models.CharField(max_length=10, blank=True, null=True)
    prazo_amortizacao_meses = models.CharField(max_length=10, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "operacoes_financiamento_records"
        verbose_name = "Operações de Financiamento — Registro"
        verbose_name_plural = "Operações de Financiamento — Registros"

    def __str__(self):
        return f"{self.cliente} ({self.cpf_cnpj or self.cnpj})"
