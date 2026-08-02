from .library_query import SortSpec


class SortEngine:
    COLUMNS = {"title", "artist", "album", "genre", "bpm", "key", "rating", "duration", "date_added"}
    DIRECTIONS = {"asc", "desc"}

    def build(self, column, direction="asc"):
        column = column.lower()
        direction = direction.lower()
        if column not in self.COLUMNS or direction not in self.DIRECTIONS:
            raise ValueError("Columna o dirección de ordenamiento no permitida.")
        return SortSpec(column, direction)
