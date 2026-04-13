from ..metrics.last_digit import LastDigitChi2, DigitPreference
from ..base import BenfordFlag


class TestLastDigitChi2:
    def test_conforme_em_distribuicao_uniforme_real(self, last_digit_uniform):
        result = LastDigitChi2().compute(last_digit_uniform)
        assert result.flag == BenfordFlag.CONFORME

    def test_p_value_presente(self, last_digit_uniform):
        result = LastDigitChi2().compute(last_digit_uniform)
        assert result.p_value is not None
        assert 0.0 <= result.p_value <= 1.0

    def test_critico_em_spike_0(self, last_digit_spike_0):
        result = LastDigitChi2().compute(last_digit_spike_0)
        assert result.flag != BenfordFlag.CONFORME


class TestDigitPreference:
    def test_detecta_spike_em_0(self, last_digit_spike_0):
        result = DigitPreference().compute(last_digit_spike_0)
        assert result.flag != BenfordFlag.CONFORME

    def test_detecta_spike_em_5(self, last_digit_spike_5):
        result = DigitPreference().compute(last_digit_spike_5)
        assert result.flag != BenfordFlag.CONFORME

    def test_conforme_em_uniforme(self, last_digit_uniform):
        result = DigitPreference().compute(last_digit_uniform)
        assert result.flag == BenfordFlag.CONFORME