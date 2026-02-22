Example 1:

.. code-block:: python
    :name: test_first

    assert True

Example 2:

.. code-block:: python
    :name: test_second
    assert True
    assert not False
    assert 1

.. code-block:: python
    :name: test_third

    def test_func():

        return 42

    assert test_func() == 42

Example 3:

.. note::

    Note example:

    .. code-block:: python
        :name: test_first

        assert True

Example 4:

.. code-block:: python
    .. code-block:: python
        .. code-block:: python
            .. code-block:: python
                .. code-block:: python
                    .. code-block:: python

Example fixture:

.. code-block:: python
    :name: test_with_fixture
    :fixtures: tmp_path

    p = tmp_path / "test.txt"
    p.write_text("hello")
    assert p.read_text() == "hello"

Example 6:

.. code-block:: python
.. code-block:: python

Example 7:

.. code-block::
    test

Example 8:

.. note::

    Note here

    .. code-block::
        test
