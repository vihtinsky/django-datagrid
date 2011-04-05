import copy
import pymongo
import pymongo.cursor
import logging

from adapters import QuerySetAdapter, ManagerAdapter, Struct


class MongoQuerySetAdapter(QuerySetAdapter):
    """Decorator to use mongo query with datagrid"""
    def __init__(self, mongo_cursor, id = "id"):
        if not isinstance(mongo_cursor, pymongo.cursor.Cursor):
            raise Exception("Argument should be pymongo.cursor.Cursor")
        self.model = ManagerAdapter()
        self.model.objects = self
        self.id = id
        self.mongo_cursor = mongo_cursor

    def __getitem__(self, items):
        if isinstance(items,int):
            i = self.mongo_cursor[items]
            return Struct(**i)
        self.mongo_cursor = self.mongo_cursor.__getitem__(items)
        return self

    def distinct(self, true_or_false=True):
        return self

    def filter_pk(self, ids_list):
        id = self.id
        code = "%s.indexOf[this.%s] != -1 " % (ids_list, id)

        mongo_cursor = self.mongo_cursor.where(code)
        a = [Struct(**i) for i in mongo_cursor]
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
                field = self.id
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
        if not field_names:
            return self
        index = field_names[0]
        reverse = pymongo.ASCENDING
        if index.startswith("-"):
            reverse = pymongo.DESCENDING
            index = index[1:]
        self.mongo_cursor = self.mongo_cursor.sort(index, direction=reverse)
        return self

    def extra_sort(self, *field_names):
        logging.error("""Sort by nonDb column with MongoQuerySetAdapter
            not supported""")
        return self

