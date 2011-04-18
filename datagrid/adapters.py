"""Adapters to use different data source with grid.Datagrid besides
django.db.models.query.QuerySet"""

import logging


def cmp_to_key(mycmp):
    """Python 2.6 implementation of Python 2.7 `functools.cmp_to_key`"""
    class K(object):
        def __init__(self, obj, *args):
            self.obj = obj
        def __lt__(self, other):
            return mycmp(self.obj, other.obj) < 0
        def __gt__(self, other):
            return mycmp(self.obj, other.obj) > 0
        def __eq__(self, other):
            return mycmp(self.obj, other.obj) == 0
        def __le__(self, other):
            return mycmp(self.obj, other.obj) <= 0
        def __ge__(self, other):
            return mycmp(self.obj, other.obj) >= 0
        def __ne__(self, other):
            return mycmp(self.obj, other.obj) != 0
    return K


class ManagerAdapter(object):
    """Adapter for Django model Manager. Used in DictionaryQuerySetAdapter"""

    objects = None


class QuerySetAdapter(object):
    """Base class for all adapters. Used in __init__ of grid.Datagrid """
    pass


class DjangoQuerySetAdapter(QuerySetAdapter):
    """Adapter for Django queryset used in grid.DataGrid"""

    def __init__(self, subject):
        self.__subject = subject

    def __getattr__(self, name):
        return getattr(self.__subject, name)

    def filter_pk(self, ids_list):
        return self.__subject.model.objects.filter(pk__in=ids_list).order_by()

    def extra_sort(self, *field_names):
        if not field_names:
            return self
        field = field_names[0]
        if field.keys()[0].startswith("-"):
            f = field.keys()[0]
            select = {f[1:]: field[f]}
            self.__subject = self.__subject.extra(select=select)
        else:
            self.__subject = self.__subject.extra(select=field)

        self.__subject = self.__subject.extra(order_by=field.keys())
        return self.__subject


class DictionaryQuerySetAdapter(QuerySetAdapter):
    """Adapter for list of dictonaries"""

    def __init__(self, objects_list):
        self.model = ManagerAdapter()
        self.model.objects = self
        self.objects_list = objects_list

    def __getitem__(self, items):
        if isinstance(items, int):
            i = self.objects_list[items]
            return Struct(**i)
        self.objects_list = self.objects_list.__getitem__(items)
        return self

    def distinct(self, true_or_false=True):
        return self

    def count(self):
        return len(self.objects_list)

    def filter_pk(self, ids_list):
        return self

    def values_list(self, *fields, **kwargs):
        if fields:
            field = fields[0]
            if field == "pk":
                field = "id"
        else:
            return self
        obj_list = [i[field] for i in self.objects_list]
        return obj_list

    def __len__(self):
        return len(self.objects_list)

    def sort_using_cmp(self, sort_keys, reverse):
        asc = reverse['asc']

        def dict_compare(x, y):
            for index in sort_keys:
                if x[index] > y[index]:
                    ret = 1 if index in asc else -1
                    return ret
                if x[index] < y[index]:
                    ret = -1 if index in asc else 1
                    return ret
            return 0

        return cmp_to_key(dict_compare)

    def order_by(self, *field_names):
        if not field_names:
            return self
        sort_keys = []
        reverse = {}

        for field in field_names:
            if field.startswith("-"):
                sort_keys.append(field[1:])
                reverse["desc"] = reverse.get("desc", [])
                reverse["desc"].append(field)
            else:
                sort_keys.append(field)
                reverse["asc"] = reverse.get("asc", [])
                reverse["asc"].append(field)

        if len(reverse.keys()) > 1:
            key_func = self.sort_using_cmp(sort_keys, reverse)
        else:
            key_func = lambda item: [item[i] for i in sort_keys]

        self.objects_list = sorted(
            self.objects_list,
            key=key_func,
            reverse=(reverse.keys()[0] == "desc")
        )
        return self

    def extra_sort(self, *field_names):
        logging.error("""Sort by nonDb column with DictionaryQuerySetAdapter
                         not supported. Please add with row to dictionary """)
        return self


class Struct:
    """Object presentation of dictionaries
    >>> d = {'a+b': 'c', 'c': 3}
    >>> s = Struct(**d)
    >>> getattr(s,'a+b')
    'c'
    >>> s.c
    3
    """
    def __init__(self, **entries):
        self.__dict__.update(entries)
