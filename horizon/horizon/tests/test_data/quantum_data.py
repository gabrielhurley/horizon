from .utils import TestDataContainer


def data(TEST):
    TEST.networks = TestDataContainer()
    TEST.ports = TestDataContainer()
    # TODO(gabriel): Move quantum test data into this module after it
    # has been refactored with object wrappers (a la Glance).
