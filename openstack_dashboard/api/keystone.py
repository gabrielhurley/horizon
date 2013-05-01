# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2012 Openstack, LLC
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

import logging
import urlparse

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from openstack_auth.backend import KEYSTONE_CLIENT_ATTR

from horizon import exceptions

from openstack_dashboard.api import base


LOG = logging.getLogger(__name__)
DEFAULT_ROLE = None

# Set up our data structure for managing Keystone API versions.
#
# The structure should contain both an "active" version which will be
# set by the keystoneclient method below, and "supported" versions which
# contain all the necessary imports for that version.
VERSIONS = {
    "preferred": None,
    "active": None,
    "supported": {}
}

# Import from oldest to newest so that "preferred" takes correct precedence.
try:
    from keystoneclient.v2_0 import client as keystone_client_v2
    VERSIONS["preferred"] = "v2.0"
    VERSIONS["supported"]["v2.0"] = {
        "client": keystone_client_v2
    }
except ImportError:
    pass

try:
    from keystoneclient.v3 import client as keystone_client_v3
    VERSIONS["preferred"] = "v3"
    VERSIONS["supported"]["v3"] = {
        "client": keystone_client_v3
    }
except ImportError:
    pass


class Service(base.APIDictWrapper):
    """ Wrapper for a dict based on the service data from keystone. """
    _attrs = ['id', 'type', 'name']

    def __init__(self, service, *args, **kwargs):
        super(Service, self).__init__(service, *args, **kwargs)
        self.url = service['endpoints'][0]['internalURL']
        self.host = urlparse.urlparse(self.url).hostname
        self.region = service['endpoints'][0]['region']
        self.disabled = None

    def __unicode__(self):
        if(self.type == "identity"):
            return _("%(type)s (%(backend)s backend)") \
                     % {"type": self.type, "backend": keystone_backend_name()}
        else:
            return self.type

    def __repr__(self):
        return "<Service: %s>" % unicode(self)


def _get_endpoint_url(request, endpoint_type, catalog=None):
    if getattr(request.user, "service_catalog", None):
        url = base.url_for(request,
                           service_type='identity',
                           endpoint_type=endpoint_type)
    else:
        auth_url = getattr(settings, 'OPENSTACK_KEYSTONE_URL')
        url = request.session.get('region_endpoint', auth_url)

    # TODO: When the Service Catalog no longer contains API versions
    # in the endpoints this can be removed.
    bits = urlparse.urlparse(url)
    root = "://".join((bits.scheme, bits.netloc))
    url = "/".join((root, VERSIONS["active"]))

    return url


def _get_active_version():
    if VERSIONS["active"] is not None:
        return VERSIONS["supported"][VERSIONS["active"]]
    key = getattr(settings, "OPENSTACK_API_VERSIONS", {}).get("identity")
    if key is None:
        # TODO: support API version discovery here; we'll leave the setting in
        # as a way of overriding the latest available version.
        key = VERSIONS["preferred"]
    VERSIONS["active"] = key
    return VERSIONS["supported"][VERSIONS["active"]]


def keystoneclient(request, admin=False):
    """Returns a client connected to the Keystone backend.

    Several forms of authentication are supported:

        * Username + password -> Unscoped authentication
        * Username + password + tenant id -> Scoped authentication
        * Unscoped token -> Unscoped authentication
        * Unscoped token + tenant id -> Scoped authentication
        * Scoped token -> Scoped authentication

    Available services and data from the backend will vary depending on
    whether the authentication was scoped or unscoped.

    Lazy authentication if an ``endpoint`` parameter is provided.

    Calls requiring the admin endpoint should have ``admin=True`` passed in
    as a keyword argument.

    The client is cached so that subsequent API calls during the same
    request/response cycle don't have to be re-authenticated.
    """
    user = request.user
    if admin:
        if not user.is_superuser:
            raise exceptions.NotAuthorized
        endpoint_type = 'adminURL'
    else:
        endpoint_type = getattr(settings,
                                'OPENSTACK_ENDPOINT_TYPE',
                                'internalURL')

    # Take care of client connection caching/fetching a new client.
    # Admin vs. non-admin clients are cached separately for token matching.
    cache_attr = "_keystoneclient_admin" if admin else KEYSTONE_CLIENT_ATTR
    if hasattr(request, cache_attr) and (not user.token.id
            or getattr(request, cache_attr).auth_token == user.token.id):
        LOG.debug("Using cached client for token: %s" % user.token.id)
        conn = getattr(request, cache_attr)
    else:
        api_version = _get_active_version()
        endpoint = _get_endpoint_url(request, endpoint_type)
        insecure = getattr(settings, 'OPENSTACK_SSL_NO_VERIFY', False)
        LOG.debug("Creating a new keystoneclient connection to %s." % endpoint)
        remote_addr = request.environ.get('REMOTE_ADDR', '')
        conn = api_version['client'].Client(token=user.token.id,
                                            endpoint=endpoint,
                                            original_ip=remote_addr,
                                            insecure=insecure,
                                            debug=settings.DEBUG)
        setattr(request, cache_attr, conn)
    return conn


def _get_project_manager(*args, **kwargs):
    if VERSIONS['active'] == "v2.0":
        manager = keystoneclient(*args, **kwargs).tenants
    else:
        manager = keystoneclient(*args, **kwargs).projects
    return manager


def tenant_create(request, name, description=None, enabled=None, domain=None):
    manager = _get_project_manager(request, admin=True)
    if VERSIONS["active"] == "v2.0":
        return manager.create(name, description, enabled)
    else:
        return manager.create(name, domain,
                              description=description,
                              enabled=enabled)


def tenant_get(request, project, admin=False):
    manager = _get_project_manager(request, admin=True)
    return manager.get(project)


def tenant_delete(request, project):
    manager = _get_project_manager(request, admin=True)
    return manager.delete(project)


def tenant_list(request, domain=None, user=None):
    manager = _get_project_manager(request, admin=True)
    if VERSIONS["active"] == "v2.0":
        return manager.list()
    else:
        return manager.list(domain=domain, user=user)


def tenant_update(request, project, name=None, description=None,
                  enabled=None, domain=None):
    manager = _get_project_manager(request, admin=True)
    if VERSIONS["active"] == "v2.0":
        return manager.update(project, name, description, enabled)
    else:
        return manager.update(project, name=name, description=description,
                              enabled=enabled, domain=domain)


def user_list(request, project=None, domain=None, group=None):
    if VERSIONS["active"] == "v2.0":
        kwargs = {"tenant_id": project}
    else:
        kwargs = {
            "project": project,
            "domain": domain,
            "group": group
        }
    return keystoneclient(request, admin=True).users.list(**kwargs)


def user_create(request, user_id, email, password, tenant_id, enabled):
    return keystoneclient(request, admin=True).users.create(user_id,
                                                            password,
                                                            email,
                                                            tenant_id,
                                                            enabled)


def user_delete(request, user_id):
    keystoneclient(request, admin=True).users.delete(user_id)


def user_get(request, user_id, admin=True):
    return keystoneclient(request, admin=admin).users.get(user_id)


def user_update(request, user, **data):
    return keystoneclient(request, admin=True).users.update(user, **data)


# Legacy method, v2 API only!
def user_update_enabled(request, user_id, enabled):
    return keystoneclient(request, admin=True).users.update_enabled(user_id,
                                                                    enabled)


# Legacy method, v2 API only!
def user_update_password(request, user_id, password, admin=True):
    return keystoneclient(request, admin=admin).users.update_password(user_id,
                                                                      password)


# Legacy method, v2 API only!
def user_update_tenant(request, user_id, tenant_id, admin=True):
    return keystoneclient(request, admin=admin).users.update_tenant(user_id,
                                                                    tenant_id)


def role_list(request):
    """ Returns a global list of available roles. """
    return keystoneclient(request, admin=True).roles.list()


def roles_for_user(request, user, project):
    manager = keystoneclient(request, admin=True).roles
    if VERSIONS["active"] == "v2.0":
        return manager.roles_for_user(user, project)
    else:
        return manager.list(user=user, project=project)


def add_tenant_user_role(request, project=None, user=None, role=None,
                         group=None, domain=None):
    """ Adds a role for a user on a tenant. """
    manager = keystoneclient(request, admin=True).roles
    if VERSIONS["active"] == "v2.0":
        return manager.add_user_role(user, role, project)
    else:
        return manager.grant(role, user=user, project=project,
                             group=group, domain=domain)


def remove_tenant_user_role(request, project=None, user=None, role=None,
                            group=None, domain=None):
    """ Removes a given single role for a user from a tenant. """
    manager = keystoneclient(request, admin=True).roles
    if VERSIONS["active"] == "v2.0":
        return manager.remove_user_role(user, role, project)
    else:
        return manager.revoke(role, user=user, project=project,
                              group=group, domain=domain)


def remove_tenant_user(request, project=None, user=None, domain=None):
    """ Removes all roles from a user on a tenant, removing them from it. """
    client = keystoneclient(request, admin=True)
    roles = client.roles.roles_for_user(user, project)
    for role in roles:
        remove_tenant_user_role(request, user=user, role=role.id,
                                project=project, domain=domain)


def get_default_role(request):
    """
    Gets the default role object from Keystone and saves it as a global
    since this is configured in settings and should not change from request
    to request. Supports lookup by name or id.
    """
    global DEFAULT_ROLE
    default = getattr(settings, "OPENSTACK_KEYSTONE_DEFAULT_ROLE", None)
    if default and DEFAULT_ROLE is None:
        try:
            roles = keystoneclient(request, admin=True).roles.list()
        except:
            roles = []
            exceptions.handle(request)
        for role in roles:
            if role.id == default or role.name == default:
                DEFAULT_ROLE = role
                break
    return DEFAULT_ROLE


def list_ec2_credentials(request, user_id):
    return keystoneclient(request).ec2.list(user_id)


def create_ec2_credentials(request, user_id, tenant_id):
    return keystoneclient(request).ec2.create(user_id, tenant_id)


def get_user_ec2_credentials(request, user_id, access_token):
    return keystoneclient(request).ec2.get(user_id, access_token)


def keystone_can_edit_user():
    backend_settings = getattr(settings, "OPENSTACK_KEYSTONE_BACKEND", {})
    return backend_settings.get('can_edit_user', True)


def keystone_can_edit_project():
    backend_settings = getattr(settings, "OPENSTACK_KEYSTONE_BACKEND", {})
    return backend_settings.get('can_edit_project', True)


def keystone_backend_name():
    if hasattr(settings, "OPENSTACK_KEYSTONE_BACKEND"):
        return settings.OPENSTACK_KEYSTONE_BACKEND['name']
    else:
        return 'unknown'
