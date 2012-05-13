# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2012 Nebula, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import datetime
import os

from django import http
from django import test as django_test
from django.conf import settings
from django.contrib.messages.storage import default_storage
from django.core.handlers import wsgi
from django.test.client import RequestFactory
from functools import wraps
import httplib2
import mox

from horizon import context_processors
from horizon import middleware
from horizon import users

from .time import time
from .time import today
from .time import utcnow


# Makes output of failing mox tests much easier to read.
wsgi.WSGIRequest.__repr__ = lambda self: "<class 'django.http.HttpRequest'>"


def create_stubs(stubs_to_create={}):
    if not isinstance(stubs_to_create, dict):
        raise TypeError("create_stub must be passed a dict, but a %s was " \
                "given." % type(stubs_to_create).__name__)

    def inner_stub_out(fn):
        @wraps(fn)
        def instance_stub_out(self):
            for key in stubs_to_create:
                if not (isinstance(stubs_to_create[key], tuple) or \
                        isinstance(stubs_to_create[key], list)):
                    raise TypeError("The values of the create_stub " \
                            "dict must be lists or tuples, but is a %s." %
                            type(stubs_to_create[key]).__name__)

                for value in stubs_to_create[key]:
                    self.mox.StubOutWithMock(key, value)
            return fn(self)
        return instance_stub_out
    return inner_stub_out


class RequestFactoryWithMessages(RequestFactory):
    def get(self, *args, **kwargs):
        req = super(RequestFactoryWithMessages, self).get(*args, **kwargs)
        req.session = []
        req._messages = default_storage(req)
        return req

    def post(self, *args, **kwargs):
        req = super(RequestFactoryWithMessages, self).post(*args, **kwargs)
        req.session = []
        req._messages = default_storage(req)
        return req


class TestCase(django_test.TestCase):
    """
    Specialized base test case class for Horizon which gives access to
    numerous additional features:

      * The ``mox`` mocking framework via ``self.mox``.
      * A set of request context data via ``self.context``.
      * A ``RequestFactory`` class which supports Django's ``contrib.messages``
        framework via ``self.factory``.
      * A ready-to-go request object via ``self.request``.
      * The ability to override specific time data controls for easier testing.
      * Several handy additional assertion methods.
    """
    def setUp(self):
        self.mox = mox.Mox()
        self.factory = RequestFactoryWithMessages()
        self.context = {}

        def fake_conn_request(*args, **kwargs):
            raise Exception("An external URI request tried to escape through "
                            "an httplib2 client. Args: %s, kwargs: %s"
                            % (args, kwargs))

        self._real_conn_request = httplib2.Http._conn_request
        httplib2.Http._conn_request = fake_conn_request

        self._real_horizon_context_processor = context_processors.horizon
        context_processors.horizon = lambda request: self.context

        self._real_get_user_from_request = users.get_user_from_request
        self.request = http.HttpRequest()
        self.request.session = self.client._session()
        middleware.HorizonMiddleware().process_request(self.request)
        os.environ["HORIZON_TEST_RUN"] = "True"

    def tearDown(self):
        self.mox.UnsetStubs()
        httplib2.Http._conn_request = self._real_conn_request
        context_processors.horizon = self._real_horizon_context_processor
        users.get_user_from_request = self._real_get_user_from_request
        self.mox.VerifyAll()
        del os.environ["HORIZON_TEST_RUN"]

    def override_times(self):
        """ Overrides the "current" time with immutable values. """
        now = datetime.datetime.utcnow()
        time.override_time = \
                datetime.time(now.hour, now.minute, now.second)
        today.override_time = datetime.date(now.year, now.month, now.day)
        utcnow.override_time = now
        return now

    def reset_times(self):
        """ Undoes the changes made by ``override_times``. """
        time.override_time = None
        today.override_time = None
        utcnow.override_time = None

    def assertRedirectsNoFollow(self, response, expected_url):
        """
        Asserts that the given response issued a 302 redirect without
        processing the view which is redirected to.
        """
        assert (response.status_code / 100 == 3), \
            "The response did not return a redirect."
        self.assertEqual(response._headers.get('location', None),
                         ('Location', settings.TESTSERVER + expected_url))
        self.assertEqual(response.status_code, 302)

    def assertNoMessages(self, response=None):
        """
        Asserts that no messages have been attached by the ``contrib.messages``
        framework.
        """
        self.assertMessageCount(response, success=0, warn=0, info=0, error=0)

    def assertMessageCount(self, response=None, **kwargs):
        """
        Asserts that the specified number of messages have been attached
        for various message types. Usage would look like
        ``self.assertMessageCount(success=1)``.
        """
        temp_req = self.client.request(**{'wsgi.input': None})
        temp_req.COOKIES = self.client.cookies
        storage = default_storage(temp_req)
        messages = []

        if response is None:
            # To gain early access to the messages we have to decode the
            # cookie on the test client.
            if 'messages' in self.client.cookies:
                message_cookie = self.client.cookies['messages'].value
                messages = storage._decode(message_cookie)
        # Check for messages in the context
        elif hasattr(response, "context") and  "messages" in response.context:
            messages = response.context["messages"]
        # Check for messages attached to the request on a TemplateResponse
        elif hasattr(response, "_request") and hasattr(response._request,
                                                       "_messages"):
            messages = response._request._messages._queued_messages

        # If we don't have messages and we don't expect messages, we're done.
        if not any(kwargs.values()) and not messages:
            return

        # If we expected messages and have none, that's a problem.
        if any(kwargs.values()) and not messages:
            error_msg = "Messages were expected, but none were set."
            assert 0 == sum(kwargs.values()), error_msg

        # Otherwise, make sure we got the expected messages.
        for msg_type, count in kwargs.items():
            msgs = [m.message for m in messages if msg_type in m.tags]
            assert len(msgs) == count, \
                   "%s messages not as expected: %s" % (msg_type.title(),
                                                        ", ".join(msgs))

    def assertNoFormErrors(self, response, context_name="form"):
        """
        Asserts that the response either does not contain a form in it's
        context, or that if it does, that form has no errors.
        """
        context = getattr(response, "context", {})
        if not context or context_name not in context:
            return True
        errors = response.context[context_name]._errors
        assert len(errors) == 0, \
               "Unexpected errors were found on the form: %s" % errors

    def assertFormErrors(self, response, count=0, message=None,
                         context_name="form"):
        """
        Asserts that the response does contain a form in it's
        context, and that form has errors, if count were given,
        it must match the exact numbers of errors
        """
        context = getattr(response, "context", {})
        assert (context and context_name in context), \
            "The response did not contain a form."
        errors = response.context[context_name]._errors
        if count:
            assert len(errors) == count, \
               "%d errors were found on the form, %d expected" % \
               (len(errors), count)
            if message and message not in unicode(errors):
                self.fail("Expected message not found, instead found: %s"
                          % ["%s: %s" % (key, [e for e in field_errors]) for
                             (key, field_errors) in errors.items()])
        else:
            assert len(errors) > 0, "No errors were found on the form"
