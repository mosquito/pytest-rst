from pathlib import Path
from collections.abc import Iterator
from textwrap import dedent

import pytest

from pytest_rst import parse_code_blocks, CodeBlock, get_indent, _parse_fixtures


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
    fixture_block = [
        b for b in blocks
        if dict(b.params).get("fixtures")
    ]
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
    result.stdout.fnmatch_lines([
        "*test_plain*PASSED*",
        "*test_fixtured*PASSED*",
    ])
    assert result.ret == 0


def test_custom_fixture(pytester):
    pytester.makeconftest(dedent("""\
        import pytest

        @pytest.fixture()
        def greeting():
            return "hello world"
    """))
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
