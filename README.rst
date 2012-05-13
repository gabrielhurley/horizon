=======
Horizon
=======

Horizon is a Django app aimed at providing an extensible framework for building
dashboards from reusable components. This version is a fork from the upstream
OpenStack Dashboard project without all the OpenStack integration.

Development
===========

For local development, first create a virtualenv for the project.
In the ``tools`` directory there is a script to create one for you:

  $ python tools/install_venv.py

Alternatively, the ``run_tests.sh`` script will also install the environment
for you and then run the full test suite to verify everything is installed
and functioning correctly.

Building Contributor Documentation
==================================

Horizon's documentation is written by contributors, for contributors.

The source is maintained in the ``docs/source`` folder using
`reStructuredText`_ and built by `Sphinx`_

.. _reStructuredText: http://docutils.sourceforge.net/rst.html
.. _Sphinx: http://sphinx.pocoo.org/

* Building Automatically::

    $ ./run_tests.sh --docs

Results are in the `docs/build/html` directory
