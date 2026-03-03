"""
IQR detecta outliers individuais
Z-score detecta valores extremos
Testes de normalidade analisam formato global

Usar MAD (Mean Absolute Deviation)

Aplicar Benford
Se houver desvio significativo:
Identificar quais dígitos estão super-representados
Investigar registros associados
Ver se coincidem pelo IQR
Avaliar clusters específicos (órgão, ano, função)
"""

import numpy as np
from scipy.stats import median_abs_deviation

def calculateQuartisIQR(conjunto: list):
    q1 = np.percentile(conjunto, 25)
    q3 = np.percentile(conjunto, 75)
    iqr = q3 - q1
    limits = [(q1 - 1.5*iqr), (q3 + 1.5*iqr)]
    return iqr, limits

def iqrOutlier(value, limits: list):
    inferior, superior = limits
    return 1 if(value < inferior or value > superior) else 0

def zScore(conjunto: list):
    data_mean = np.mean(np.array(conjunto))
    data_std = np.std(np.array(conjunto))

    z_scores = (conjunto - data_mean) / data_std

    return z_scores

def madOutliers(conjunto: list, threshold=3.5):
    data = np.array(conjunto)
    mediana = np.median(data)
    mad = median_abs_deviation(data)

    # Evitar divisão por zero
    if mad == 0:
        return np.zeros(len(data)), []

    modified_z_scores = 0.6745 * (data - mediana) / mad

    mask = np.abs(modified_z_scores) > threshold

    return modified_z_scores, data[mask]

if __name__ == "__main__":
    conjunto = [2, 5, 7, 10, 12, 15, 18, 20, 22, 24, 26, 100]
    print(f"Conjunto: {conjunto}")
    log_conjunto = np.log10(conjunto)
    iqr, limits = calculateQuartisIQR(log_conjunto)
    
    outliers = []
    normal_values = []

    for i in conjunto:
        log_i = np.log10(i)
        flag = iqrOutlier(log_i, limits)
        if flag == 1:
            outliers.append(i)
        else:
            normal_values.append(i)

    print("Normal values:", normal_values)

    print("Outliers IQR:", outliers)

    z_scores = zScore(conjunto)

    z_score_outliers = []
    valores_outliers = []

    mask = np.abs(z_scores) > 3
    valores_outliers = np.array(conjunto)[mask]
    print("Valores outliers Z Scores:", valores_outliers.tolist())

    modified_z, mad_outliers = madOutliers(conjunto)

    print("Valores outliers (MAD):", mad_outliers.tolist())