import pandas as pd
import sys
import os

# ── Configurações ──────────────────────────────────────────────────────────────
CSV_PATH = "resultado_fraude_consolidado.csv"
CHUNK_SIZE = 200_000
ENCODING = "utf-8"

NOMES_ALVO = [
    "odebrecht",
    "andrade gutierrez",
    "camargo correa",
    "utc engenharia",
]

# ── Detecta separador automaticamente ─────────────────────────────────────────
def detectar_separador(path, encoding):
    with open(path, "r", encoding=encoding, errors="replace") as f:
        primeira_linha = f.readline()
    for sep in [",", ";", "\t", "|"]:
        if sep in primeira_linha:
            return sep
    return ","

# ── Leitura e busca em chunks ──────────────────────────────────────────────────
def buscar_nomes(csv_path):
    if not os.path.exists(csv_path):
        print(f"❌ Arquivo não encontrado: {csv_path}")
        sys.exit(1)

    sep = detectar_separador(csv_path, ENCODING)
    print(f"✅ Separador detectado: '{sep}'")

    tamanho_mb = os.path.getsize(csv_path) / (1024 ** 2)
    print(f"📁 Tamanho do arquivo: {tamanho_mb:.0f} MB")
    print(f"🔍 Buscando {len(NOMES_ALVO)} nomes...\n")

    resultados = {nome: [] for nome in NOMES_ALVO}
    total_linhas = 0
    chunk_num = 0
    col_nome = None
    col_classif = None

    try:
        reader = pd.read_csv(
            csv_path,
            sep=sep,
            encoding=ENCODING,
            dtype=str,
            chunksize=CHUNK_SIZE,
            on_bad_lines="skip",
        )

        for chunk in reader:
            chunk_num += 1
            total_linhas += len(chunk)

            chunk.columns = chunk.columns.str.strip().str.lower()

            if chunk_num == 1:
                print(f"📋 Colunas encontradas: {list(chunk.columns)}\n")

                for candidato in ["favorecido", "nome", "razao_social", "nome_favorecido", "fornecedor"]:
                    if candidato in chunk.columns:
                        col_nome = candidato
                        break

                if col_nome is None:
                    print("⚠️  Coluna de nome não identificada automaticamente.")
                    print("    Colunas disponíveis:", list(chunk.columns))
                    sys.exit(1)

                print(f"✅ Coluna de nome usada: '{col_nome}'\n")

                col_classif = (
                    "classificação" if "classificação" in chunk.columns
                    else "classificacao" if "classificacao" in chunk.columns
                    else None
                )

            # Normaliza nome para busca (lowercase, sem acento não é necessário pois fazemos contains)
            nome_normalizado = chunk[col_nome].str.lower().str.strip().fillna("")

            # Filtra anos da Operação Lava Jato (2007-2016)
            mask_ano = pd.to_numeric(chunk["ano"], errors="coerce").between(2007, 2016)
            chunk = chunk[mask_ano]
            nome_normalizado = chunk[col_nome].str.lower().str.strip().fillna("")

            # Filtra apenas classificações alvo
            classif_normalizada = chunk[col_classif].str.lower().str.strip() if col_classif else None
            mask_classif = classif_normalizada.isin({"normal", "suspeita", "alta suspeita"}) if col_classif else pd.Series([True] * len(chunk))

            # Busca por cada nome (contains = busca parcial)
            for nome in NOMES_ALVO:
                mask = nome_normalizado.str.contains(nome, na=False) & mask_classif
                matches = chunk[mask]

                for _, row in matches.iterrows():
                    resultados[nome].append({
                        "favorecido": row[col_nome],
                        "classificação": row[col_classif] if col_classif else "N/A",
                        "linha_aprox": total_linhas - len(chunk) + row.name,
                    })

            if chunk_num % 10 == 0:
                print(f"  ⏳ Processados ~{total_linhas:,} linhas (chunk {chunk_num})...")

    except UnicodeDecodeError:
        print("❌ Erro de encoding. Tente alterar ENCODING para 'latin1' ou 'cp1252'.")
        sys.exit(1)

    # ── Relatório final ────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"✅ Processamento concluído: {total_linhas:,} linhas lidas\n")
    print("📊 RESULTADO POR EMPRESA:")
    print(f"{'='*60}")

    algum_encontrado = False

    for nome in NOMES_ALVO:
        ocorrencias = resultados[nome]
        if ocorrencias:
            algum_encontrado = True
            classifs = [o["classificação"] for o in ocorrencias]
            nomes_encontrados = list({o["favorecido"] for o in ocorrencias})
            print(f"\n✅ ENCONTRADO | '{nome}'")
            print(f"   Ocorrências : {len(ocorrencias)}")
            print(f"   Nomes reais : {nomes_encontrados[:5]}")  # mostra até 5 variações
            print(f"   Classificações: {dict(pd.Series(classifs).value_counts().to_dict())}")
        else:
            print(f"\n❌ NÃO ENCONTRADO | '{nome}'")

    if not algum_encontrado:
        print("\n⚠️  Nenhuma empresa foi encontrada no arquivo.")

    print(f"\n{'='*60}")
    return resultados


if __name__ == "__main__":
    if len(sys.argv) > 1:
        CSV_PATH = sys.argv[1]

    buscar_nomes(CSV_PATH)