# coding=utf-8
# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

from pants.option.arg_splitter import GLOBAL_SCOPE
from pants.option.parser import Parser


class ParserHierarchy(object):
  """A hierarchy of scoped Parser instances.

  A scope is a dotted string: E.g., compile.java. In this example the compile.java scope is
  enclosed in the compile scope, which is enclosed in the global scope (represented by an
  empty string.)
  """
  def __init__(self, env, config, scope_infos):
    # Sorting ensures that ancestors precede descendants.
    scope_infos = sorted(set(list(scope_infos)), key=lambda si: si.scope)
    self._parser_by_scope = {}
    for scope_info in scope_infos:
      scope = scope_info.scope
      parent_parser = (None if scope == GLOBAL_SCOPE else
                       self._parser_by_scope[scope.rpartition('.')[0]])
      self._parser_by_scope[scope] = Parser(env, config, scope_info, parent_parser)

  def get_parser_by_scope(self, scope):
    return self._parser_by_scope[scope]

  def walk(self, callback):
    """Invoke callback on each parser, in pre-order depth-first order."""
    self._parser_by_scope[GLOBAL_SCOPE].walk(callback)
