# Copyright (C) 2010-2014 GRNET S.A.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django.http import HttpResponse, HttpResponseRedirect
from django.utils.encoding import smart_str

from objpool.http import PooledHTTPConnection

from synnefo.lib import join_urls

from .utils import fix_header, forward_header

import urlparse

# We use proxy to delegate requests to another domain. Sending host specific
# headers (Host, Cookie) may cause confusion to the server we proxy to.
#
# http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.10
# Connection and MUST NOT be communicated by proxies over further connections
EXCLUDE_HEADERS = ['Host', 'Cookie', 'Connection', 'X-Forwarded-Host']


def proxy(request, proxy_base=None, target_base=None, redirect=False):
    kwargs = {}

    if None in (proxy_base, target_base):
        m = "proxy() needs both proxy_base and target_base argument not None"
        raise AssertionError(m)

    # Get strings from lazy objects
    proxy_base = str(proxy_base)
    target_base = str(target_base)

    parsed = urlparse.urlparse(target_base)
    target_path = '/' + parsed.path.strip('/')
    proxy_base = proxy_base.strip('/')

    # prepare headers
    headers = dict(map(lambda (k, v): fix_header(k, v),
                   filter(lambda (k, v): forward_header(k),
                          request.META.iteritems())))

    # set X-Forwarded-For, if already set, pass it through, otherwise set it
    # to the current request remote address
    source_ip = request.META.get('REMOTE_ADDR', None)
    if source_ip and 'X-Forwarded-For' not in headers:
        headers['X-Forwarded-For'] = source_ip

    # request.META remains cleanup
    for k in headers.keys():
        if '_' in k:
            headers.pop(k)

    for k in EXCLUDE_HEADERS:
        headers.pop(k, None)

    kwargs['headers'] = headers
    kwargs['body'] = request.body

    path = smart_str(request.path, encoding='utf-8').lstrip('/')
    if not path.startswith(proxy_base):
        m = "request path '{0}' does not start with proxy_base '{1}'"
        m = m.format(path, proxy_base)
        raise AssertionError(m)
    path = path.replace(proxy_base, '', 1)

    # redirect to target instead of proxing
    if redirect:
        redirect_url = join_urls(target_base, path)
        qs = request.GET.urlencode()
        return HttpResponseRedirect('?'.join([redirect_url, qs]))

    path = join_urls(target_path, path)
    with PooledHTTPConnection(parsed.netloc, parsed.scheme) as conn:
        conn.request(
            request.method,
            '?'.join([path, request.GET.urlencode()]), **kwargs)
        response = conn.getresponse()

        # turn httplib.HttpResponse to django.http.Response
        length = response.getheader('content-length', None)
        data = response.read(length)
        status = int(response.status)
        django_http_response = HttpResponse(data, status=status)
        # do we need to exclude any headers here?
        for name, value in response.getheaders():
            django_http_response[name] = value
        return django_http_response
