from django.db import models


class OperacoesExportacaoRecord(models.Model):
    """
    Amostra de operações de exportação BNDES extraídas do S3.
    """

    # ── Exportador (pré/pós-embarque) ─────────────────────────────────
    exportador = models.CharField(max_length=300, blank=True, null=True)
    cnpj_do_exportador = models.CharField(max_length=20, blank=True, null=True)
    porte_do_exportador = models.CharField(max_length=100, blank=True, null=True)
    pais_destino_das_exportacoes = models.CharField(max_length=100, blank=True, null=True)

    # ── Cliente / Tomador (presente em todos os arquivos) ─────────────
    cliente = models.CharField(max_length=300, blank=True, null=True)
    cpf_cnpj = models.CharField(max_length=20, blank=True, null=True)
    porte_do_cliente = models.CharField(max_length=100, blank=True, null=True)
    natureza_do_cliente = models.CharField(max_length=100, blank=True, null=True)

    # ── Localização ───────────────────────────────────────────────────
    uf = models.CharField(max_length=2, blank=True, null=True)
    municipio = models.CharField(max_length=300, blank=True, null=True)
    municipio_codigo = models.CharField(max_length=10, blank=True, null=True)

    # ── Operação ──────────────────────────────────────────────────────
    numero_da_operacao = models.CharField(max_length=100, blank=True, null=True)
    descricao_da_operacao = models.TextField(blank=True, null=True)
    data_da_contratacao = models.CharField(max_length=20, blank=True, null=True)
    situacao_da_operacao = models.CharField(max_length=100, blank=True, null=True)
    tipo_de_garantia = models.CharField(max_length=100, blank=True, null=True)
    categoria = models.CharField(max_length=100, blank=True, null=True)

    # ── Classificação ─────────────────────────────────────────────────
    area_operacional = models.CharField(max_length=100, blank=True, null=True)
    modalidade_de_apoio = models.CharField(max_length=100, blank=True, null=True)
    forma_de_apoio = models.CharField(max_length=100, blank=True, null=True)
    produto = models.CharField(max_length=100, blank=True, null=True)
    modalidade_operacional = models.CharField(max_length=100, blank=True, null=True)
    instrumento_financeiro = models.CharField(max_length=100, blank=True, null=True)
    inovacao = models.CharField(max_length=100, blank=True, null=True)
    setor_subsetor_de_atividade = models.CharField(max_length=100, blank=True, null=True)

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

    # ── Financeiro / Valores ──────────────────────────────────────────
    moeda_sigla = models.CharField(max_length=10, blank=True, null=True)
    fonte_de_recursos_desembolsos = models.CharField(max_length=100, blank=True, null=True)
    fonte_de_recurso_desembolsos = models.CharField(max_length=100, blank=True, null=True)
    custo_financeiro = models.CharField(max_length=100, blank=True, null=True)
    mutuario = models.CharField(max_length=300, blank=True, null=True)
    valor_da_operacao_em_um = models.CharField(max_length=50, blank=True, null=True)
    valor_desembolsado_em_um = models.CharField(max_length=50, blank=True, null=True)
    valor_da_operacao_em_reais = models.CharField(max_length=50, blank=True, null=True)
    valor_desembolsado_em_reais = models.CharField(max_length=50, blank=True, null=True)
    juros = models.CharField(max_length=100, blank=True, null=True)
    prazo_total_meses = models.CharField(max_length=10, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "operacoes_exportacao_records"
        verbose_name = "Operações de Exportação — Registro"
        verbose_name_plural = "Operações de Exportação — Registros"

    def __str__(self):
        return f"{self.cliente} ({self.cpf_cnpj})"
