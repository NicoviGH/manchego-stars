#!/usr/bin/env python3
"""Tests for tools/callsites.py -- the query grep cannot answer (#300).

Six greps in one session answered questions they could not actually answer, and three of
those shipped bugs the whole unit suite passed through. The common shape: "where is this
function called, and WITH WHAT" is a structural question, and text search treats a
definition, a keyword argument and a positional argument as the same thing.

Run: python3 tools/test_callsites.py
"""
import os
import sys
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callsites


def _call_on(source, target, needle):
    """The single call of `target` on the line containing `needle` -- so a fixture edit
    cannot silently re-point an assertion at a different call site."""
    lineno = next(i for i, l in enumerate(source.split('\n'), 1) if needle in l)
    return next(s for s in callsites.scan(source, target, '<s>')
                if s.kind == 'call' and s.lineno == lineno)


SAMPLE = textwrap.dedent('''
    def wrap(text, width=200, measure=px):
        return text

    def helper(script, slot, fid, width=200):
        return wrap(script, width)

    def caller():
        a = wrap('x')
        b = wrap('y', width=29)
        c = wrap('z', 42)
        d = helper(s, 'slot', fid, 29)
        e = other.wrap('w', width=20)
        return a, b, c, d, e
''')


class Definitions(unittest.TestCase):
    def test_a_definition_is_reported_as_a_DEF_not_a_call(self):
        """The first miss: a regex sweep rewrote function DEFINITIONS along with the calls,
        leaving their bodies referring to a parameter that no longer existed."""
        found = callsites.scan(SAMPLE, 'wrap', '<s>')
        defs = [f for f in found if f.kind == 'def']
        self.assertEqual(1, len(defs))
        self.assertEqual(['text', 'width', 'measure'], defs[0].params)

    def test_calls_are_never_counted_as_definitions(self):
        found = callsites.scan(SAMPLE, 'wrap', '<s>')
        # five: the pass-through in `helper`, three in `caller`, and the module-qualified one
        self.assertEqual(5, len([f for f in found if f.kind == 'call']))


class ArgumentBinding(unittest.TestCase):
    def test_a_POSITIONAL_argument_is_bound_to_its_parameter_NAME(self):
        """The second miss, and the one that shipped: `_ch05_opening_body(..., fid, 29)`
        passed a width positionally, so every search for `width=` walked straight past it and
        ch05's moose scene re-wrapped to seven characters a line."""
        found = callsites.scan(SAMPLE, 'helper', '<s>')
        call = [f for f in found if f.kind == 'call'][0]
        self.assertEqual('29', call.bound['width'])
        self.assertIn('width', call.positional)

    def test_a_keyword_argument_is_bound_by_its_own_name(self):
        call = _call_on(SAMPLE, 'wrap', "wrap('y', width=29)")
        self.assertEqual('29', call.bound['width'])
        self.assertNotIn('width', call.positional)

    def test_a_positional_SECOND_argument_binds_to_width_too(self):
        call = _call_on(SAMPLE, 'wrap', "wrap('z', 42)")
        self.assertEqual('42', call.bound['width'])
        self.assertIn('width', call.positional)

    def test_an_omitted_argument_is_absent_rather_than_guessed(self):
        """`wrap('x')` takes the default. Reporting a value there would invent one."""
        self.assertNotIn('width', _call_on(SAMPLE, 'wrap', "wrap('x')").bound)

    def test_an_expression_argument_is_reported_as_written(self):
        """`wrap(script, width)` -- the pass-through. Its value is a name, and saying so is
        the point: a site that forwards its caller's width is not a site that sets one."""
        self.assertEqual('width', _call_on(SAMPLE, 'wrap', 'wrap(script, width)').bound['width'])


class MethodCalls(unittest.TestCase):
    def test_an_attribute_call_of_the_same_name_is_found(self):
        """`bc._wrap_fe_lines(...)` in the tests is the same function reached through a
        module. Missing those would under-report exactly where the campaign is exercised."""
        self.assertEqual('20', _call_on(SAMPLE, 'wrap', "other.wrap('w', width=20)")
                         .bound['width'])


class StarredArguments(unittest.TestCase):
    """A `*args` splat makes every later position UNKNOWABLE -- the star may stand for any
    number of arguments. Binding what follows it to the next parameter name is a guess that
    reads like a fact, and this feeds the width guard."""

    STARRED = textwrap.dedent("""
        def wrap(text, width=200, measure=px):
            return text
        a = wrap(*args, 29)
        b = wrap(*args, *more)
        c = wrap(*args, width=29)
    """)

    def test_a_positional_AFTER_a_star_is_not_bound_to_a_parameter_name(self):
        call = _call_on(self.STARRED, 'wrap', 'wrap(*args, 29)')
        self.assertNotIn('width', call.bound,
                         'the star may stand for any number of args -- this is a guess')

    def test_two_stars_do_not_clobber_each_other(self):
        call = _call_on(self.STARRED, 'wrap', 'wrap(*args, *more)')
        self.assertEqual(2, len([k for k in call.bound if k.startswith('*')]))

    def test_a_KEYWORD_after_a_star_is_still_exact(self):
        """A keyword names its own parameter, so a splat before it changes nothing."""
        call = _call_on(self.STARRED, 'wrap', 'wrap(*args, width=29)')
        self.assertEqual('29', call.bound['width'])


class TheCommandLine(unittest.TestCase):
    def test_it_binds_positionals_across_FILES(self):
        """The tool's headline case. A call in another module has no local definition, so
        without resolving the signature from the defining file the CLI prints `arg1=29` --
        the positional-width form this tool exists to surface, unsurfaced."""
        import tempfile
        d = tempfile.mkdtemp()
        with open(os.path.join(d, 'defs.py'), 'w') as fh:
            fh.write('def wrap(text, width=200):\n    return text\n')
        with open(os.path.join(d, 'uses.py'), 'w') as fh:
            fh.write("import defs\ndefs.wrap('x', 29)\n")
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            callsites.main([os.path.join(d, '*.py'), 'wrap'])
        self.assertIn('width=29', buf.getvalue())
        self.assertNotIn('arg1=29', buf.getvalue())


class Reporting(unittest.TestCase):
    def test_render_names_the_file_the_line_and_the_binding(self):
        out = callsites.render(callsites.scan(SAMPLE, 'helper', 'x.py'))
        self.assertIn('DEF   x.py:', out)
        self.assertIn('width=29', out)
        self.assertIn('POSITIONAL', out)

    def test_a_syntax_error_names_the_file_rather_than_raising(self):
        with self.assertRaises(callsites.ParseError) as raised:
            callsites.scan('def (:', 'wrap', 'broken.py')
        self.assertIn('broken.py', str(raised.exception))


if __name__ == '__main__':
    unittest.main()
