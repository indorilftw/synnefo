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

from django.conf import settings as global_settings
from django.utils.translation import ugettext as _
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import HttpResponseRedirect

from astakos.im.util import login_url
from astakos.im.models import AstakosUser, AstakosUserAuthProvider, \
    PendingThirdPartyUser
from astakos.im import settings
from astakos.im.views.target import get_pending_key, \
    handle_third_party_signup, handle_third_party_login, \
    init_third_party_session
from astakos.im.views.decorators import cookie_fix, requires_auth_provider

import astakos.im.messages as astakos_messages
import logging

logger = logging.getLogger(__name__)


def migrate_eppn_to_remote_id(eppn, remote_id):
    """
    Retrieve active and pending accounts that are associated with shibboleth
    using EPPN as the third party unique identifier update them by storing
    REMOTE_USER value instead.
    """
    if eppn == remote_id:
        return

    try:
        provider = AstakosUserAuthProvider.objects.get(module='shibboleth',
                                                       identifier=eppn)
        msg = "Migrating user %r eppn (%s -> %s)"
        logger.info(msg, provider.user.log_display, eppn, remote_id)
        provider.identifier = remote_id
        provider.save()
    except AstakosUserAuthProvider.DoesNotExist:
        pass

    pending_users = \
        PendingThirdPartyUser.objects.filter(third_party_identifier=eppn,
                                             provider='shibboleth')

    for pending in pending_users:
        msg = "Migrating pending user %s eppn (%s -> %s)"
        logger.info(msg, pending.email, eppn, remote_id)
        pending.third_party_identifier = remote_id
        pending.save()

    return remote_id


class Tokens:
    # these are mapped by the Shibboleth SP software
    SHIB_EPPN = "HTTP_EPPN"  # eduPersonPrincipalName
    SHIB_NAME = "HTTP_SHIB_INETORGPERSON_GIVENNAME"
    SHIB_SURNAME = "HTTP_SHIB_PERSON_SURNAME"
    SHIB_CN = "HTTP_SHIB_PERSON_COMMONNAME"
    SHIB_DISPLAYNAME = "HTTP_SHIB_INETORGPERSON_DISPLAYNAME"
    SHIB_EP_AFFILIATION = "HTTP_SHIB_EP_AFFILIATION"
    SHIB_SESSION_ID = "HTTP_SHIB_SESSION_ID"
    SHIB_MAIL = "HTTP_SHIB_MAIL"
    SHIB_REMOTE_USER = "HTTP_REMOTE_USER"


@requires_auth_provider('shibboleth')
@require_http_methods(["GET", "POST"])
@cookie_fix
def login(request,
          template='im/third_party_check_local.html',
          extra_context=None):

    init_third_party_session(request)
    extra_context = extra_context or {}

    tokens = request.META
    third_party_key = get_pending_key(request)

    shibboleth_headers = {}
    for token in dir(Tokens):
        if token == token.upper():
            shibboleth_headers[token] = request.META.get(getattr(Tokens,
                                                                 token),
                                                         'NOT_SET')
            # also include arbitrary shibboleth headers
            for key in request.META.keys():
                if key.startswith('HTTP_SHIB_'):
                    shibboleth_headers[key.replace('HTTP_', '')] = \
                        request.META.get(key)

    # log shibboleth headers
    # TODO: info -> debug
    logger.info("shibboleth request: %r" % shibboleth_headers)

    try:
        eppn = tokens.get(Tokens.SHIB_EPPN, None)
        user_id = tokens.get(Tokens.SHIB_REMOTE_USER)
        fullname, first_name, last_name, email = None, None, None, None
        if global_settings.DEBUG and not eppn:
            user_id = getattr(global_settings, 'SHIBBOLETH_TEST_REMOTE_USER',
                              None)
            eppn = getattr(global_settings, 'SHIBBOLETH_TEST_EPPN', None)
            fullname = getattr(global_settings, 'SHIBBOLETH_TEST_FULLNAME',
                               None)

        if not user_id:
            raise KeyError(_(astakos_messages.SHIBBOLETH_MISSING_USER_ID) % {
                'domain': settings.BASE_HOST,
                'contact_email': settings.CONTACT_EMAIL
            })
        if Tokens.SHIB_DISPLAYNAME in tokens:
            fullname = tokens[Tokens.SHIB_DISPLAYNAME]
        elif Tokens.SHIB_CN in tokens:
            fullname = tokens[Tokens.SHIB_CN]
        if Tokens.SHIB_NAME in tokens:
            first_name = tokens[Tokens.SHIB_NAME]
        if Tokens.SHIB_SURNAME in tokens:
            last_name = tokens[Tokens.SHIB_SURNAME]

        if fullname:
            splitted = fullname.split(' ', 1)
            if len(splitted) == 2:
                first_name, last_name = splitted
        fullname = '%s %s' % (first_name, last_name)

        if not any([first_name, last_name]) and \
                settings.SHIBBOLETH_REQUIRE_NAME_INFO:
            raise KeyError(_(astakos_messages.SHIBBOLETH_MISSING_NAME))

    except KeyError, e:
        # invalid shibboleth headers, redirect to login, display message
        logger.exception(e)
        messages.error(request, e.message)
        return HttpResponseRedirect(login_url(request))

    if settings.SHIBBOLETH_MIGRATE_EPPN:
        migrate_eppn_to_remote_id(eppn, user_id)

    affiliation = tokens.get(Tokens.SHIB_EP_AFFILIATION, 'Shibboleth')
    email = tokens.get(Tokens.SHIB_MAIL, '')
    provider_info = {'eppn': eppn, 'email': email, 'name': fullname,
                     'headers': shibboleth_headers, 'user_id': user_id}

    try:
        return handle_third_party_login(request, 'shibboleth',
                                        user_id, provider_info,
                                        affiliation, third_party_key)
    except AstakosUser.DoesNotExist, e:
        third_party_key = get_pending_key(request)
        user_info = {'affiliation': affiliation,
                     'first_name': first_name,
                     'last_name': last_name,
                     'email': email}
        return handle_third_party_signup(request, user_id, 'shibboleth',
                                         third_party_key,
                                         provider_info,
                                         user_info,
                                         template,
                                         extra_context)
