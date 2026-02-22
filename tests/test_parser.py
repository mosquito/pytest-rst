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


# --- Parser edge cases: indentation, formatting, structure ---


def _parse(text):
    """Parse RST text and return code blocks.

    Appends a terminator line because the parser only yields a block
    when a lower-indent line follows it.
    """
    from io import StringIO
    return list(parse_code_blocks(StringIO(dedent(text) + "\n.\n")))


class TestParserIndentation:
    def test_no_blank_line_between_params_and_code(self):
        blocks = _parse("""\
            .. code-block:: python
                :name: test_no_blank
                assert True
        """)
        assert len(blocks) == 1
        assert blocks[0].lines == ("assert True",)

    def test_extra_blank_lines_before_code(self):
        blocks = _parse("""\
            .. code-block:: python
                :name: test_blanks



                assert True
        """)
        assert len(blocks) == 1
        assert dict(blocks[0].params)["name"] == "test_blanks"
        assert "assert True" in blocks[0].lines

    def test_deeply_indented_code_block(self):
        blocks = _parse("""\
            .. note::

                .. code-block:: python
                    :name: test_deep

                    x = 1
                    assert x == 1
        """)
        assert len(blocks) == 1
        assert dict(blocks[0].params)["name"] == "test_deep"
        assert blocks[0].lines == ("x = 1", "assert x == 1")

    def test_code_block_with_mixed_indentation_in_body(self):
        blocks = _parse("""\
            .. code-block:: python
                :name: test_mixed_indent

                def foo():
                    return 42

                assert foo() == 42
        """)
        assert len(blocks) == 1
        assert blocks[0].lines == (
            "def foo():",
            "    return 42",
            "",
            "assert foo() == 42",
        )

    def test_tab_indented_rst_ignored(self):
        """Tabs are not considered indentation by get_indent."""
        blocks = _parse("""\
            .. code-block:: python
                :name: test_tab

                assert True
        """)
        assert len(blocks) == 1


class TestParserMalformedRst:
    def test_code_block_no_syntax(self):
        """code-block without a language should not produce python blocks."""
        blocks = _parse("""\
            .. code-block::
                :name: test_no_syntax

                assert True
        """)
        assert all(b.syntax != "python" for b in blocks)

    def test_code_block_wrong_syntax(self):
        """code-block with non-python syntax should be skipped."""
        blocks = _parse("""\
            .. code-block:: javascript
                :name: test_js

                console.log("hi");

            .. code-block:: python
                :name: test_py

                assert True
        """)
        python_blocks = [b for b in blocks if b.syntax == "python"]
        assert len(python_blocks) == 1
        assert dict(python_blocks[0].params)["name"] == "test_py"

    def test_non_param_line_ends_param_parsing(self):
        """A line not starting with : ends param parsing and becomes code."""
        blocks = _parse("""\
            .. code-block:: python
                :name: test_bad_param
                not_a_param

                assert True
        """)
        assert len(blocks) == 1
        params = dict(blocks[0].params)
        assert params["name"] == "test_bad_param"
        # not_a_param is treated as code, not a param
        assert "not_a_param" in blocks[0].lines

    def test_malformed_param_with_colon_is_skipped(self):
        """Param line starting with : but no closing : is warned/skipped."""
        blocks = _parse("""\
            .. code-block:: python
                :name: test_ok
                :broken

                assert True
        """)
        assert len(blocks) == 1
        params = dict(blocks[0].params)
        assert params["name"] == "test_ok"
        assert "broken" not in params

    def test_empty_code_block(self):
        """Code block with params but no body."""
        blocks = _parse("""\
            .. code-block:: python
                :name: test_empty_body

            Next paragraph.
        """)
        assert len(blocks) == 1
        # All lines should be empty or the block should have no content
        assert all(line.strip() == "" for line in blocks[0].lines)

    def test_code_block_at_eof_not_yielded(self):
        """Parser does not yield the last block if no lower-indent
        line follows it (known limitation). Test this directly
        without the _parse terminator."""
        from io import StringIO
        blocks = list(parse_code_blocks(StringIO(dedent("""\
            .. code-block:: python
                :name: test_eof

                assert True"""))))
        assert len(blocks) == 0

    def test_code_block_before_trailing_text(self):
        blocks = _parse("""\
            .. code-block:: python
                :name: test_trailing

                assert True
        """)
        assert len(blocks) == 1
        assert blocks[0].lines == ("assert True",)

    def test_consecutive_code_blocks_no_separator(self):
        blocks = _parse("""\
            .. code-block:: python
                :name: test_first

                x = 1

            .. code-block:: python
                :name: test_second

                y = 2
        """)
        python_blocks = [
            b for b in blocks if b.syntax == "python"
        ]
        assert len(python_blocks) == 2
        names = [dict(b.params).get("name") for b in python_blocks]
        assert names == ["test_first", "test_second"]

    def test_duplicate_param_last_wins(self):
        blocks = _parse("""\
            .. code-block:: python
                :name: test_first_name
                :name: test_second_name

                assert True
        """)
        assert len(blocks) == 1
        params = dict(blocks[0].params)
        assert params["name"] == "test_second_name"

    def test_code_block_directive_misspelled(self):
        """Misspelled directive should not be collected."""
        blocks = _parse("""\
            .. codeblock:: python
                :name: test_misspelled

                assert True
        """)
        assert len(blocks) == 0

    def test_param_with_extra_spaces(self):
        """Extra spaces between : and value are consumed by the regex."""
        blocks = _parse("""\
            .. code-block:: python
                :name:   test_spaces

                assert True
        """)
        assert len(blocks) == 1
        params = dict(blocks[0].params)
        # The param regex \s* consumes leading spaces
        assert params["name"] == "test_spaces"


class TestParserStructure:
    def test_non_python_block_between_python_blocks(self):
        blocks = _parse("""\
            .. code-block:: python
                :name: test_before

                x = 1

            .. code-block:: bash

                echo "hello"

            .. code-block:: python
                :name: test_after

                y = 2
        """)
        python_blocks = [
            b for b in blocks if b.syntax == "python"
        ]
        assert len(python_blocks) == 2

    def test_code_block_inside_note_directive(self):
        blocks = _parse("""\
            .. note::

                Some text here.

                .. code-block:: python
                    :name: test_in_note

                    assert 1 + 1 == 2

            After note.
        """)
        assert len(blocks) == 1
        assert dict(blocks[0].params)["name"] == "test_in_note"

    def test_multiple_nested_levels(self):
        blocks = _parse("""\
            .. warning::

                .. tip::

                    .. code-block:: python
                        :name: test_nested

                        result = 42
                        assert result == 42
        """)
        assert len(blocks) == 1
        assert dict(blocks[0].params)["name"] == "test_nested"
        assert "result = 42" in blocks[0].lines

    def test_block_with_only_blank_lines(self):
        blocks = _parse("""\
            .. code-block:: python
                :name: test_blanks_only



            End.
        """)
        assert len(blocks) == 1

    def test_code_block_with_multiline_string_in_code(self):
        blocks = _parse("""\
            .. code-block:: python
                :name: test_multiline_str

                text = '''
                hello
                world
                '''
                assert "hello" in text
        """)
        assert len(blocks) == 1
        code = "\n".join(blocks[0].lines)
        assert "hello" in code
        assert "world" in code

    def test_rst_with_no_code_blocks(self):
        blocks = _parse("""\
            Title
            =====

            Just some text with no code blocks.

            Another paragraph.
        """)
        assert blocks == []

    def test_rst_with_only_unnamed_blocks(self):
        blocks = _parse("""\
            Example:

            .. code-block:: python

                x = 1

            .. code-block:: python

                y = 2
        """)
        # blocks are parsed but none have names
        for b in blocks:
            assert dict(b.params).get("name") is None


# --- Integration tests: edge cases with pytester ---


class TestIntegrationEdgeCases:
    def test_code_block_no_name_not_collected(self, pytester):
        pytester.makefile(
            ".rst",
            test_noname=dedent("""\
                Example:

                .. code-block:: python

                    assert False

                End.
            """),
        )
        result = pytester.runpytest("-v")
        assert "FAILED" not in result.stdout.str()
        assert result.ret == 5  # no tests collected

    def test_non_test_prefix_not_collected(self, pytester):
        pytester.makefile(
            ".rst",
            test_prefix=dedent("""\
                Example:

                .. code-block:: python
                    :name: example_not_test

                    assert False

                End.
            """),
        )
        result = pytester.runpytest("-v")
        assert "FAILED" not in result.stdout.str()
        assert result.ret == 5

    def test_syntax_error_in_code_block(self, pytester):
        pytester.makefile(
            ".rst",
            test_syntax=dedent("""\
                Broken:

                .. code-block:: python
                    :name: test_syntax_err

                    def foo(
                        # missing closing paren

                End.
            """),
        )
        result = pytester.runpytest("-v")
        assert result.ret != 0

    def test_code_block_with_function_definition(self, pytester):
        pytester.makefile(
            ".rst",
            test_func=dedent("""\
                Functions:

                .. code-block:: python
                    :name: test_function_def

                    def add(a, b):
                        return a + b

                    assert add(2, 3) == 5
                    assert add(-1, 1) == 0

                End.
            """),
        )
        result = pytester.runpytest("-v")
        result.stdout.fnmatch_lines(["*test_function_def*PASSED*"])
        assert result.ret == 0

    def test_code_block_with_class_definition(self, pytester):
        pytester.makefile(
            ".rst",
            test_cls=dedent("""\
                Classes:

                .. code-block:: python
                    :name: test_class_def

                    class Counter:
                        def __init__(self):
                            self.n = 0

                        def inc(self):
                            self.n += 1
                            return self.n

                    c = Counter()
                    assert c.inc() == 1
                    assert c.inc() == 2

                End.
            """),
        )
        result = pytester.runpytest("-v")
        result.stdout.fnmatch_lines(["*test_class_def*PASSED*"])
        assert result.ret == 0

    def test_code_block_with_imports(self, pytester):
        pytester.makefile(
            ".rst",
            test_imports=dedent("""\
                Imports:

                .. code-block:: python
                    :name: test_stdlib_imports

                    import os
                    import sys
                    from pathlib import Path

                    assert hasattr(os, "getcwd")
                    assert hasattr(sys, "version")
                    assert Path(".").exists()

                End.
            """),
        )
        result = pytester.runpytest("-v")
        result.stdout.fnmatch_lines(["*test_stdlib_imports*PASSED*"])
        assert result.ret == 0

    def test_many_blocks_in_one_file(self, pytester):
        blocks = []
        for i in range(10):
            blocks.append(dedent(f"""\
                Block {i}:

                .. code-block:: python
                    :name: test_block_{i}

                    assert {i} == {i}
            """))
        blocks.append("End.\n")
        pytester.makefile(".rst", test_many="\n".join(blocks))
        result = pytester.runpytest("-v")
        for i in range(10):
            result.stdout.fnmatch_lines([f"*test_block_{i}*PASSED*"])
        assert result.ret == 0

    def test_code_block_deeply_nested_in_directives(self, pytester):
        pytester.makefile(
            ".rst",
            test_deep=dedent("""\
                .. note::

                    Some context here.

                    .. code-block:: python
                        :name: test_inside_note

                        assert 1 + 1 == 2

                End.
            """),
        )
        result = pytester.runpytest("-v")
        result.stdout.fnmatch_lines(["*test_inside_note*PASSED*"])
        assert result.ret == 0

    def test_non_python_code_block_ignored(self, pytester):
        pytester.makefile(
            ".rst",
            test_lang=dedent("""\
                .. code-block:: javascript
                    :name: test_js_block

                    throw new Error("should not run");

                .. code-block:: python
                    :name: test_py_block

                    assert True

                End.
            """),
        )
        result = pytester.runpytest("-v")
        result.stdout.fnmatch_lines(["*test_py_block*PASSED*"])
        assert "test_js_block" not in result.stdout.str()
        assert result.ret == 0

    def test_code_block_with_blank_lines_in_body(self, pytester):
        pytester.makefile(
            ".rst",
            test_blanks=dedent("""\
                Blanks:

                .. code-block:: python
                    :name: test_with_blanks

                    x = 1

                    y = 2

                    assert x + y == 3

                End.
            """),
        )
        result = pytester.runpytest("-v")
        result.stdout.fnmatch_lines(["*test_with_blanks*PASSED*"])
        assert result.ret == 0

    def test_code_block_exception_traceback_has_line_numbers(
        self, pytester,
    ):
        pytester.makefile(
            ".rst",
            test_tb=dedent("""\
                Traceback:

                .. code-block:: python
                    :name: test_traceback

                    x = 1
                    y = 2
                    assert x == y

                End.
            """),
        )
        result = pytester.runpytest("-v")
        result.stdout.fnmatch_lines(["*test_traceback*FAILED*"])
        # Verify the traceback references the .rst file
        result.stdout.fnmatch_lines(["*test_tb.rst*"])
        assert result.ret != 0

    def test_empty_rst_file(self, pytester):
        pytester.makefile(".rst", test_empty="")
        result = pytester.runpytest("-v")
        assert result.ret == 5  # no tests collected

    def test_rst_file_with_only_text(self, pytester):
        pytester.makefile(
            ".rst",
            test_text=dedent("""\
                Title
                =====

                Just a document with no code at all.

                Another section
                ---------------

                Still no code.
            """),
        )
        result = pytester.runpytest("-v")
        assert result.ret == 5

    def test_code_block_at_end_of_file_not_collected(self, pytester):
        """Block at EOF with no trailing content is not collected
        (known parser limitation)."""
        pytester.makefile(
            ".rst",
            test_eof=dedent("""\
                EOF:

                .. code-block:: python
                    :name: test_at_eof

                    assert True
            """),
        )
        result = pytester.runpytest("-v")
        assert result.ret == 5  # no tests collected

    def test_fixture_and_plain_blocks_interleaved(self, pytester):
        pytester.makefile(
            ".rst",
            test_interleave=dedent("""\
                .. code-block:: python
                    :name: test_plain_1

                    assert 1 == 1

                .. code-block:: python
                    :name: test_with_fix
                    :fixtures: tmp_path

                    assert tmp_path.is_dir()

                .. code-block:: python
                    :name: test_plain_2

                    assert 2 == 2

                End.
            """),
        )
        result = pytester.runpytest("-v")
        result.stdout.fnmatch_lines([
            "*test_plain_1*PASSED*",
            "*test_with_fix*PASSED*",
            "*test_plain_2*PASSED*",
        ])
        assert result.ret == 0
