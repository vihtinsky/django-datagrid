from django.conf import settings
from django.contrib.auth.models import SiteProfileNotAvailable
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import InvalidPage, Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.template.defaultfilters import date, timesince
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.views.decorators.cache import cache_control
from django.db.models import Q
from django.db.models.query import QuerySet, ValuesQuerySet
from .adapters import *
import StringIO


class Column(object):
    """
    A column in a data grid.

    The column is the primary component of the data grid. It is used to
    display not only the column header but the HTML for the cell as well.

    Columns can be tied to database fields and can be used for sorting.
    Not all columns have to allow for this, though.

    Columns can have an image, text, or both in the column header. The
    contents of the cells can be instructed to link to the object on the
    row or the data in the cell.
    """
    SORT_DESCENDING = 0
    SORT_ASCENDING = 1
    creation_counter = 0
    def __init__(self, label=None, detailed_label=None,
                 field_name=None, db_field=None,
                 image_url=None, image_width=None, image_height=None,
                 image_alt="", shrink=False, expand=False, sortable=False,
                 default="",
                 default_sort_dir=SORT_DESCENDING, link=False,
                 link_func=None, cell_clickable=False, css_class="", data_func=None):
        self.id = None
        self.datagrid = None
        self.default = default
        self.field_name = field_name
        self.db_field = db_field or field_name
        self.label = label
        # self.detailed_label = detailed_label or self.label
        self.image_url = image_url
        self.image_width = image_width
        self.image_height = image_height
        self.image_alt = image_alt
        self.shrink = shrink
        self.expand = expand
        self.sortable = sortable
        self.default_sort_dir = default_sort_dir
        self.cell_clickable = cell_clickable
        self.link = link
        self.link_func = link_func or \
            (lambda x, y: self.datagrid.link_to_object(x, y))
        self.css_class = css_class
        self.data_func = data_func
        self.creation_counter = Column.creation_counter
        Column.creation_counter += 1

        # State
        self.active = False
        self.last = False
        self.width = 0

    def get_toggle_url(self):
        """
        Returns the URL of the current page with this column's visibility
        toggled.
        """
        columns = [column.id for column in self.datagrid.columns]

        if self.active:
            columns.remove(self.id)
        else:
            columns.append(self.id)

        return "?%scolumns=%s" % (self.get_url_params_except("columns"),
                                  ",".join(columns))
    toggle_url = property(get_toggle_url)

    def get_header(self):
        """
        Displays a sortable column header.

        The column header will include the current sort indicator, if it
        belongs in the sort list. It will also be made clickable in order
        to modify the sort order appropriately, if sortable.
        """
        in_sort = False
        sort_direction = self.SORT_DESCENDING
        sort_primary = False
        sort_url = ""
        unsort_url = ""

        if self.sortable:
            sort_list = self.datagrid.sort_list

            rev_column_id = "-%s" % self.id
            new_column_id = self.id
            cur_column_id = ""
            if self.id in sort_list:
                # This column is currently being sorted in
                # ascending order.
                sort_direction = self.SORT_ASCENDING
                cur_column_id = self.id
                new_column_id = rev_column_id
            elif rev_column_id in sort_list:
                # This column is currently being sorted in
                # descending order.
                sort_direction = self.SORT_DESCENDING
                cur_column_id = rev_column_id
                new_column_id = self.id

            if cur_column_id:
                in_sort = True
                sort_primary = (sort_list[0] == cur_column_id)

            url_prefix = "?%ssort=" % self.get_url_params_except("sort",
                                                                 "datagrid-id",
                                                                 "gridonly",
                                                                 "columns")
            unsort = [i for i in sort_list if i !=cur_column_id]
            unsort_url = url_prefix + ','.join(unsort)
            if sort_primary:
                unsort.insert(0, new_column_id)
            else:
                unsort.append(new_column_id)

            if isinstance(self,NonDatabaseColumn):
                if len(unsort)>1:
                    in_sort = False
                sort_url   = url_prefix + new_column_id
            else:
                sort_url   = url_prefix + ",".join(unsort)

        return mark_safe(render_to_string(
            self.datagrid.column_header_template, {
                'MEDIA_URL': settings.MEDIA_URL,
                'column': self,
                'in_sort': in_sort,
                'sort_ascending': sort_direction == self.SORT_ASCENDING,
                'sort_primary': sort_primary,
                'sort_url': sort_url,
                'unsort_url': unsort_url,
            }))
    header = property(get_header)

    def get_url_params_except(self, *params):
        """
        Utility function to return a string containing URL parameters to
        this page with the specified parameter filtered out.
        """
        s = ""

        for key in self.datagrid.request.GET:
            if key not in params:
                s += "%s=%s&" % (key, self.datagrid.request.GET[key])

        return s

    def render_cell(self, obj):
        """
        Renders the table cell containing column data.
        """
        rendered_data = self.render_data(obj)
        css_class = ""
        url = ""

        if self.css_class:
            if callable(self.css_class):
                css_class = self.css_class(obj)
            else:
                css_class = self.css_class

        if self.link:
            try:
                url = self.link_func(obj, rendered_data)
            except AttributeError:
                pass

        self.label = self.label or ' '.join(self.id.split('_')).title()
        return mark_safe(render_to_string(self.datagrid.cell_template, {
            'MEDIA_URL': settings.MEDIA_URL,
            'column': self,
            'css_class': css_class,
            'url': url,
            'data': mark_safe(rendered_data)
        }))

    def render_data(self, obj):
        """
        Renders the column data to a string. This may contain HTML.
        """
        field_names = self.field_name.split('.')
        if len(field_names) > 1:
            field_name = field_names.pop(0)
            value = getattr(obj, field_name)
            if callable(value):
                value = value()
            if value is None:
                #NO further processing is possible, so bailout early.
                return value
            while field_names:
                field_name = field_names.pop(0)
                value = getattr(value, field_name)
                if callable(value):
                    value = value()
                if value is None:
                    #NO further processing is possible, so bailout early.
                    return value
        else:
            # value = getattr(obj, self.field_name)
            value = getattr(obj, self.db_field, self.default)
        if self.data_func:
            value = self.data_func(value)
        if callable(value):
            return value()
        else:
            return value

class NonDatabaseColumn(Column):
    def __init__(self, label="", extra_sort=False, *args, **kwargs):
        Column.__init__(self, label, *args, **kwargs)
        self.db_field = False
        self.extra_sort = extra_sort
    def render_data(self, obj):
        if self.data_func:
            return self.data_func(obj)
        return self.label

class DateTimeColumn(Column):
    """
    A column that renders a date or time.
    """
    def __init__(self, label, format=None, sortable=True, *args, **kwargs):
        Column.__init__(self, label, sortable=sortable, *args, **kwargs)
        self.format = format

    def render_data(self, obj):
        # return date(getattr(obj, self.field_name), self.format)
        return date(getattr(obj, self.db_field), self.format)

class DateTimeSinceColumn(Column):
    """
    A column that renders a date or time relative to now.
    """
    def __init__(self, label, sortable=True, *args, **kwargs):
        Column.__init__(self, label, sortable=sortable, *args, **kwargs)

    def render_data(self, obj):
        # return _("%s ago") % timesince(getattr(obj, self.field_name))
        return _("%s ago") % timesince(getattr(obj, self.db_field))


class DataGrid(object):
    """
    A representation of a list of objects, sorted and organized by
    columns. The sort order and column lists can be customized. allowing
    users to view this data however they prefer.

    This is meant to be subclassed for specific uses. The subclasses are
    responsible for defining one or more column types. It can also set
    one or more of the following optional variables:

        * 'title':                  The title of the grid.
        * 'profile_sort_field':     The variable name in the user profile
                                    where the sort order can be loaded and
                                    saved.
        * 'profile_columns_field":  The variable name in the user profile
                                    where the columns list can be loaded and
                                    saved.
        * 'paginate_by':            The number of items to show on each page
                                    of the grid. The default is 50.
        * 'paginate_orphans':       If this number of objects or fewer are
                                    on the last page, it will be rolled into
                                    the previous page. The default is 3.
        * 'page':                   The page to display. If this is not
                                    specified, the 'page' variable passed
                                    in the URL will be used, or 1 if that is
                                    not specified.
        * 'listview_template':      The template used to render the list view.
                                    The default is 'datagrid/listview.html'
        * 'column_header_template': The template used to render each column
                                    header. The default is
                                    'datagrid/column_header.html'
        * 'cell_template':          The template used to render a cell of
                                    data. The default is 'datagrid/cell.html'
        * 'optimize_sorts':         Whether or not to optimize queries when
                                    using multiple sorts. This can offattr_metaer a
                                    speed improvement, but may need to be
                                    turned off for more advanced querysets
                                    (such as when using extra()).
                                    The default is True.
    """
    def __init__(self, request, queryset, title="", extra_context={},
                 optimize_sorts=True, listview_template='datagrid/listview.html',
                 column_header_template='datagrid/column_header.html', cell_template='datagrid/cell.html'):
        self.request = request
        if isinstance(queryset, QuerySetAdapter):
            self.queryset = queryset
        elif isinstance(queryset, list):
            self.queryset = DictionaryQuerySetAdapter(queryset)
        elif isinstance(queryset,QuerySet):
            self.queryset = DjangoQuerySetAdapter(queryset)
        elif isinstance(queryset, ValuesQuerySet):
            self.queryset = DjangoQuerySetAdapter(queryset)
        else:
            raise Exception("Unsupported Query Type")

        self.rows = []
        self.columns = []
        self.all_columns = []
        self.db_field_map = {}
        self.paginator = None
        self.page = None
        self.sort_list = None
        self.state_loaded = False
        self.page_num = 0
        self.id = None
        self.extra_context = dict(extra_context)
        self.optimize_sorts = optimize_sorts

        if not hasattr(request, "datagrid_count"):
            request.datagrid_count = 0

        self.id = "datagrid-%s" % request.datagrid_count
        request.datagrid_count += 1

        # Customizable variables
        # self.title = title
        self.grid_header = title
        self.profile_sort_field = None
        self.profile_columns_field = None
        self.paginate_by = 10
        self.paginate_orphans = 3
        self.listview_template = listview_template
        self.column_header_template = column_header_template
        self.cell_template = cell_template


        for attr in dir(self):
            column = getattr(self, attr)
            if isinstance(column, Column):
                self.all_columns.append(column)
                column.datagrid = self
                column.id = attr

                # Reset the column.
                column.active = False
                column.last = False
                column.width = 0

                if not column.field_name:
                    column.field_name = column.id

                if not column.db_field and \
                  not isinstance(column, NonDatabaseColumn):
                    column.db_field = column.field_name
                if column.db_field:
                    self.db_field_map[column.id] = column.db_field

        self.all_columns.sort(key=lambda x: x.creation_counter)
        self.columns = self.all_columns

        # self.default_columns = [el.label or ' '.join(el.id.split()).title() for el in self.all_columns]#TODO:FOR now
        # self.default_sort = self.default_columns[0]
        self.default_sort = self.all_columns[0].id

        #Get the meta fields
        meta = getattr(self, 'Meta', None)
        page_size = request.GET.get('page_size', None)
        if page_size:
            try:
                self.paginate_by = int(page_size)
                if self.paginate_by < self.paginate_orphans:
                    #Special case, because in this case other values will result in weird result
                    self.paginate_orphans = 0
            except ValueError:
                pass

        #Handle controls
        self.pagination_control_widget = getattr(meta, 'pagination_control_widget', False)
        self.get_pdf_link = getattr(meta, 'get_pdf_link', False)
        self.get_csv_link = getattr(meta, 'get_csv_link', False)
        self.filter_fields = getattr(meta, 'filter_fields', [])
        self.search_fields = getattr(meta, 'search_fields', [])
        self.filtering_options = {}
        if self.filter_fields:
            filtering_options = {}
            #TODO: This is very costly for large querysets so we may want to cache this, or do this in SQL
            for field in self.filter_fields:
                filtering_options[field] = set([getattr(el, field) for el in queryset])
            self.filtering_options = filtering_options



    def load_state(self):
        """
        Loads the state of the datagrid.

        This will retrieve the user-specified or previously stored
        sorting order and columns list, as well as any state a subclass
        may need.
        """

        if self.state_loaded:
            return

        profile_sort_list = None
        profile_columns_list = None
        profile = None
        profile_dirty = False

        # Get the saved settings for this grid in the profile. These will
        # work as defaults and allow us to determine if we need to save
        # the profile.
        if self.request.user.is_authenticated():
            try:
                profile = self.request.user.get_profile()

                if self.profile_sort_field:
                    profile_sort_list = \
                        getattr(profile, self.profile_sort_field, None)

                if self.profile_columns_field:
                    profile_columns_list = \
                        getattr(profile, self.profile_columns_field, None)
            except SiteProfileNotAvailable:
                pass
            except ObjectDoesNotExist:
                pass


        columns = self.all_columns


        expand_columns = []
        normal_columns = []

        for colname in columns:
            try:
                column = getattr(self, colname.id)
            except AttributeError:
                # The user specified a column that doesn't exist. Skip it.
                continue

            if column not in self.columns:
                self.columns.append(column)
            column.active = True

            if column.expand:
                # This column is requesting all remaining space. Save it for
                # later so we can tell how much to give it. Each expanded
                # column will count as two normal columns when calculating
                # the normal sized columns.
                expand_columns.append(column)
            elif column.shrink:
                # Make this as small as possible.
                column.width = 0
            else:
                # We'll divide the column widths equally after we've built
                # up the lists of expanded and normal sized columns.
                normal_columns.append(column)

        self.columns[-1].last = True

        # Try to figure out the column widths for each column.
        # We'll start with the normal sized columns.
        total_pct = 100

        # Each expanded column counts as two normal columns.
        normal_column_width = total_pct / (len(self.columns) +
                                           len(expand_columns))

        for column in normal_columns:
            column.width = normal_column_width
            total_pct -= normal_column_width

        if len(expand_columns) > 0:
            expanded_column_width = total_pct / len(expand_columns)
        else:
            expanded_column_width = 0

        for column in expand_columns:
            column.width = expanded_column_width


        # Now get the sorting order for the columns.
        sort_str = self.request.GET.get('sort', profile_sort_list)
        if not sort_str:
            sort_str = self.default_sort
        if sort_str:
            self.sort_list = sort_str.split(',')
        else:
            self.sort_list = []


        # A subclass might have some work to do for loading and saving
        # as well.
        if self.load_extra_state(profile):
            profile_dirty = True

        self.state_loaded = True

        # Fetch the list of objects and have it ready.
        self.precompute_objects()


    def load_extra_state(self, profile):
        """
        Loads any extra state needed for this grid.

        This is used by subclasses that may have additional data to load
        and save. This should return True if any profile-stored state has
        changed, or False otherwise.
        """
        return False

    def precompute_objects(self):
        """
        Builds the queryset and stores the list of objects for use in
        rendering the datagrid.
        """
        query = self.queryset
        use_select_related = False
        # Generate the actual list of fields we'll be sorting by
        sort_list = []
        extra_sort_list = []
        for sort_item in self.sort_list:
            if sort_item[0] == "-":
                base_sort_item = sort_item[1:]
                prefix = "-"
            else:
                base_sort_item = sort_item
                prefix = ""

            if sort_item and base_sort_item in self.db_field_map:
                db_field = self.db_field_map[base_sort_item]
                sort_list.append(prefix + db_field)

                # Lookups spanning tables require that we query from those
                # tables. In order to keep things simple, we'll just use
                # select_related so that we don't have to figure out the
                # table relationships. We only do this if we have a lookup
                # spanning tables.
                if '.' in db_field:
                    use_select_related = True
            else:
                column = getattr(self,base_sort_item)
                if column.extra_sort:
                    extra_sort_list.append({sort_item:column.extra_sort})

        if extra_sort_list:
            query = query.extra_sort(*extra_sort_list)

        if sort_list:
            query = query.order_by(*sort_list)
        if not ( sort_list or extra_sort_list):
            query = query.order_by()





        self.paginator = Paginator(query, self.paginate_by,
                                           self.paginate_orphans)
        page_num = self.request.GET.get('page', 1)

        # Accept either "last" or a valid page number.
        if page_num == "last":
            page_num = self.paginator.num_pages

        try:
            self.page = self.paginator.page(page_num)
        except InvalidPage:
            raise Http404

        self.rows = []
        self.rows_raw = []
        id_list = None

        if self.optimize_sorts and len(sort_list) > 0:
            # This can be slow when sorting by multiple columns. If we
            # have multiple items in the sort list, we'll request just the
            # IDs and then fetch the actual details from that.
            id_list = list(self.page.object_list.distinct().values_list(
                'pk', flat=True))
            # Make sure to unset the order. We can't meaningfully order these
            # results in the query, as what we really want is to keep it in
            # the order specified in id_list, and we certainly don't want
            # the database to do any special ordering (possibly slowing things
            # down). We'll set the order properly in a minute.
            self.page.object_list = self.post_process_queryset(
                self.queryset.filter_pk(id_list))
        if use_select_related:
            self.page.object_list = \
                self.page.object_list.select_related(depth=1)

        if id_list:
            # The database will give us the items in a more or less random
            # order, since it doesn't know to keep it in the order provided by
            # the ID list. This will place the results back in the order we
            # expect.
            index = dict([(id, pos) for (pos, id) in enumerate(id_list)])
            object_list = [None] * len(id_list)
            for obj in list(self.page.object_list):
                object_list[index[obj.id]] = obj
        else:
            # Grab the whole list at once. We know it won't be too large,
            # and it will prevent one query per row.
            if isinstance(self.page.object_list, ValuesQuerySet):
                object_list = [ Struct(**i) for i in self.page.object_list ]
            else:
                object_list = list(self.page.object_list)

        for obj in object_list:
            self.rows.append({
                'object': obj,
                'cells': [column.render_cell(obj) for column in self.columns],
                'data': [column.render_data(obj) for column in self.columns],
            })

    def post_process_queryset(self, queryset):
        """
        Processes a QuerySet after the initial query has been built and
        pagination applied. This is only used when optimizing a sort.

        By default, this just returns the existing queryset. Custom datagrid
        subclasses can override this to add additional queries (such as
        subqueries in an extra() call) for use in the cell renderers.

        When optimize_sorts is True, subqueries (using extra()) on the initial
        QuerySet passed to the datagrid will be stripped from the final
        result. This function can be used to re-add those subqueries.
        """
        return queryset

    def handle_search(self):
        if not self.search_fields:
            return
        query = self.request.GET.get('q', None)
        if not query:
            return
        query_criteria=Q(id=-1)
        for field in self.search_fields:
            field = field+"__icontains"
            query_criteria  = query_criteria | Q(**{field:query})
        self.queryset = self.queryset.filter(query_criteria)

    def handle_filter(self):
        queryset = self.queryset
        if not self.filter_fields:
            return
        for field in self.filter_fields:
            query = self.request.GET.get(field, None)
            if query:
                self.queryset = queryset.filter(**{field: query})



    def render_listview(self):
        """
        Renders the standard list view of the grid.

        This can be called from templates.
        """
        self.handle_search()
        self.handle_filter()
        self.load_state()
        context = {
            'datagrid': self,
            'request': self.request,
            'is_paginated': self.page.has_other_pages(),
            'results_per_page': self.paginate_by,
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
            'page': self.page.number,
            'next': self.page.next_page_number(),
            'previous': self.page.previous_page_number(),
            'last_on_page': self.page.end_index(),
            'first_on_page': self.page.start_index(),
            'pages': self.paginator.num_pages,
            'hits': self.paginator.count,
            'page_range': self.paginator.page_range,
            'pagination_control_widget': self.pagination_control_widget,
            'get_pdf_link': self.get_pdf_link,
            'get_csv_link': self.get_csv_link,
            'filter_fields': self.filter_fields,
            'search_fields': self.search_fields,
            'filtering_options': self.filtering_options.items(),
        }


        context.update(self.extra_context)

        return mark_safe(render_to_string(self.listview_template,
            RequestContext(self.request, context)))

    @cache_control(no_cache=True, no_store=True, max_age=0,
                   must_revalidate=True)
    def render_listview_to_response(self):
        """
        Renders the listview to a response, preventing caching in the
        process.
        """
        return HttpResponse(unicode(self.render_listview()))

    def render_to_response(self, template_name, extra_context={}):
        """
        Renders a template containing this datagrid as a context variable.
        """
        self.handle_search()
        self.handle_filter()
        self.load_state()


        # If the caller is requesting just this particular grid, return it.
        if self.request.GET.get('gridonly', False) and \
           self.request.GET.get('datagrid-id', None) == self.id:
            return self.render_listview_to_response()

        context = {
            'datagrid': self
        }
        context.update(extra_context)
        context.update(self.extra_context)
        if self.request.GET.get('is_pdf', None):
            import ho.pisa as pisa
            file_data = render_to_string('datagrid/as_pdf.pdf', context)
            myfile = StringIO.StringIO()
            pisa.CreatePDF(file_data, myfile)
            myfile.seek(0)
            response =  HttpResponse(myfile, mimetype='application/pdf')
            response['Content-Disposition'] = 'attachment; filename=data.pdf'
            return response
        elif self.request.GET.get('is_csv', None):
            file_data = render_to_string('datagrid/as_csv.csv', context)
            response =  HttpResponse(file_data, mimetype='text.csv')
            response['Content-Disposition'] = 'attachment; filename=data.csv'
            return response


        return render_to_response(template_name, RequestContext(self.request,
                                                                context))

    @staticmethod
    def link_to_object(obj, value):
        return obj.get_absolute_url()

    @staticmethod
    def link_to_value(obj, value):
        return value.get_absolute_url()
