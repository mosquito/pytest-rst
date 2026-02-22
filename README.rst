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

Code blocks can request pytest fixtures. Fixtures are injected into the code
block's namespace. There are two syntaxes: a directive option and a comment.

Directive option (``:fixtures:``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the ``:fixtures:`` directive option on the code block:

.. code-block:: rst

    .. code-block:: python
        :name: test_file_ops
        :fixtures: tmp_path

        p = tmp_path / "test.txt"
        p.write_text("hello")
        assert p.read_text() == "hello"

Comment syntax (``# fixtures:``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use a ``# fixtures:`` comment inside the code block. This is recommended when
your RST files are uploaded to PyPI, because PyPI's renderer rejects unknown
directive options like ``:fixtures:``.

.. code-block:: python
    :name: test_comment_fixture_readme

    # fixtures: tmp_path
    p = tmp_path / "test.txt"
    p.write_text("hello")
    assert p.read_text() == "hello"

Multiple fixtures (comma-separated):

.. code-block:: python
    :name: test_comment_multi_readme

    # fixtures: tmp_path, capsys
    print("hello")
    p = tmp_path / "f.txt"
    p.write_text("ok")
    assert p.read_text() == "ok"
    captured = capsys.readouterr()
    assert captured.out == "hello\n"

The ``# fixtures:`` line is stripped before execution and does not affect
your code. Both syntaxes can be combined — fixture names are merged.

Any pytest fixture works, including custom ones defined in ``conftest.py``.

Versioning
----------

This software follows `Semantic Versioning`_.

.. _Semantic Versioning: http://semver.org/
