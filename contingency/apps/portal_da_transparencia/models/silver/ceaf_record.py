from django.db import models


class CEAFRecord(models.Model):
    """
    Amostra de sancionados no CEAF extraídos do S3.
    """

    # ── Cadastro ──────────────────────────────────────────────────────
    cadastro = models.CharField(max_length=100, blank=True, null=True)

    # ── Sanção ────────────────────────────────────────────────────────
    codigo_sancao = models.CharField(max_length=50, blank=True, null=True)
    tipo_pessoa = models.CharField(max_length=1, blank=True, null=True)
    cpf_ou_cnpj_do_sancionado = models.CharField(max_length=20, blank=True, null=True)
    nome_do_sancionado = models.CharField(max_length=300, blank=True, null=True)

    # ── Categoria e Documento ─────────────────────────────────────────
    categoria_sancao = models.CharField(max_length=100, blank=True, null=True)
    numero_documento = models.CharField(max_length=100, blank=True, null=True)

    # ── Processo ──────────────────────────────────────────────────────
    numero_processo = models.CharField(max_length=100, blank=True, null=True)

    # ── Datas ─────────────────────────────────────────────────────────
    data_inicio_sancao = models.CharField(max_length=20, blank=True, null=True)
    data_final_sancao = models.CharField(max_length=20, blank=True, null=True)
    data_publicacao = models.CharField(max_length=20, blank=True, null=True)
    data_transito_em_julgado = models.CharField(max_length=20, blank=True, null=True)
    data_origem_informacao = models.CharField(max_length=20, blank=True, null=True)

    # ── Publicação ────────────────────────────────────────────────────
    publicacao = models.CharField(max_length=200, blank=True, null=True)
    detalhamento_meio_publicacao = models.CharField(max_length=300, blank=True, null=True)

    # ── Abrangência ───────────────────────────────────────────────────
    abrangencia_sancao = models.CharField(max_length=200, blank=True, null=True)

    # ── Cargo/Função ──────────────────────────────────────────────────
    cargo_efetivo = models.CharField(max_length=100, blank=True, null=True)
    funcao_confianca = models.CharField(max_length=100, blank=True, null=True)

    # ── Órgão ─────────────────────────────────────────────────────────
    orgao_lotacao = models.CharField(max_length=300, blank=True, null=True)
    orgao_sancionador = models.CharField(max_length=300, blank=True, null=True)
    uf_orgao_sancionador = models.CharField(max_length=2, blank=True, null=True)
    esfera_orgao_sancionador = models.CharField(max_length=50, blank=True, null=True)

    # ── Complemento ───────────────────────────────────────────────────
    fundamentacao_legal = models.CharField(max_length=500, blank=True, null=True)
    origem_informacoes = models.CharField(max_length=200, blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)

    # ── Controle ──────────────────────────────────────────────────────
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ceaf_records"
        verbose_name = "CEAF — Registro"
        verbose_name_plural = "CEAF — Registros"

    def __str__(self):
        return f"{self.nome_do_sancionado} ({self.cpf_ou_cnpj_do_sancionado})"
