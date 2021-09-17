.. image:: https://coveralls.io/repos/github/mosquito/pytest-rst/badge.svg?branch=master
   :target: https://coveralls.io/github/mosquito/pytest-rst
   :alt: Coveralls

.. image:: https://github.com/aiokitchen/pytest-rst/workflows/tox/badge.svg
   :target: https://github.com/aiokitchen/pytest-rst/actions?query=workflow%3Atox
   :alt: Actions

.. image:: https://img.shields.io/pypi/v/pytest-rst.svg
   :target: https://pypi.python.org/pypi/pytest-rst/
   :alt: Latest Version

.. image:: https://img.shields.io/pypi/wheel/pytest-rst.svg
   :target: https://pypi.python.org/pypi/pytest-rst/

.. image:: https://img.shields.io/pypi/pyversions/pytest-rst.svg
   :target: https://pypi.python.org/pypi/pytest-rst/

.. image:: https://img.shields.io/pypi/l/pytest-rst.svg
   :target: https://pypi.python.org/pypi/pytest-rst/


pytest-rst run python tests in ReStructuredText
===============================================

Code block must have ``:name:`` attribute starts with ``test_``.

Example
-------

This block will running as a pytest test-case:

.. code-block:: rst

    .. code-block:: python
        :name: test_first

        assert True

.. code-block:: python
    :name: test_first

    assert True


This block just not running:

.. code-block:: rst

    .. code-block:: python

        # not a test
        assert False

.. code-block:: python

    # not a test
    assert False


Versioning
----------

This software follows `Semantic Versioning`_


.. _Semantic Versioning: http://semver.org/
