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

from scipy.stats import iqr

def calculateIQR(conjunto: list):
    computed = iqr(conjunto)
    return computed

if __name__ == "__main__":
    result = calculateIQR([2, 5, 7, 10, 12, 15, 18])
    print(result)