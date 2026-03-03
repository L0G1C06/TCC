INPUT: base_dados (valor, orgao, ano, funcao, ...)

--------------------------------------------------
ETAPA 1 — PRÉ-PROCESSAMENTO
--------------------------------------------------

1. Remover valores nulos
2. Remover valores <= 0
3. X ← coluna VALOR

--------------------------------------------------
ETAPA 2 — DETECÇÃO INDIVIDUAL DE OUTLIERS
--------------------------------------------------

# IQR
4. Q1 ← percentil(X, 25%)
5. Q3 ← percentil(X, 75%)
6. IQR ← Q3 - Q1
7. limites ← [Q1 - 1.5*IQR , Q3 + 1.5*IQR]
8. Marcar OUTLIER_IQR

# Z-score
9. media ← média(X)
10. desvio ← desvio_padrao(X)
11. Calcular Z para cada xi
12. Se |Z| > 3 → OUTLIER_Z

# MAD robusto
13. mediana ← mediana(X)
14. MAD ← mediana(|xi - mediana|)
15. modified_z ← 0.6745*(xi - mediana)/MAD
16. Se |modified_z| > 3.5 → OUTLIER_MAD

--------------------------------------------------
ETAPA 3 — TESTES DE NORMALIDADE
--------------------------------------------------

17. p_shapiro ← teste_shapiro(X)
18. p_ks ← teste_KS(X)

--------------------------------------------------
ETAPA 4 — BENFORD MULTI-DÍGITO
--------------------------------------------------

Para cada valor xi:

19. d1 ← primeiro_digito(xi)
20. d2 ← segundo_digito(xi)
21. d12 ← dois_primeiros_digitos(xi)
22. d_last ← ultimo_digito(xi)

Armazenar vetores:
    D1, D2, D12, DLAST

-----------------------------
4.1 PRIMEIRO DÍGITO
-----------------------------

23. freq_obs_d1 ← frequência(D1)
24. freq_exp_d1[d] ← log10(1 + 1/d)

25. MAD_d1 ← média(|obs - exp|)
26. chi2_d1 ← soma((obs - exp)^2 / exp)

-----------------------------
4.2 SEGUNDO DÍGITO
-----------------------------

27. freq_obs_d2 ← frequência(D2)

28. freq_exp_d2[d] ←
       somatório log10(1 + 1/(10*k + d))
       para k = 1 até 9

29. MAD_d2
30. chi2_d2

-----------------------------
4.3 DOIS PRIMEIROS DÍGITOS
-----------------------------

31. freq_obs_d12 ← frequência(D12)

32. freq_exp_d12[n] ← log10(1 + 1/n)
       para n = 10 até 99

33. MAD_d12
34. chi2_d12

-----------------------------
4.4 ÚLTIMO DÍGITO (uniforme)
-----------------------------

35. freq_obs_last ← frequência(DLAST)

36. freq_exp_last[d] ← 0.1   # uniforme 0-9

37. MAD_last
38. chi2_last

--------------------------------------------------
ETAPA 5 — VERIFICAR DESVIO GLOBAL BENFORD
--------------------------------------------------

39. Se qualquer:
        MAD_d1 > limiar1
     OU MAD_d2 > limiar2
     OU MAD_d12 > limiar3
     OU MAD_last > limiar4
     OU p_chi2 < 0.05

    então BENFORD_DESVIO = verdadeiro

--------------------------------------------------
ETAPA 6 — IDENTIFICAÇÃO DE DÍGITOS SUSPEITOS
--------------------------------------------------

40. Para cada distribuição (d1, d2, d12, last):

        identificar dígitos onde:
            freq_obs > freq_exp + margem

        marcar como DIGITO_SUSPEITO

--------------------------------------------------
ETAPA 7 — MARCAÇÃO POR TRANSAÇÃO
--------------------------------------------------

Para cada transação i:

41. flag_benford_i ← 0

42. Se d1_i ∈ DIGITOS_SUSPEITOS_d1 → flag_benford_i += 1
43. Se d2_i ∈ DIGITOS_SUSPEITOS_d2 → flag_benford_i += 1
44. Se d12_i ∈ DIGITOS_SUSPEITOS_d12 → flag_benford_i += 1
45. Se d_last_i ∈ DIGITOS_SUSPEITOS_last → flag_benford_i += 1

--------------------------------------------------
ETAPA 8 — ANÁLISE POR CLUSTER
--------------------------------------------------

46. Agrupar por (orgao, ano, funcao)

Para cada cluster:

    47. Repetir análise Benford multi-dígito
    48. Calcular taxa de outliers
    49. Calcular MAD do cluster

    50. Se cluster com:
            alto MAD_benford
            E alta taxa de outliers
        marcar CLUSTER_ALTO_RISCO

--------------------------------------------------
ETAPA 9 — SCORE FINAL
--------------------------------------------------

Para cada transação:

51. risco ←
        w1*OUTLIER_IQR
      + w2*OUTLIER_Z
      + w3*OUTLIER_MAD
      + w4*flag_benford_i
      + w5*cluster_alto_risco

52. Normalizar risco ∈ [0,1]

53. Classificar:
        risco >= 0.7 → ALTA SUSPEITA
        0.4 ≤ risco < 0.7 → SUSPEITA
        risco < 0.4 → NORMAL

--------------------------------------------------
OUTPUT
--------------------------------------------------

54. Retornar:

    - Tabela por transação com todas as flags
    - Score final
    - Dígitos suspeitos por nível
    - Métricas Benford (MAD_d1, MAD_d2, MAD_d12, MAD_last)
    - Clusters de risco