from pathlib import Path
from collections.abc import Iterator
from textwrap import dedent

import pytest

from pytest_rst import (
    CodeBlock,
    _make_rst_test_func,
    _parse_fixtures,
    get_indent,
    parse_code_blocks,
)


INDENT_CASES = [
    ["foo\n", 0],
    ["foo", 0],
    ["\tbar", 0],
    [" foo ", 1],
    [" foo", 1],
    ["  foo ", 2],
    ["   foo ", 3],
    [" ", -1],
    ["  ", -1],
    [" \n", -1],
]


@pytest.fixture()
def sample_fp() -> Iterator:
    path = Path(__file__).parent / "sample.rst"
    with open(path) as fp:
        yield fp


@pytest.mark.parametrize("line,indent", INDENT_CASES)
def test_get_indent(line, indent):
    assert get_indent(line) == indent


def test_parser(sample_fp):
    blocks = list(parse_code_blocks(sample_fp))
    assert blocks == [
        CodeBlock(
            start_line=5,
            params=(("name", "test_first"),),
            syntax="python",
            lines=("assert True",),
        ),
        CodeBlock(
            start_line=11,
            params=(("name", "test_second"),),
            syntax="python",
            lines=("assert True", "assert not False", "assert 1"),
        ),
        CodeBlock(
            start_line=18,
            params=(("name", "test_third"),),
            syntax="python",
            lines=(
                "def test_func():",
                "",
                "    return 42",
                "",
                "assert test_func() == 42",
            ),
        ),
        CodeBlock(
            start_line=33,
            params=(("name", "test_first"),),
            syntax="python",
            lines=("assert True",),
        ),
        CodeBlock(
            start_line=38,
            params=(),
            syntax="python",
            lines=(
                ".. code-block:: python",
                "    .. code-block:: python",
                "        .. code-block:: python",
                "            .. code-block:: python",
                "                .. code-block:: python",
            ),
        ),
        CodeBlock(
            start_line=50,
            params=(
                ("name", "test_with_fixture"),
                ("fixtures", "tmp_path"),
            ),
            syntax="python",
            lines=(
                'p = tmp_path / "test.txt"',
                'p.write_text("hello")',
                'assert p.read_text() == "hello"',
            ),
        ),
    ]


PARSE_FIXTURES_CASES = [
    ("", ()),
    ("tmp_path", ("tmp_path",)),
    ("tmp_path, capsys", ("tmp_path", "capsys")),
    ("  tmp_path , capsys  ", ("tmp_path", "capsys")),
    (",,,", ()),
]


@pytest.mark.parametrize("value,expected", PARSE_FIXTURES_CASES)
def test_parse_fixtures(value, expected):
    assert _parse_fixtures(value) == expected


def test_fixtures_parsed_from_block(sample_fp):
    blocks = list(parse_code_blocks(sample_fp))
    fixture_block = [b for b in blocks if dict(b.params).get("fixtures")]
    assert len(fixture_block) == 1
    assert dict(fixture_block[0].params)["fixtures"] == "tmp_path"


def test_single_fixture(pytester):
    pytester.makefile(
        ".rst",
        test_fix=dedent("""\
            Example:

            .. code-block:: python
                :name: test_tmp
                :fixtures: tmp_path

                p = tmp_path / "hello.txt"
                p.write_text("world")
                assert p.read_text() == "world"

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_tmp*PASSED*"])
    assert result.ret == 0


def test_multiple_fixtures(pytester):
    pytester.makefile(
        ".rst",
        test_multi=dedent("""\
            Example:

            .. code-block:: python
                :name: test_multi_fix
                :fixtures: tmp_path, capsys

                print("hello")
                p = tmp_path / "f.txt"
                p.write_text("ok")
                assert p.read_text() == "ok"
                captured = capsys.readouterr()
                assert captured.out == "hello\\n"

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_multi_fix*PASSED*"])
    assert result.ret == 0


def test_mixed_plain_and_fixture_blocks(pytester):
    pytester.makefile(
        ".rst",
        test_mixed=dedent("""\
            Plain:

            .. code-block:: python
                :name: test_plain

                assert 1 + 1 == 2

            With fixture:

            .. code-block:: python
                :name: test_fixtured
                :fixtures: tmp_path

                assert tmp_path.is_dir()

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(
        [
            "*test_plain*PASSED*",
            "*test_fixtured*PASSED*",
        ]
    )
    assert result.ret == 0


def test_custom_fixture(pytester):
    pytester.makeconftest(
        dedent("""\
        import pytest

        @pytest.fixture()
        def greeting():
            return "hello world"
    """)
    )
    pytester.makefile(
        ".rst",
        test_custom=dedent("""\
            Custom:

            .. code-block:: python
                :name: test_greet
                :fixtures: greeting

                assert greeting == "hello world"

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_greet*PASSED*"])
    assert result.ret == 0


def test_nonexistent_fixture(pytester):
    pytester.makefile(
        ".rst",
        test_bad=dedent("""\
            Bad:

            .. code-block:: python
                :name: test_missing
                :fixtures: no_such_fixture

                pass

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*ERROR*"])
    assert result.ret != 0


def test_backward_compat_no_fixtures(pytester):
    pytester.makefile(
        ".rst",
        test_compat=dedent("""\
            Compat:

            .. code-block:: python
                :name: test_ok

                x = 42
                assert x == 42

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_ok*PASSED*"])
    assert result.ret == 0


# --- _make_rst_test_func unit tests ---


def test_make_rst_test_func_signature():
    code = compile("x = a + b", "<test>", "exec")
    fn = _make_rst_test_func(code, ("a", "b"))
    import inspect

    params = list(inspect.signature(fn).parameters)
    assert params == ["a", "b"]


def test_make_rst_test_func_injects_fixtures():
    code = compile(
        "result.append(val * 2)",
        "<test>",
        "exec",
    )
    fn = _make_rst_test_func(code, ("val", "result"))
    collected: list[int] = []
    fn(val=21, result=collected)
    assert collected == [42]


def test_make_rst_test_func_sets_dunder_name():
    code = compile(
        "result.append(__name__)",
        "<test>",
        "exec",
    )
    fn = _make_rst_test_func(code, ("result",))
    collected: list[str] = []
    fn(result=collected)
    assert collected == ["__main__"]


# --- Additional integration tests ---


def test_fixture_monkeypatch(pytester):
    pytester.makefile(
        ".rst",
        test_mp=dedent("""\
            Monkeypatch:

            .. code-block:: python
                :name: test_monkeypatch_env
                :fixtures: monkeypatch

                import os
                monkeypatch.setenv("MY_TEST_VAR", "hello")
                assert os.environ["MY_TEST_VAR"] == "hello"

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_monkeypatch_env*PASSED*"])
    assert result.ret == 0


def test_fixture_with_yield_teardown(pytester):
    pytester.makeconftest(
        dedent("""\
        import pytest

        @pytest.fixture()
        def tracked(tmp_path):
            marker = tmp_path / "setup.txt"
            marker.write_text("setup")
            yield "value"
            teardown_marker = tmp_path / "teardown.txt"
            teardown_marker.write_text("teardown")
    """)
    )
    pytester.makefile(
        ".rst",
        test_yield=dedent("""\
            Yield fixture:

            .. code-block:: python
                :name: test_use_tracked
                :fixtures: tracked

                assert tracked == "value"

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_use_tracked*PASSED*"])
    assert result.ret == 0


def test_fixture_assertion_failure_reported(pytester):
    pytester.makefile(
        ".rst",
        test_fail=dedent("""\
            Fail:

            .. code-block:: python
                :name: test_will_fail
                :fixtures: tmp_path

                assert tmp_path / "nope.txt" == "wrong"

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_will_fail*FAILED*"])
    assert result.ret != 0


def test_fixture_runtime_error_reported(pytester):
    pytester.makefile(
        ".rst",
        test_err=dedent("""\
            Error:

            .. code-block:: python
                :name: test_will_error
                :fixtures: tmp_path

                raise RuntimeError("boom")

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(
        [
            "*test_will_error*FAILED*",
            "*RuntimeError: boom*",
        ]
    )
    assert result.ret != 0


def test_empty_fixtures_param_uses_plain_item(pytester):
    pytester.makefile(
        ".rst",
        test_empty=dedent("""\
            Empty:

            .. code-block:: python
                :name: test_empty_fix
                :fixtures:

                assert 1 + 1 == 2

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_empty_fix*PASSED*"])
    assert result.ret == 0


def test_multiple_fixture_blocks_in_same_file(pytester):
    pytester.makefile(
        ".rst",
        test_two=dedent("""\
            First:

            .. code-block:: python
                :name: test_fix_a
                :fixtures: tmp_path

                (tmp_path / "a.txt").write_text("a")
                assert (tmp_path / "a.txt").read_text() == "a"

            Second:

            .. code-block:: python
                :name: test_fix_b
                :fixtures: tmp_path

                (tmp_path / "b.txt").write_text("b")
                assert (tmp_path / "b.txt").read_text() == "b"

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(
        [
            "*test_fix_a*PASSED*",
            "*test_fix_b*PASSED*",
        ]
    )
    assert result.ret == 0


def test_fixture_tmp_path_is_unique_per_block(pytester):
    pytester.makefile(
        ".rst",
        test_uniq=dedent("""\
            A:

            .. code-block:: python
                :name: test_path_a
                :fixtures: tmp_path

                (tmp_path / "marker.txt").write_text(str(tmp_path))

            B:

            .. code-block:: python
                :name: test_path_b
                :fixtures: tmp_path

                assert not (tmp_path / "marker.txt").exists()

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(
        [
            "*test_path_a*PASSED*",
            "*test_path_b*PASSED*",
        ]
    )
    assert result.ret == 0


def test_rst_prefix_option_with_fixtures(pytester):
    pytester.makefile(
        ".rst",
        test_prefix=dedent("""\
            Prefix:

            .. code-block:: python
                :name: check_prefixed
                :fixtures: tmp_path

                assert tmp_path.is_dir()

            .. code-block:: python
                :name: test_skipped_by_prefix
                :fixtures: tmp_path

                assert tmp_path.is_dir()

            End.
        """),
    )
    result = pytester.runpytest(
        "-v",
        "--rst-prefix",
        "check_",
    )
    result.stdout.fnmatch_lines(["*check_prefixed*PASSED*"])
    assert "test_skipped_by_prefix" not in result.stdout.str()
    assert result.ret == 0


def test_scoped_fixture(pytester):
    pytester.makeconftest(
        dedent("""\
        import pytest

        call_count = 0

        @pytest.fixture(scope="session")
        def counter():
            global call_count
            call_count += 1
            return call_count
    """)
    )
    pytester.makefile(
        ".rst",
        test_scope=dedent("""\
            A:

            .. code-block:: python
                :name: test_scope_a
                :fixtures: counter

                assert counter == 1

            B:

            .. code-block:: python
                :name: test_scope_b
                :fixtures: counter

                assert counter == 1

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(
        [
            "*test_scope_a*PASSED*",
            "*test_scope_b*PASSED*",
        ]
    )
    assert result.ret == 0


def test_autouse_fixture_with_fixture_block(pytester):
    pytester.makeconftest(
        dedent("""\
        import pytest

        @pytest.fixture(autouse=True)
        def auto_env(monkeypatch):
            monkeypatch.setenv("RST_AUTO", "yes")
    """)
    )
    pytester.makefile(
        ".rst",
        test_auto=dedent("""\
            Autouse:

            .. code-block:: python
                :name: test_autouse_env
                :fixtures: tmp_path

                import os
                assert os.environ.get("RST_AUTO") == "yes"
                assert tmp_path.is_dir()

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_autouse_env*PASSED*"])
    assert result.ret == 0


def test_fixture_request(pytester):
    pytester.makefile(
        ".rst",
        test_req=dedent("""\
            Request:

            .. code-block:: python
                :name: test_has_request
                :fixtures: request

                assert request.node is not None

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_has_request*PASSED*"])
    assert result.ret == 0


def test_fixture_tmp_path_factory(pytester):
    pytester.makefile(
        ".rst",
        test_tpf=dedent("""\
            Factory:

            .. code-block:: python
                :name: test_tmp_path_factory
                :fixtures: tmp_path_factory

                p = tmp_path_factory.mktemp("data")
                assert p.is_dir()

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_tmp_path_factory*PASSED*"])
    assert result.ret == 0


def test_fixture_with_imports_in_code(pytester):
    pytester.makefile(
        ".rst",
        test_imp=dedent("""\
            Imports:

            .. code-block:: python
                :name: test_imports_and_fixtures
                :fixtures: tmp_path

                import json
                data = {"key": "value"}
                p = tmp_path / "data.json"
                p.write_text(json.dumps(data))
                assert json.loads(p.read_text()) == data

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_imports_and_fixtures*PASSED*"])
    assert result.ret == 0


def test_fixture_dependent_fixtures(pytester):
    pytester.makeconftest(
        dedent("""\
        import pytest

        @pytest.fixture()
        def base_value():
            return 10

        @pytest.fixture()
        def doubled(base_value):
            return base_value * 2
    """)
    )
    pytester.makefile(
        ".rst",
        test_dep=dedent("""\
            Dependent:

            .. code-block:: python
                :name: test_dependent
                :fixtures: doubled

                assert doubled == 20

            End.
        """),
    )
    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*test_dependent*PASSED*"])
    assert result.ret == 0
