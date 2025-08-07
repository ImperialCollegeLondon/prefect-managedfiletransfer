from enum import Enum


class SortFilesBy(Enum):
    PATH_ASC = "path_asc"
    PATH_DESC = "path_desc"
    SIZE_ASC = "size_asc"
    SIZE_DESC = "size_desc"
    DATE_ASC = "date_asc"
    DATE_DESC = "date_desc"

    def get_sort_by_lambda_tuple(self) -> tuple:
        """
        Returns a tuple of (lambda function, reverse boolean) for sorting.
        The lambda function is used to extract the attribute to sort by,
        and the boolean indicates whether to sort in reverse order.
        """
        switcher = {
            SortFilesBy.PATH_ASC: (lambda x: x.path, False),
            SortFilesBy.PATH_DESC: (lambda x: x.path, True),
            SortFilesBy.SIZE_ASC: (lambda x: x.size, False),
            SortFilesBy.SIZE_DESC: (lambda x: x.size, True),
            SortFilesBy.DATE_ASC: (lambda x: x.last_modified, False),
            SortFilesBy.DATE_DESC: (lambda x: x.last_modified, True),
        }
        return switcher[self]
