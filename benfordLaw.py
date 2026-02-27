import numpy as np
import math
from collections import Counter
import random
from scipy.stats import chi2

# -------------------------
# 1️⃣ Gerar dados naturais (log-normal)
# -------------------------

def gerar_dados_naturais(qtd=1000):
    """
    Gera valores financeiros simulados (distribuição log-normal).
    Naturalmente tende a seguir Benford.
    """
    dados = np.random.lognormal(mean=8, sigma=1.0, size=qtd)
    return list(dados)


# -------------------------
# 2️⃣ Inserir fraude
# -------------------------

def inserir_fraude(dados, percentual_fraude=0.15, digito_forcado=9):
    """
    Força uma porcentagem dos valores a começarem com um dígito específico.
    """
    qtd_fraude = int(len(dados) * percentual_fraude)
    
    for i in random.sample(range(len(dados)), qtd_fraude):
        valor = dados[i]
        novo_valor = float(str(digito_forcado) + str(int(valor))[1:])
        dados[i] = novo_valor
        
    return dados


# -------------------------
# 3️⃣ Benford
# -------------------------

def benford_prob(d):
    return math.log10(1 + (1/d))

def primeiro_digito(n):
    return int(str(int(n))[0])

def analisar_benford(amostra, titulo="ANÁLISE"):

    primeiros = [primeiro_digito(n) for n in amostra if n > 0]
    total = len(primeiros)
    freq_obs = Counter(primeiros)

    print(f"\n{'='*40}")
    print(titulo)
    print('='*40)

    chi_quadrado = 0

    for d in range(1, 10):
        observado = freq_obs.get(d, 0)
        esperado = total * benford_prob(d)

        chi_quadrado += ((observado - esperado) ** 2) / esperado

        print(f"Dígito {d}: Obs={observado:4d} | Esp={esperado:7.2f}")

    print("\nQui-Quadrado:", round(chi_quadrado, 2))

    graus_liberdade = 8
    alpha = 0.05

    valor_critico = chi2.ppf(1 - alpha, graus_liberdade)
    print(f"Valor critico: {valor_critico}")

    if chi_quadrado > valor_critico:
        print("🚨 POSSÍVEL ANOMALIA DETECTADA")
    else:
        print("✅ Compatível com Benford")


# -------------------------
# 4️⃣ Execução
# -------------------------

if __name__ == "__main__":

    # Dados naturais
    dados_naturais = gerar_dados_naturais(1000)
    analisar_benford(dados_naturais, "DADOS NATURAIS")

    # Inserindo fraude
    dados_fraudados = inserir_fraude(dados_naturais.copy(), percentual_fraude=0.20, digito_forcado=9)
    analisar_benford(dados_fraudados, "DADOS COM FRAUDE")