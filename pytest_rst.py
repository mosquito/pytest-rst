from types import CodeType
from typing import Iterable, Optional, TextIO

import docutils.frontend
import docutils.nodes
import docutils.parsers.rst
import docutils.utils
import py
import pytest


def parse_rst(fp: TextIO) -> docutils.nodes.document:
    parser = docutils.parsers.rst.Parser()
    settings = docutils.frontend.OptionParser(
        read_config_files=False,
        components=(docutils.parsers.rst.Parser,),
    ).get_default_values()

    document = docutils.utils.new_document(fp.name, settings=settings)
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

        names = node.get("names", [])
        if not names:
            return

        test_name = names[0]
        if not test_name.startswith("test_"):
            return

        self.code_objects.append(
            (
                test_name,
                compile(
                    source=node.astext(),
                    filename=node.source,
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
    obj = None

    def collect(self) -> Iterable["RSTTestItem"]:
        with open(self.fspath, "r") as fp:
            doc = parse_rst(fp)
            visitor = CodeVisitor(doc)
            doc.walk(visitor)

            for name, code in visitor.code_objects:
                yield RSTTestItem.from_parent(
                    name=name,
                    parent=self,
                    code=code,
                )


def pytest_collect_file(
    path: py.path.local, parent: pytest.Collector,
) -> Optional[RSTModule]:
    if path.ext != ".rst":
        return None

    return RSTModule.from_parent(parent=parent, fspath=path)
