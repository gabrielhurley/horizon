from horizon.api import glance
from .utils import TestDataContainer


def data(TEST):
    TEST.images = TestDataContainer()
    TEST.snapshots = TestDataContainer()

    # Snapshots
    snapshot_dict = {'name': u'snapshot',
                     'container_format': u'ami',
                     'id': 3}
    snapshot = glance.Image(snapshot_dict)
    snapshot_properties_dict = {'image_type': u'snapshot'}
    snapshot.properties = glance.ImageProperties(snapshot_properties_dict)
    TEST.snapshots.add(snapshot)

    # Images
    image_properties_dict = {'image_type': u'image'}
    image_dict = {'id': '1',
                  'name': 'public_image',
                  'container_format': 'novaImage'}
    public_image = glance.Image(image_dict)
    public_image.properties = glance.ImageProperties(image_properties_dict)

    image_dict = {'id': '2',
                  'name': 'private_image',
                  'container_format': 'aki'}
    private_image = glance.Image(image_dict)
    private_image.properties = glance.ImageProperties(image_properties_dict)

    TEST.images.add(public_image, private_image)
