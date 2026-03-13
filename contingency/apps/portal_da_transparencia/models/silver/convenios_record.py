from django.db import models


class ConveniosRecord(models.Model):
    """
    Amostra de convênios extraídos do S3.
    """

    # ── Convênio ──────────────────────────────────────────────────────
    numero_convenio = models.CharField(max_length=100, blank=True, null=True)
    numero_original = models.CharField(max_length=100, blank=True, null=True)

    # ── Ordem Bancária ────────────────────────────────────────────────
    data_emissao_ob = models.CharField(max_length=20, blank=True, null=True)
    numero_ordem_bancaria = models.CharField(max_length=100, blank=True, null=True)

    # ── Valores ───────────────────────────────────────────────────────
    valor_liberado = models.CharField(max_length=50, blank=True, null=True)
    valor_convenio = models.CharField(max_length=50, blank=True, null=True)
    valor_contrapartida = models.CharField(max_length=50, blank=True, null=True)

    # ── Geográfico ────────────────────────────────────────────────────
    uf = models.CharField(max_length=2, blank=True, null=True)
    codigo_siafi_municipio = models.CharField(max_length=10, blank=True, null=True)
    nome_municipio = models.CharField(max_length=100, blank=True, null=True)

    # ── Situação ──────────────────────────────────────────────────────
    situacao_convenio = models.CharField(max_length=50, blank=True, null=True)

    # ── Processo ──────────────────────────────────────────────────────
    numero_processo_convenio = models.CharField(max_length=100, blank=True, null=True)

    # ── Objeto ────────────────────────────────────────────────────────
    objeto_convenio = models.TextField(blank=True, null=True)

    # ── Órgão Concedente ──────────────────────────────────────────────
    codigo_orgao_superior = models.CharField(max_length=10, blank=True, null=True)
    nome_orgao_superior = models.CharField(max_length=100, blank=True, null=True)
    codigo_orgao_concedente = models.CharField(max_length=10, blank=True, null=True)
    nome_orgao_concedente = models.CharField(max_length=100, blank=True, null=True)
    codigo_ug_concedente = models.CharField(max_length=10, blank=True, null=True)
    nome_ug_concedente = models.CharField(max_length=100, blank=True, null=True)

    # ── Convenente ────────────────────────────────────────────────────
    codigo_convenente = models.CharField(max_length=20, blank=True, null=True)
    tipo_convenente = models.CharField(max_length=50, blank=True, null=True)
    nome_convenente = models.CharField(max_length=200, blank=True, null=True)
    tipo_ente_convenente = models.CharField(max_length=50, blank=True, null=True)

    # ── Instrumento ───────────────────────────────────────────────────
    tipo_instrumento = models.CharField(max_length=50, blank=True, null=True)

    # ── Datas ─────────────────────────────────────────────────────────
    data_publicacao = models.CharField(max_length=20, blank=True, null=True)
    data_inicio_vigencia = models.CharField(max_length=20, blank=True, null=True)
    data_final_vigencia = models.CharField(max_length=20, blank=True, null=True)
    data_ultima_liberacao = models.CharField(max_length=20, blank=True, null=True)

    # ── Última Liberação ──────────────────────────────────────────────
    valor_ultima_liberacao = models.CharField(max_length=50, blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "convenios_records"
        verbose_name = "Convênio — Registro"
        verbose_name_plural = "Convênios — Registros"

    def __str__(self):
        return f"{self.numero_convenio} - {self.nome_convenente}"
