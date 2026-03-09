class PolarsRow:
    """
    Representa uma linha do Data Lake como objeto com acesso por atributo,
    espelhando o comportamento de uma instância django.db.models.Model.
    """

    def __init__(self, data: dict):
        self._data = data
        for key, value in data.items():
            # Normaliza o nome do atributo: espaços e hífens viram underscore
            attr = key.lower().replace(" ", "_").replace("-", "_")
            object.__setattr__(self, attr, value)

    def __repr__(self):
        pk = self._data.get("id") or self._data.get("cpf") or "..."
        return f"<PolarsRow {pk}>"

    def __getitem__(self, key):
        return self._data[key]

    def to_dict(self) -> dict:
        return self._data