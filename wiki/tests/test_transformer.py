from nose.tools import assert_equals
from transformer import Line, Header, BlockQuote, Table, Transformer


class _TransformationTest(object):

    def _assert_transformation(self, element_class, input, expected):
        element = element_class()
        element.add(input)
        assert_equals(str(element), expected)


class TestLineTransformation(_TransformationTest):

    def test_regular_line(self):
        line = "this is a line of text"
        self._assert_line(line, line)

    def test_empty_line(self):
        self._assert_line('\n', '')

    def test_escaped_wiki_word(self):
        word = '!EscapedWikiWord'
        self._assert_line(word, word[1:])

    def test_normal_exclamation_mark(self):
        line = "there's !something afoot !"
        self._assert_line(line, line)

    def test_line_contains_only_hyperlink(self):
        target = 'http://robotframework.org'
        link = 'RobotFramework'
        line = '[%s  %s]' % (target, link)
        self._assert_line(line, '`%s`__' % link, [target])

    def test_multi_word_link_name(self):
        target = 'http://robotframework.org'
        link = 'Robot Framework'
        line = '[%s %s]' % (target, link)
        self._assert_line(line, '`%s`__' % link, [target])

    def test_hyperlink_and_other_content(self):
        target = 'http://robotframework.org'
        link = 'RobotFramework'
        template = 'Some content before [%s %s] and after a link'
        self._assert_line(template % (target, link),
                          'Some content before `%s`__ and after a link' % link, [target])

    def test_wiki_word_link(self):
        self._assert_line('[WikiWordLink Alias]', '[[Alias|Wiki Word Link]]')

    def test_single_wiki_word_link(self):
        self._assert_line('[Word Long Alias]', '[[Long Alias|Word]]')

    def test_image_link(self):
        target = 'http://wiki.ex.googlecode.com/hg/img.png'
        self._assert_line('[%s]' % target, '[[%s]]' % 'img.png')

    def test_table_of_contents(self):
        self._assert_line('<wiki:toc/>', '.. contents::\n  :local:')

    def test_table_of_contents_with_depth(self):
        self._assert_line('<wiki:toc max_depth="2"/>', '.. contents::\n  :local:\n  :depth: 2')

    def test_bullet_list(self):
        list_item = '  * a bullet point'
        self._assert_line(list_item, list_item)

    def test_enumerated_list(self):
        self._assert_line(' # point', '  #. point')

    def _assert_line(self, input, expected, links=[]):
        line = Line(input)
        assert_equals(str(line), expected)
        links = ['__ %s' % l for l in links]
        assert_equals(Line(input).links, links)


class TestHeader(_TransformationTest):

    def test_level1(self):
        header = "= Header1 ="
        level_1_symbol = '='
        self._assert_header(header, 'Header1\n' + level_1_symbol * 7)

    def test_level2(self):
        level_2_symbol = '-'
        self._assert_header('==h2==', 'h2\n' + level_2_symbol *2)

    def test_level3(self):
        level_3_symbol = '~'
        self._assert_header('===h3===', 'h3\n' + level_3_symbol *2)

    def test_whitespace_around_header_markers_is_ignored(self):
        self._assert_header(' = =  header= =   ', 'header\n------')

    def _assert_header(self, input, expected):
        self._assert_transformation(Header, input, expected)


class TestBlockQuotes(object):

    def test_one_line_block(self):
        block = ['{{{', 'literal', '}}}']
        expected_lines = ['::', '', '    literal', '']
        self._assert_block_quote(block, '\n'.join(expected_lines))

    def _assert_block_quote(self, input, expected):
        quote = BlockQuote()
        for line in input:
            quote.add(line)
        assert_equals(str(quote), expected)


class TestTables(object):

    def test_simple_table(self):
        line = '''|| a table || with two cols ||
|| text || and longer cell content ||
'''
        table = '''
=======  =======================
a table  with two cols
=======  =======================
text     and longer cell content
=======  =======================
'''
        self._assert_table(line.strip().splitlines(), table.lstrip())

    def _assert_table(self, input, expected):
        table = Table()
        for line in input:
            table.add(line)
        assert_equals(str(table), expected)

def test_integration():
    INPUT = """
#ignored pragma
= Some Header =

Some regular text in a
couple of lines with [http://to.here link] included.

{{{
a literal code
block
}}}

== Smaller header ==
|| header ||row||
||table || content   ||
"""

    EXPECTED = """=====
title
=====

Some Header
===========

Some regular text in a
couple of lines with `link`__ included.

::

    a literal code
    block


Smaller header
--------------
======  =======
header  row
======  =======
table   content
======  =======


__ http://to.here
""".splitlines()

    output = Transformer('title').transform(INPUT.splitlines()).splitlines()
    assert_equals(len(output), len(EXPECTED))
    for actual, expected in zip(output, EXPECTED):
        assert_equals(actual, expected)

class TestLinkListNewLines(object):

    def test_new_lines_at_the_end_of_file_stripped(self):
        input = """
Foo [http://to.here link]



"""
        expected = """=====
title
=====

Foo `link`__

__ http://to.here
""".splitlines()

        self._assert_transformation(input, expected)

    def test_no_new_line_creates_a_separating_new_line(self):
        input = "Foo [http://to.here link]"

        expected = """=====
title
=====

Foo `link`__

__ http://to.here
""".splitlines()

        self._assert_transformation(input, expected)

    def _assert_transformation(self, input, expected):
        output = Transformer('title').transform(input.splitlines()).splitlines()
        assert_equals(len(output), len(expected))
        for actual, expected in zip(output, expected):
            assert_equals(actual, expected)

