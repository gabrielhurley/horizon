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

from django import http
from django.core.urlresolvers import reverse

from horizon import api
from horizon import test

from mox import IgnoreArg, IsA


IMAGES_INDEX_URL = reverse('horizon:nova:images_and_snapshots:index')


class ImageViewTests(test.TestCase):
    def test_image_create_get(self):
        url = reverse('horizon:nova:images_and_snapshots:images:create')
        res = self.client.get(url)
        self.assertTemplateUsed(res,
                               'nova/images_and_snapshots/images/create.html')

    @test.create_stubs({api.glance: ('image_create',)})
    def test_image_create_post(self):
        form_data = {
                'name': 'Ubuntu 11.10',
                'copy_from': 'http://cloud-images.ubuntu.com/releases/'
                            'oneiric/release/ubuntu-11.10-server-cloudimg'
                            '-amd64-disk1.img',
                'disk_format': 'qcow2',
                'minimum_disk': '15',
                'minimum_ram': '512',
                'is_public': '1',
                'method': 'CreateImageForm'
                }

        api.glance.image_create(IsA(http.HttpRequest), **form_data). \
                AndReturn(self.images.first())
        self.mox.ReplayAll()

        url = reverse('horizon:nova:images_and_snapshots:images:create')
        res = self.client.post(url, form_data)

        self.assertNoFormErrors(res)
        self.assertEqual(res.status_code, 302)

    @test.create_stubs({api.glance: ('image_get',)})
    def test_image_detail_get(self):
        image = self.images.first()

        api.glance.image_get(IsA(http.HttpRequest), str(image.id)) \
                                 .AndReturn(self.images.first())
        self.mox.ReplayAll()

        res = self.client.get(
                reverse('horizon:nova:images_and_snapshots:images:detail',
                args=[image.id]))
        self.assertTemplateUsed(res,
                                'nova/images_and_snapshots/images/detail.html')
        self.assertEqual(res.context['image'].name, image.name)

    @test.create_stubs({api.glance: ('image_get',)})
    def test_image_detail_get_with_exception(self):
        image = self.images.first()

        api.glance.image_get(IsA(http.HttpRequest), str(image.id)) \
                  .AndRaise(self.exceptions.glance)
        self.mox.ReplayAll()

        url = reverse('horizon:nova:images_and_snapshots:images:detail',
                      args=[image.id])
        res = self.client.get(url)
        self.assertRedirectsNoFollow(res, IMAGES_INDEX_URL)
