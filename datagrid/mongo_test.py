from datetime import datetime, timedelta
from pymongo import Connection
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.http import HttpRequest

from datagrid.grids import ( Column, DataGrid, DateTimeSinceColumn,
                                NonDatabaseColumn)
from datagrid.adapters import DictionaryQuerySetAdapter
from django.test.testcases import TestCase

def id_mod_4(obj):
    return obj.id % 4

def populate_mongo_db():
    con = Connection()
    db = con['test_datagrids_db']
    db.groups.remove()
    groups = []
    for i in range(1, 100):
        groups.append({'id':i, 'name':"Group %02d" % i})

    db.groups.insert(groups)
class DataGridWithMongoCursor(DataGrid):
    objid = Column("ID", link=True, sortable=True, field_name="id")
    name = Column("Group Name", link=True, sortable=True, expand=True)
    custom = NonDatabaseColumn("Second Title",
                               sortable=True, link=True)
    def __init__(self, request):
        con = Connection()
        db = con['test_datagrids_db']

        DataGrid.__init__(self, request,
                            DictionaryQuerySetAdapter(list(db.groups.find())),
                            "All Groups")
        self.default_sort = "objid"
        self.default_columns = [
            "objid", "name"
        ]


class MongoDataGridTest(TestCase):
    grid_class = DataGridWithMongoCursor
    def setUp(self):
        self.old_auth_profile_module = getattr(settings, "AUTH_PROFILE_MODULE",
                                               None)
        settings.AUTH_PROFILE_MODULE = None
        populate_mongo_db()
        self.user = User(username="testuser")
        self.request = HttpRequest()
        self.request.user = self.user
        self.datagrid = self.grid_class(self.request)

    def tearDown(self):
        settings.AUTH_PROFILE_MODULE = self.old_auth_profile_module

    def testRender(self):
        """Testing basic datagrid rendering"""
        self.datagrid.render_listview()

    def testRenderToResponse(self):
        """Testing rendering datagrid to HTTPResponse"""
        self.datagrid.render_listview_to_response()

    def testSortAscending(self):
        """Testing datagrids with ascending sort"""
        self.request.GET['sort'] = "name,objid"
        self.datagrid.load_state()

        self.assertEqual(self.datagrid.sort_list, ["name", "objid"])
        self.assertEqual(len(self.datagrid.rows), self.datagrid.paginate_by)
        self.assertEqual(self.datagrid.rows[0]['object'].name, "Group 01")
        self.assertEqual(self.datagrid.rows[1]['object'].name, "Group 02")
        self.assertEqual(self.datagrid.rows[2]['object'].name, "Group 03")

        # Exercise the code paths when rendering
        self.datagrid.render_listview()

    def testSortDescending(self):
        """Testing datagrids with descending sort"""
        self.request.GET['sort'] = "-name"
        self.datagrid.load_state()

        self.assertEqual(self.datagrid.sort_list, ["-name"])
        self.assertEqual(len(self.datagrid.rows), self.datagrid.paginate_by)
        self.assertEqual(self.datagrid.rows[0]['object'].name, "Group 99")
        self.assertEqual(self.datagrid.rows[1]['object'].name, "Group 98")
        self.assertEqual(self.datagrid.rows[2]['object'].name, "Group 97")

        # Exercise the code paths when rendering
        self.datagrid.render_listview()

    def testSortNoDbAscending(self):
        """Testing datagrids with ascending sort"""
        self.request.GET['sort'] = "custom"
        self.datagrid.load_state()
        self.assertEqual(self.datagrid.sort_list, ["custom"])
        self.assertEqual(len(self.datagrid.rows), self.datagrid.paginate_by)
        self.assertEqual(self.datagrid.rows[0]['object'].name, "Group 04")
        self.assertEqual(self.datagrid.rows[1]['object'].name, "Group 08")
        self.assertEqual(self.datagrid.rows[2]['object'].name, "Group 12")

        # Exercise the code paths when rendering
        self.datagrid.render_listview()

    def testSortNoDbDescending(self):
        """Testing datagrids with ascending sort"""
        self.request.GET['sort'] = "-custom"
        self.datagrid.load_state()
        self.assertEqual(self.datagrid.sort_list, ["-custom"])
        self.assertEqual(len(self.datagrid.rows), self.datagrid.paginate_by)
        self.assertEqual(self.datagrid.rows[0]['object'].name, "Group 03")
        self.assertEqual(self.datagrid.rows[1]['object'].name, "Group 07")
        self.assertEqual(self.datagrid.rows[2]['object'].name, "Group 11")

        # Exercise the code paths when rendering
        self.datagrid.render_listview()

