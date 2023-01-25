from pathlib import Path
from typing import TextIO

import pytest

from pytest_rst import parse_code_blocks, CodeBlock, get_indent


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
def sample_fp() -> TextIO:
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
            params=(('name', 'test_first'),),
            syntax='python',
            lines=('assert True',)
        ),
        CodeBlock(
            start_line=11,
            params=(('name', 'test_second'),),
            syntax='python',
            lines=('assert True', 'assert not False', 'assert 1')
        ),
        CodeBlock(
            start_line=29,
            params=(),
            syntax='python',
            lines=('.. code-block:: python',)
        ),
    ]
