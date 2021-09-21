from types import CodeType
from typing import Iterable, Optional, TextIO

import docutils.frontend
import docutils.nodes
import docutils.parsers.rst
import docutils.utils
import py
import pytest


def parse_rst(fp: TextIO, **kwargs) -> docutils.nodes.document:
    parser = docutils.parsers.rst.Parser()
    defaults = dict(
        quiet=True,
        source_link=False,
        generator=False,
        toc_backlinks=False,
        footnote_backlinks=False,
        section_numbering=False,
        strip_comments=False,
        strip_classes=False,
        strip_elements_with_classes=False,
        debug=False,
        syntax_highlight='none',
        raw_enabled=False,
    )

    defaults.update(kwargs)

    settings = docutils.frontend.OptionParser(
        read_config_files=False,
        defaults=defaults,
        components=(docutils.parsers.rst.Parser,),
    ).get_default_values()

    document = docutils.utils.new_document(fp.name, settings=settings)

    if not settings.strict_visitor:
        # Hide all messages
        document.reporter.error = lambda a, b, *_, **__: b

    parser.parse(fp.read(), document)
    return document


class CodeVisitor(docutils.nodes.NodeVisitor):
    def __init__(self, *args, **kwargs):
        super(CodeVisitor, self).__init__(*args, **kwargs)
        self.code_objects = []

    def unknown_visit(self, node: docutils.nodes.Node) -> None:
        return

    def visit_literal_block(self, node: docutils.nodes.literal_block) -> None:
        if frozenset(node["classes"]) != frozenset(["code", "python"]):
            return

        names = node.get("names") or [""]
        test_name = names[0]

        source, line = docutils.utils.get_source_line(node)
        shift = ""
        if line:
            shift += "\n" * line

        self.code_objects.append(
            (
                test_name,
                dict(
                    source=shift + node.astext(),
                    filename=source,
                    mode="exec",
                )
            )
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
            doc = parse_rst(
                fp, strict_visitor=self.config.getoption("--rst-strict")
            )
            visitor = CodeVisitor(doc)
            doc.walk(visitor)

            name_prefix = self.config.getoption("--rst-prefix")

            for name, code in visitor.code_objects:
                if not name.startswith(name_prefix):
                    continue

                yield RSTTestItem.from_parent(
                    name=name,
                    parent=self,
                    code=compile(**code),
                )


def pytest_addoption(parser):
    parser.addoption(
        '--rst-prefix', default="test_",
        help='RST code-block name prefix'
    )

    parser.addoption(
        '--rst-strict', action="store_true",
        help='RST strict parser'
    )


@pytest.hookimpl(trylast=True)
def pytest_collect_file(
    path: py.path.local, parent: pytest.Collector
) -> Optional[RSTModule]:
    if path.ext != ".rst":
        return None

    return RSTModule.from_parent(parent=parent, fspath=path)
