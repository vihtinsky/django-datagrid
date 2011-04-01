from datagrid.grids import *
from blogango.models import BlogEntry
from django.contrib.auth.models import Group

def grid_data_func(value):
    return value.upper()

def slug_link_func(obj, value):
    # return  args[0]
    return 'http://google.com/404/'

def non_db_col_value(obj):
    return obj.id % 4

class DataGridWithDictonaryData(DataGrid):
    objid = Column("ID", link=True, sortable=True, field_name="id")
    name = Column("Group Name", link=True, sortable=True, expand=True)
    custom = NonDatabaseColumn("Second Title",
                               sortable=True, data_func=non_db_col_value,
                               link=True,
                               extra_sort="id-id/4*4",
                               )
    def __init__(self, request):
        DataGrid.__init__(self, request, Group.objects.values(), "All Groups")
        self.default_sort = "objid"
        self.default_columns = [
            "objid", "name"
        ]

class BlogGrid(DataGrid):
    created_by = Column(sortable=True,
                        link=True,
                        cell_clickable=True,
                        css_class='red')

    created_on = DateTimeColumn("created on",
                                format='d b, Y',
                                sortable=True,
                                link=False)

    created_on_since = DateTimeSinceColumn("created on ",
                                           sortable=True,
                                           db_field='created_on')

    slug = Column("Slug",
                  sortable=False,
                  link=False,
                  link_func=slug_link_func,
                  image_url='/site_media/blogango/images/date_icon.png')

    title = Column("Title",
                   sortable=True,
                   link=False,
                   db_field='title',
                   image_url='http://media.agiliq.com/images/terminal.png',
                   image_width=20,
                   image_height=20,
                   image_alt='foo bar',
                   data_func=grid_data_func)

    blog_title = NonDatabaseColumn("Second Title", sortable=True, link=True, data_func=non_db_col_value)
    col1 = NonDatabaseColumn(sortable=True, link=True, data_func=non_db_col_value)

def blog_grid(request):
    posts = BlogEntry.objects.all()
    blog_grid = BlogGrid(request=request, queryset=posts, title='Blog Grid View')
    blog_grid = DataGridWithDictonaryData(request=request)

    return blog_grid.render_to_response('blog_grid/blog_grid.html', {'blog_grid': blog_grid})
