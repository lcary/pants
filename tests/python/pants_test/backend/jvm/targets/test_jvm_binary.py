# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import unittest
from textwrap import dedent

from pants.backend.jvm.register import build_file_aliases as register_jvm
from pants.backend.jvm.targets.exclude import Exclude
from pants.backend.jvm.targets.jvm_binary import (Duplicate, JarRules, JvmBinary, ManifestEntries,
                                                  Skip)
from pants.base.address import BuildFileAddress
from pants.base.exceptions import TargetDefinitionException
from pants.base.payload_field import FingerprintedField
from pants.base.target import Target
from pants_test.base_test import BaseTest


class JarRulesTest(unittest.TestCase):
  def test_jar_rule(self):
    dup_rule = Duplicate('foo', Duplicate.REPLACE)
    self.assertEquals('Duplicate(apply_pattern=foo, action=REPLACE)',
                      repr(dup_rule))
    skip_rule = Skip('foo')
    self.assertEquals('Skip(apply_pattern=foo)', repr(skip_rule))

  def test_invalid_apply_pattern(self):
    with self.assertRaisesRegexp(ValueError, r'The supplied apply_pattern is not a string'):
      Skip(None)
    with self.assertRaisesRegexp(ValueError, r'The supplied apply_pattern is not a string'):
      Duplicate(None, Duplicate.SKIP)
    with self.assertRaisesRegexp(ValueError, r'The supplied apply_pattern: \) is not a valid'):
      Skip(r')')
    with self.assertRaisesRegexp(ValueError, r'The supplied apply_pattern: \) is not a valid'):
      Duplicate(r')', Duplicate.SKIP)

  def test_bad_action(self):
    with self.assertRaisesRegexp(ValueError, r'The supplied action must be one of'):
      Duplicate('foo', None)

  def test_duplicate_error(self):
    with self.assertRaisesRegexp(Duplicate.Error, r'Duplicate entry encountered for path foo'):
      raise Duplicate.Error('foo')

  def test_default(self):
    jar_rules = JarRules.default()
    self.assertTrue(4, len(jar_rules.rules))
    for rule in jar_rules.rules:
      self.assertTrue(rule.apply_pattern.pattern.startswith(r'^META-INF'))

  def test_set_bad_default(self):
    with self.assertRaisesRegexp(ValueError, r'The default rules must be a JarRules'):
      JarRules.set_default(None)


class JvmBinaryTest(BaseTest):
  @property
  def alias_groups(self):
    return register_jvm()

  def test_simple(self):
    self.add_to_build_file('BUILD', dedent('''
    jvm_binary(name='foo',
      main='com.example.Foo',
      basename='foo-base',
    )
    '''))

    target = self.target('//:foo')
    self.assertEquals('com.example.Foo', target.main)
    self.assertEquals('com.example.Foo', target.payload.main)
    self.assertEquals('foo-base', target.basename)
    self.assertEquals('foo-base', target.payload.basename)
    self.assertEquals([], target.deploy_excludes)
    self.assertEquals([], target.payload.deploy_excludes)
    self.assertEquals(JarRules.default(), target.deploy_jar_rules)
    self.assertEquals(JarRules.default(), target.payload.deploy_jar_rules)
    self.assertEquals({}, target.payload.manifest_entries.entries);

  def test_default_base(self):
    self.add_to_build_file('BUILD', dedent('''
    jvm_binary(name='foo',
      main='com.example.Foo',
    )
    '''))
    target = self.target('//:foo')
    self.assertEquals('foo', target.basename)

  def test_deploy_jar_excludes(self):
    self.add_to_build_file('BUILD', dedent('''
    jvm_binary(name='foo',
      main='com.example.Foo',
      deploy_excludes=[exclude(org='example.com', name='foo-lib')],
    )
    '''))
    target = self.target('//:foo')
    self.assertEquals([Exclude(org='example.com', name='foo-lib')],
                      target.deploy_excludes)

  def test_deploy_jar_rules(self):
    self.add_to_build_file('BUILD', dedent('''
    jvm_binary(name='foo',
      main='com.example.Foo',
      deploy_jar_rules=jar_rules([Duplicate('foo', Duplicate.SKIP)],
                                 default_dup_action=Duplicate.FAIL)
    )
    '''))
    target = self.target('//:foo')
    jar_rules =  target.deploy_jar_rules
    self.assertEquals(1, len(jar_rules.rules))
    self.assertEquals('foo', jar_rules.rules[0].apply_pattern.pattern)
    self.assertEquals(repr(Duplicate.SKIP),
                      repr(jar_rules.rules[0].action)) # <object object at 0x...>
    self.assertEquals(Duplicate.FAIL, jar_rules.default_dup_action)

  def test_bad_source_declaration(self):
    build_file = self.add_to_build_file('BUILD', dedent('''
        jvm_binary(name='foo',
          main='com.example.Foo',
          source=['foo.py'],
        )
        '''))
    with self.assertRaisesRegexp(TargetDefinitionException,
                                 r'Invalid target JvmBinary.*foo.*source must be a single'):
      self.build_graph.inject_address_closure(BuildFileAddress(build_file, 'foo'))

  def test_bad_sources_declaration(self):
    with self.assertRaisesRegexp(Target.IllegalArgument,
                                 r'jvm_binary only supports a single "source" argument'):
      self.make_target('foo:foo', target_type=JvmBinary, main='com.example.Foo', sources=['foo.py'])

  def test_bad_main_declaration(self):
    build_file = self.add_to_build_file('BUILD', dedent('''
        jvm_binary(name='bar',
          main=['com.example.Bar'],
        )
        '''))
    with self.assertRaisesRegexp(TargetDefinitionException,
                                 r'Invalid target JvmBinary.*bar.*main must be a fully'):
      self.build_graph.inject_address_closure(BuildFileAddress(build_file, 'bar'))

  def test_bad_jar_rules(self):
    build_file = self.add_to_build_file('BUILD', dedent('''
        jvm_binary(name='foo',
          main='com.example.Foo',
          deploy_jar_rules='invalid',
        )
        '''))
    with self.assertRaisesRegexp(TargetDefinitionException,
                                  r'Invalid target JvmBinary.*foo.*'
                                  r'deploy_jar_rules must be a JarRules specification. got str'):
      self.build_graph.inject_address_closure(BuildFileAddress(build_file, 'foo'))

  def _assert_fingerprints_not_equal(self, fields):
    for field in fields:
      for other_field in fields:
        if field == other_field:
          continue
        self.assertNotEquals(field.fingerprint(), other_field.fingerprint())

  def test_jar_rules_field(self):
    field1 = FingerprintedField(JarRules(rules=[Duplicate('foo', Duplicate.SKIP)]))
    field1_same = FingerprintedField(JarRules(rules=[Duplicate('foo', Duplicate.SKIP)]))
    field2 = FingerprintedField(JarRules(rules=[Duplicate('foo', Duplicate.CONCAT)]))
    field3 = FingerprintedField(JarRules(rules=[Duplicate('bar', Duplicate.SKIP)]))
    field4 = FingerprintedField(JarRules(rules=[Duplicate('foo', Duplicate.SKIP),
                                           Duplicate('bar', Duplicate.SKIP)]))
    field5 = FingerprintedField(JarRules(rules=[Duplicate('foo', Duplicate.SKIP), Skip('foo')]))
    field6 = FingerprintedField(JarRules(rules=[Duplicate('foo', Duplicate.SKIP)],
                                    default_dup_action=Duplicate.FAIL))
    field6_same = FingerprintedField(JarRules(rules=[Duplicate('foo', Duplicate.SKIP)],
                                         default_dup_action=Duplicate.FAIL))
    field7 = FingerprintedField(JarRules(rules=[Skip('foo')]))
    field8 = FingerprintedField(JarRules(rules=[Skip('bar')]))
    field8_same = FingerprintedField(JarRules(rules=[Skip('bar')]))

    self.assertEquals(field1.fingerprint(), field1_same.fingerprint())
    self.assertEquals(field6.fingerprint(), field6_same.fingerprint())
    self.assertEquals(field8.fingerprint(), field8_same.fingerprint())
    self._assert_fingerprints_not_equal([field1, field2, field3, field4, field5, field6, field7])

  def test_manifest_entries(self):
    self.add_to_build_file('BUILD', dedent('''
        jvm_binary(name='foo',
          main='com.example.Foo',
          manifest_entries= {
            'Foo-Field' : 'foo',
          }
        )
        '''))
    target = self.target('//:foo')
    self.assertTrue(isinstance(target.payload.manifest_entries, ManifestEntries))
    entries = target.payload.manifest_entries.entries
    self.assertEquals({ 'Foo-Field' : 'foo'}, entries)

  def test_manifest_not_dict(self):
    self.add_to_build_file('BUILD', dedent('''
        jvm_binary(name='foo',
          main='com.example.Foo',
          manifest_entries= 'foo',
        )
        '''))
    with self.assertRaisesRegexp(TargetDefinitionException,
                                 r'Invalid target JvmBinary\(BuildFileAddress\(.*BUILD\), foo\)\): '
                                 r'manifest_entries must be a dict. got str'):
       self.target('//:foo')

  def test_manifest_bad_key(self):
    self.add_to_build_file('BUILD', dedent('''
        jvm_binary(name='foo',
          main='com.example.Foo',
          manifest_entries= {
            jar(org='bad', name='bad', rev='bad') : 'foo',
          }
        )
        '''))
    with self.assertRaisesRegexp(ManifestEntries.ExpectedDictionaryError,
                                 r'entries must be dictionary of strings, got key bad-bad-bad type JarDependency'):
      self.target('//:foo')

  def test_manifest_entries_fingerprint(self):
    field1 = ManifestEntries()
    field2 = ManifestEntries({'Foo-Field' : 'foo'})
    field2_same = ManifestEntries({'Foo-Field' : 'foo'})
    field3 = ManifestEntries({'Foo-Field' : 'foo', 'Bar-Field' : 'bar'})
    self.assertEquals(field2.fingerprint(), field2_same.fingerprint())
    self._assert_fingerprints_not_equal([field1, field2, field3])
