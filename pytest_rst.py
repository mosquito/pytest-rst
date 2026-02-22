import logging
import re
import textwrap
from io import StringIO
from pathlib import Path
from types import CodeType, FunctionType
from typing import (
    Any,
    Iterable,
    Iterator,
    List,
    NamedTuple,
    Optional,
    TextIO,
    Tuple,
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


CODE_BLOCK_REGEXP = re.compile(r"^\.\. code-block::(\s*(?P<syntax>\S+)\s*)?$")
COMMENT_FIXTURES_REGEXP = re.compile(r"^#\s*fixtures:\s*(.+)$")


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


def parse_code_blocks(fp: TextIO) -> Iterator[CodeBlock]:
    fp.seek(0)

    code_lines: List[CodeLine] = []
    code_block_indent: int = -2
    syntax: Optional[str] = None

    content = tuple(
        map(
            lambda x: (get_indent(x[1]), x[0], x[1]),
            enumerate(fp, start=0),
        ),
    )

    index = -1
    while index < (len(content) - 1):
        index += 1
        indent, lineno, line = content[index]

        if indent < 0:
            continue

        if code_block_indent == -2:
            match = CODE_BLOCK_REGEXP.match(line[indent:])
            if match is None:
                continue
            groups = match.groupdict()
            syntax = groups.get("syntax") or None
            code_block_indent = -1
            continue

        if code_block_indent == -1:
            code_block_indent = indent

        if indent >= code_block_indent:
            code_lines.append(
                CodeLine(
                    lineno=lineno,
                    line=line[code_block_indent:],
                ),
            )
            continue

        if syntax == "python":
            # parse params
            params_parsed = False
            params: List[Tuple[str, str]] = []
            line_first: int = code_lines[0].lineno
            result_lines = []
            previous_line = 0

            for lineno, line in code_lines:
                if not line.startswith(":") and not params_parsed:
                    params_parsed = True
                    line_first = lineno

                if not params_parsed:
                    match = re.match(
                        r"^:(?P<param>.*):\s*(?P<value>.*)?$",
                        line,
                    )
                    if match is None:
                        logging.warning(
                            "Ignore bad formatted rst param %r at line %d",
                            line,
                            lineno,
                        )
                        continue
                    groups = match.groupdict()
                    params.append((groups["param"], groups.get("value") or ""))
                    continue

                if previous_line and lineno != (previous_line + 1):
                    for _ in range(lineno - (previous_line + 1)):
                        result_lines.append("")

                result_lines.append(line.rstrip())
                previous_line = lineno

            yield CodeBlock(
                syntax=syntax,
                start_line=line_first,
                params=tuple(params),
                lines=tuple(result_lines),
            )
            result_lines.clear()

        code_lines = []
        syntax = None
        code_block_indent = -2
        index -= 1


def _parse_fixtures(value: str) -> Tuple[str, ...]:
    return tuple(name for name in (s.strip() for s in value.split(",")) if name)


def _make_rst_test_func(
    code: CodeType,
    fixture_names: Tuple[str, ...],
) -> FunctionType:
    params = ", ".join(fixture_names)
    wrapper_src = textwrap.dedent(f"""\
        def rst_test_func({params}):
            ns = {{"__name__": "__main__"}}
            ns.update({{ {", ".join(f"{n!r}: {n}" for n in fixture_names)} }})
            exec(code, ns)
    """)
    local_ns: dict[str, Any] = {}
    exec(
        compile(wrapper_src, "<rst-fixture-wrapper>", "exec"),
        {"code": code},
        local_ns,
    )
    fn: FunctionType = local_ns["rst_test_func"]
    return fn


class RSTTestItem(pytest.Item):
    def __init__(self, name: str, parent: "RSTModule", code: CodeType):
        super().__init__(name=name, parent=parent)
        self.module = code

    def runtest(self) -> None:
        exec(self.module, {"__name__": "__main__"})


class RSTModule(pytest.Module):
    def collect(self) -> Iterable[pytest.Item]:
        with open(self.fspath, "r") as fp:
            for code_block in parse_code_blocks(fp):
                params = dict(code_block.params)
                test_name = params.get("name")

                if not test_name:
                    continue

                if not test_name.startswith(
                    self.config.getoption("--rst-prefix"),
                ):
                    continue

                fixtures_value = params.get("fixtures", "")
                fixtures_found: set[str] = set(
                    _parse_fixtures(fixtures_value),
                )

                # Scan for "# fixtures:" comments and strip them
                filtered_lines = []
                for line in code_block.lines:
                    match = COMMENT_FIXTURES_REGEXP.match(line.strip())
                    if match:
                        fixtures_found.update(
                            _parse_fixtures(match.group(1)),
                        )
                    else:
                        filtered_lines.append(line)

                fixture_names = tuple(sorted(fixtures_found))

                with StringIO() as code_fp:
                    code_fp.write("\n" * code_block.start_line)
                    for line in filtered_lines:
                        code_fp.write(line)
                        code_fp.write("\n")

                    code = compile(
                        source=code_fp.getvalue(),
                        mode="exec",
                        filename=self.fspath,
                    )

                item_name = (
                    f"{test_name}"
                    f"[{code_block.start_line}:{code_block.end_line}]"
                )

                if fixture_names:
                    wrapper = _make_rst_test_func(
                        code,
                        fixture_names,
                    )
                    yield pytest.Function.from_parent(
                        name=item_name,
                        parent=self,
                        callobj=wrapper,
                    )
                else:
                    yield RSTTestItem.from_parent(
                        name=item_name,
                        parent=self,
                        code=code,
                    )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--rst-prefix",
        default="test_",
        help="RST code-block name prefix",
    )


@pytest.hookimpl(trylast=True)
def pytest_collect_file(
    file_path: Path,
    parent: pytest.Collector,
) -> Optional[RSTModule]:
    if file_path.suffix != ".rst":
        return None
    return RSTModule.from_parent(parent=parent, path=file_path)
