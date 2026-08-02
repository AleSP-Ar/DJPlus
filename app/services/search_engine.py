from .library_query import SearchCriteria


class SearchEngine:
    def build(self, **values):
        return SearchCriteria(**{key: value for key, value in values.items() if value is not None})
