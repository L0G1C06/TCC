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

def calculateQuartisIQR(conjunto: list):
    q1 = np.percentile(conjunto, 25)
    q3 = np.percentile(conjunto, 75)
    iqr = q3 - q1
    limits = [(q1 - 1.5*iqr), (q3 + 1.5*iqr)]
    return iqr, limits

def iqrOutlier(value, limits: list):
    inferior, superior = limits
    return 1 if(value < inferior or value > superior) else 0

if __name__ == "__main__":
    conjunto = [2, 5, 7, 10, 12, 15, 18, 20, 22, 24, 26, 100]
    log_conjunto = np.log10(conjunto)
    iqr, limits = calculateQuartisIQR(log_conjunto)
    print("IQR:", iqr)
    print("Limites:", limits)
    
    outliers = []
    normal_values = []

    for i in conjunto:
        log_i = np.log10(i)
        flag = iqrOutlier(log_i, limits)
        if flag == 1:
            outliers.append(i)
        else:
            normal_values.append(i)

    print("Outliers:", outliers)
    print("Normal values:", normal_values)