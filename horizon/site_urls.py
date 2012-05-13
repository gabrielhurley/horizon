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

from django.conf.urls.defaults import patterns, url, include


urlpatterns = patterns('horizon.views.auth',
    url(r'home/$', 'user_home', name='user_home')
)

urlpatterns += patterns('',
    url(r'^auth/login$', 'django.contrib.auth.views.login', name="login"),
    url(r'^auth/logout$', 'django.contrib.auth.views.logout', name="logout"),
    url(r'^i18n/setlang/$', 'django.views.i18n.set_language',
        name="set_language"),
    url(r'^i18n/', include('django.conf.urls.i18n')))
