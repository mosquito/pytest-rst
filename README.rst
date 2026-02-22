pytest-rst
==========

.. image:: https://github.com/mosquito/pytest-rst/workflows/tests/badge.svg
   :target: https://github.com/mosquito/pytest-rst/actions?query=workflow%3Atests
   :alt: Tests

.. image:: https://img.shields.io/pypi/v/pytest-rst.svg
   :target: https://pypi.python.org/pypi/pytest-rst/
   :alt: Latest Version

.. image:: https://img.shields.io/pypi/wheel/pytest-rst.svg
   :target: https://pypi.python.org/pypi/pytest-rst/

.. image:: https://img.shields.io/pypi/pyversions/pytest-rst.svg
   :target: https://pypi.python.org/pypi/pytest-rst/

.. image:: https://img.shields.io/pypi/l/pytest-rst.svg
   :target: https://pypi.python.org/pypi/pytest-rst/

A pytest plugin that discovers and runs Python code blocks embedded in
reStructuredText files as test cases.

Installation
------------

.. code-block:: bash

    pip install pytest-rst

Usage
-----

Add a ``:name:`` option starting with ``test_`` to any Python code block in
your ``.rst`` files, and pytest will collect and run it automatically:

.. code-block:: rst

    .. code-block:: python
        :name: test_example

        assert 2 + 2 == 4

.. code-block:: python
    :name: test_example

    assert 2 + 2 == 4

Code blocks without a ``test_`` name are ignored:

.. code-block:: rst

    .. code-block:: python

        # this will not be collected by pytest
        assert False

.. code-block:: python

    # this will not be collected by pytest
    assert False

Fixtures
--------

Code blocks can request pytest fixtures using the ``:fixtures:`` option.
Fixtures are injected into the code block's namespace.

Single fixture:

.. code-block:: rst

    .. code-block:: python
        :name: test_file_ops
        :fixtures: tmp_path

        p = tmp_path / "test.txt"
        p.write_text("hello")
        assert p.read_text() == "hello"

.. code-block:: python
    :name: test_file_ops
    :fixtures: tmp_path

    p = tmp_path / "test.txt"
    p.write_text("hello")
    assert p.read_text() == "hello"

Multiple fixtures (comma-separated):

.. code-block:: rst

    .. code-block:: python
        :name: test_capture
        :fixtures: tmp_path, capsys

        print("hello")
        captured = capsys.readouterr()
        assert captured.out == "hello\n"

Any pytest fixture works, including custom ones defined in ``conftest.py``.

Versioning
----------

This software follows `Semantic Versioning`_.

.. _Semantic Versioning: http://semver.org/
