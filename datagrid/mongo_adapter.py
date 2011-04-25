import copy
import pymongo
import pymongo.cursor
import logging

from adapters import QuerySetAdapter, ManagerAdapter


class MongoQuerySetAdapter(QuerySetAdapter):
    """Decorator to use mongo query with datagrid"""
    def __init__(self, mongo_cursor, pk = "id"):
        if not isinstance(mongo_cursor, pymongo.cursor.Cursor):
            raise Exception("Argument should be pymongo.cursor.Cursor")
        self.model = ManagerAdapter()
        self.model.objects = self
        self.pk = pk
        self.mongo_cursor = mongo_cursor

    def __getitem__(self, items):
        if isinstance(items,int):
            i = self.mongo_cursor[items]
            return Struct(self.pk, **i)
        self.mongo_cursor = self.mongo_cursor.__getitem__(items)
        return self

    def distinct(self, true_or_false=True):
        return self

    def filter_pk(self, ids_list):
        pk = self.pk
        code = "%s.indexOf[this.%s] != -1 " % (ids_list, pk)
        mongo_cursor = self.mongo_cursor.where(code)
        print code
        a = [Struct(self.pk, **i) for i in mongo_cursor]
        return a

    def count(self):
        if isinstance(self.mongo_cursor, list):
            return len(self.mongo_cursor)
        return self.mongo_cursor.count()

    def filter(self, *args, **kwargs):
        return self

    def values_list(self, *fields, **kwargs):
        if fields:
            field = fields[0]
            if field == "pk":
                field = self.pk
        else:
            return self
        cursor = copy.copy(self.mongo_cursor)
        list = [i[field] for i in cursor]
        return list

    def __len__(self):
        if isinstance(self.mongo_cursor, list):
            return len(self.mongo_cursor)
        return self.mongo_cursor.count()

    def order_by(self, *field_names):
        print field_names
        asc = pymongo.ASCENDING
        desc = pymongo.DESCENDING
        sort = []
        if not field_names:
            return self
        for index in field_names:
            if index.startswith("-"):
                index = index[1:]
                sort.append((index, desc))
            else:
                sort.append((index, asc))
        self.mongo_cursor = self.mongo_cursor.sort(sort)
        return self


    def extra_sort(self, *field_names):
        logging.error("""Sort by nonDb column with MongoQuerySetAdapter
            not supported""")
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
    def __init__(self, pk="id", **entries):
        self.__dict__["id"] = entries[pk]
        self.__dict__.update(entries)
