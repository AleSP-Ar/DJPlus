from app.services.filter_engine import FilterEngine


class SmartRuleEngine:
    """Converts persisted AND rules into the existing FilterCriteria contract."""

    def __init__(self, filter_engine=None):
        self.filter_engine = filter_engine or FilterEngine()

    def build_filters(self, rules):
        filters = {}
        for rule in rules:
            self._apply_rule(filters, rule.field, rule.operator, rule.value)
        return self.filter_engine.build(**filters)

    def _apply_rule(self, filters, field, operator, value):
        if field == "bpm":
            self._apply_range(filters, "bpm", operator, value, float)
        elif field == "rating":
            self._apply_range(filters, "rating", operator, value, int)
        elif field == "key" and operator in {"=", "contains"}:
            self._set_once(filters, "key", str(value).strip())
        elif field == "favorite" and operator == "=":
            self._set_once(filters, "favorite", self._as_boolean(value))
        else:
            raise ValueError(f"Regla smart no compatible: {field} {operator}.")

    def _apply_range(self, filters, field, operator, value, converter):
        try:
            converted = converter(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"El valor de {field} no es válido.") from error
        if operator == ">=":
            self._set_once(filters, f"{field}_min", converted)
        elif operator == "<=":
            self._set_once(filters, f"{field}_max", converted)
        elif operator == "=":
            self._set_once(filters, f"{field}_min", converted)
            self._set_once(filters, f"{field}_max", converted)
        else:
            raise ValueError(f"Operador no compatible para {field}: {operator}.")

    def _set_once(self, filters, key, value):
        if key in filters:
            raise ValueError(f"La regla {key} está duplicada.")
        filters[key] = value

    def _as_boolean(self, value):
        normalized = str(value).strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
        raise ValueError("El valor de favorite debe ser true o false.")
