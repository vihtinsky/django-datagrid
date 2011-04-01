class ManagerAdapter(object):
    objects=None

class QuerySetAdapter(object):
    def distinct(self, true_or_false=True):
        return self

class DictionaryQuerySetAdapter(QuerySetAdapter):
    """Decorator to use datagrids with list of dictonaries"""
    def __init__(self, list):
        self.model = ManagerAdapter()
        self.model.objects = self
        self.list = list

    def __getitem__(self, items):
        if isinstance(items,int):
            i = self.list[items]
            return Struct(**i)
        self.list = self.list.__getitem__(items)
        return self

    def count(self):
        return len(self.list)

    def filter(self, *args, **kwargs):
        return self

    def values_list(self, *fields, **kwargs):
        if fields:
            field = fields[0]
            if field == "pk":
                field = "id"
        else:
            return self
        list = [i[field] for i in self.list]
        return list

    def __len__(self):
        return len(self.list)

    def order_by(self, *field_names):
        if not field_names:
            return self
        index = field_names[0]
        reverse = False
        if index.startswith("-"):
            reverse = True
            index = index[1:]
        self.list = sorted(self.list,
                               key=lambda item : item[index],
                               reverse=reverse)
        return self


class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)
