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

from contextlib import contextmanager

import copy
import datetime
import functools

from snf_django.utils.testing import with_settings, override_settings, \
    assertIn, assertGreater, assertRaises

from django.test import Client
from django.test import TestCase
from django.core import mail
from django.http import SimpleCookie, HttpRequest, QueryDict
from django.utils.importlib import import_module
from django.utils import simplejson as json

from astakos.im.activation_backends import *
from astakos.im.views.target.shibboleth import Tokens as ShibbolethTokens
from astakos.im.models import *
from astakos.im import functions
from astakos.im import settings as astakos_settings
from astakos.im import forms
from astakos.im import activation_backends
from astakos.im import auth as auth_functions

from urllib import quote
from datetime import timedelta

from astakos.im import messages
from astakos.im import auth_providers
from astakos.im import quotas
from astakos.im import register

from django.conf import settings


# set some common settings
astakos_settings.EMAILCHANGE_ENABLED = True
astakos_settings.RECAPTCHA_ENABLED = False

settings.LOGGING_SETUP['disable_existing_loggers'] = False

# shortcut decorators to override provider settings
# e.g. shibboleth_settings(ENABLED=True) will set
# ASTAKOS_AUTH_PROVIDER_SHIBBOLETH_ENABLED = True in global synnefo settings
prefixes = {'providers': 'AUTH_PROVIDER_',
            'shibboleth': 'ASTAKOS_AUTH_PROVIDER_SHIBBOLETH_',
            'local': 'ASTAKOS_AUTH_PROVIDER_LOCAL_'}
im_settings = functools.partial(with_settings, astakos_settings)
shibboleth_settings = functools.partial(with_settings,
                                        settings,
                                        prefix=prefixes['shibboleth'])
localauth_settings = functools.partial(with_settings, settings,
                                       prefix=prefixes['local'])


class AstakosTestClient(Client):
    pass


class ShibbolethClient(AstakosTestClient):
    """
    A shibboleth agnostic client.
    """
    VALID_TOKENS = filter(lambda x: not x.startswith("_"),
                          dir(ShibbolethTokens))

    def __init__(self, *args, **kwargs):
        self.tokens = kwargs.pop('tokens', {})
        super(ShibbolethClient, self).__init__(*args, **kwargs)

    def set_tokens(self, **kwargs):
        for key, value in kwargs.iteritems():
            key = 'SHIB_%s' % key.upper()
            if key not in self.VALID_TOKENS:
                raise Exception('Invalid shibboleth token')

            self.tokens[key] = value

    def unset_tokens(self, *keys):
        for key in keys:
            key = 'SHIB_%s' % param.upper()
            if key in self.tokens:
                del self.tokens[key]

    def reset_tokens(self):
        self.tokens = {}

    def get_http_token(self, key):
        http_header = getattr(ShibbolethTokens, key)
        return http_header

    def request(self, **request):
        """
        Transform valid shibboleth tokens to http headers
        """
        for token, value in self.tokens.iteritems():
            request[self.get_http_token(token)] = value

        for param in request.keys():
            key = 'SHIB_%s' % param.upper()
            if key in self.VALID_TOKENS:
                request[self.get_http_token(key)] = request[param]
                del request[param]

        return super(ShibbolethClient, self).request(**request)


def get_user_client(username, password="password"):
    client = Client()
    client.login(username=username, password=password)
    return client


def get_local_user(username, **kwargs):
    try:
        return AstakosUser.objects.get(email=username)
    except:
        user = auth_functions.make_local_user(email=username,
                                              has_signed_terms=True)
        user.set_password(kwargs.pop('password', 'password'))

        for key, value in kwargs.iteritems():
            setattr(user, key, value)
        user.save()

        if kwargs.get("is_active", True):
            backend = activation_backends.get_backend()
            backend.verify_user(user, user.verification_code)
            backend.accept_user(user)

        return user


def get_mailbox(email):
    mails = []
    for sent_email in mail.outbox:
        for recipient in sent_email.recipients():
            if email in recipient:
                mails.append(sent_email)
    return mails


def reverse_with_next(next_reverse, base_reverse='login'):
    return reverse(base_reverse) + '?next=%s' % reverse(next_reverse)
