import logging
import re
from io import StringIO
from pathlib import Path
from types import CodeType
from typing import (
    Iterable, Iterator, NamedTuple, Optional, Tuple, TextIO, List
)

import pytest


class CodeBlock(NamedTuple):
    start_line: int
    params: Tuple[Tuple[str, str], ...]
    syntax: Optional[str]
    lines: Tuple[str, ...]

    @property
    def end_line(self) -> int:
        return self.start_line + len(self.lines) + 1


CODE_BLOCK_REGEXP = re.compile(r"\.\. code-block::(\s*(?P<syntax>\S+)\s*)?$")


def get_indent(s: str, *, indent_char: str = " ") -> int:
    if not s.strip():
        return -1

    if not s.startswith(indent_char):
        return 0

    result = 0
    for c in s:
        if c != indent_char:
            return result
        result += 1

    return result


class CodeLine(NamedTuple):
    lineno: int
    line: str


class IndentBlock(NamedTuple):
    indent: int
    lines: Tuple[CodeLine]
    parent: Optional["IndentBlock"]


def parse_indent_blocks(fp: TextIO) -> Iterator[IndentBlock]:

    last_indent = -1

    groups = []
    group = []

    for lineno, line in enumerate(fp.readlines()):
        indent = get_indent(line)
        if indent < 0:
            continue

        if last_indent < 0:
            last_indent = indent

        if indent != last_indent:
            last_indent = indent
            if group:
                groups.append(group)
            group = []
        group.append((indent, lineno, line))

    parent = None
    for group in groups:
        block = []
        indent = 0

        for indent, lineno, line in group:
            block.append(CodeLine(lineno=lineno, line=line))

        parent = IndentBlock(
            indent=indent,
            lines=tuple(block),
            parent=parent
        )

        yield parent


def parse_code_blocks(fp: TextIO) -> Iterator[CodeBlock]:
    fp.seek(0)
    for block in parse_indent_blocks(fp):
        if not block.parent:
            continue

        last_parent_line: CodeLine = block.parent.lines[-1]
        match = CODE_BLOCK_REGEXP.match(last_parent_line.line)

        if match is None:
            continue

        groups = match.groupdict()
        syntax = groups.get("syntax") or None

        params: List[Tuple[str, str]] = []
        code_lines: List[CodeLine] = []
        parse_params = True

        for lineno, line in block.lines:
            line: str = line[block.indent:]
            if not line.startswith(":"):
                parse_params = False

            if parse_params:
                match = re.match(
                    r"^:(?P<param>.*):\s*(?P<value>.*)?$", line
                )
                if match is None:
                    logging.warning(
                        "Ignore bad formatted rst param %r at line %d",
                        line, lineno
                    )
                    continue
                groups = match.groupdict()
                params.append((groups["param"], groups.get("value")))
                continue

            code_lines.append(CodeLine(lineno=lineno, line=line))

        if not code_lines:
            continue

        with StringIO() as rfp:
            start_line = code_lines[0].lineno
            last_lineno = start_line
            rfp.write(code_lines[0].line)

            for lineno, line in code_lines[1:]:
                for _ in range(last_lineno, lineno - 1):
                    rfp.write("\n")
                last_lineno = lineno
                rfp.write(line)

            result_lines = (
                rfp.getvalue().rstrip() + "\n"
            )

        if not result_lines.strip():
            continue

        yield CodeBlock(
            syntax=syntax,
            start_line=start_line,
            params=tuple(params),
            lines=tuple(result_lines.splitlines()),
        )


class RSTTestItem(pytest.Item):
    def __init__(self, name: str, parent: "RSTModule", code: CodeType):
        super().__init__(name=name, parent=parent)
        self.module = code

    def runtest(self) -> None:
        exec(self.module, {"__name__": "__main__"})


class RSTModule(pytest.Module):
    def collect(self) -> Iterable["RSTTestItem"]:
        with open(self.fspath, "r") as fp:
            for code_block in parse_code_blocks(fp):
                if code_block.syntax != "python":
                    continue

                params = dict(code_block.params)
                test_name = params.get("name")

                if not test_name:
                    continue

                if not test_name.startswith(
                    self.config.getoption("--rst-prefix"),
                ):
                    continue

                with StringIO() as fp:
                    fp.write("\n" * code_block.start_line)
                    for line in code_block.lines:
                        fp.write(line)
                        fp.write("\n")

                    yield RSTTestItem.from_parent(
                        name=(
                            f"{test_name}"
                            f"[{code_block.start_line}:{code_block.end_line}]"
                        ),
                        parent=self,
                        code=compile(
                            source=fp.getvalue(), mode="exec",
                            filename=self.fspath.basename,
                        ),
                    )


def pytest_addoption(parser):
    parser.addoption(
        "--rst-prefix", default="test_",
        help="RST code-block name prefix",
    )


@pytest.hookimpl(trylast=True)
def pytest_collect_file(path, parent: pytest.Collector) -> Optional[RSTModule]:
    if path.ext != ".rst":
        return None
    return RSTModule.from_parent(parent=parent, path=Path(path))
