from django.core.paginator import Paginator


def paginate_queryset(request, queryset, per_page=10, page_param="page"):
    """Return a page object and query string preserving current filters/search/sort."""
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get(page_param))

    query_params = request.GET.copy()
    query_params.pop(page_param, None)

    return page_obj, query_params.urlencode()
