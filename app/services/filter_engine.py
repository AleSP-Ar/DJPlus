from .library_query import FilterCriteria


class FilterEngine:
    def build(self, **values):
        criteria = FilterCriteria(**{key: value for key, value in values.items() if value is not None})
        if criteria.bpm_min is not None and criteria.bpm_max is not None and criteria.bpm_min > criteria.bpm_max:
            raise ValueError("El BPM mínimo no puede ser mayor que el máximo.")
        if criteria.rating_min is not None and criteria.rating_max is not None and criteria.rating_min > criteria.rating_max:
            raise ValueError("El rating mínimo no puede ser mayor que el máximo.")
        return criteria
