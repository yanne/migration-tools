"""Wiki transformer: transform from Google Code Wiki markup to reStructuredTest

Uasge: transformer.py infile [outfile]

If outfile is not given, transformation is done in-place.
"""

import re
import os
import sys


class Line(object):
    _escaped_wiki_word_re = re.compile('!([A-Z])')
    _link_re = re.compile('\[(\\S*) +(.*?)\]')
    _wiki_word_pattern = '([A-Z][a-z]*)'
    _wiki_word_matcher = re.compile('(%s{2,})' % _wiki_word_pattern)
    _image_link_matcher = re.compile('\[http://wiki\..*?\.googlecode\.com/hg/(.*?)\]')
    _toc_re = re.compile('<wiki:toc *(max_depth=[\'"](\\d)[\'"])? */>')
    _enumerated_list_re = re.compile('^ *#')

    def __init__(self, line):
        self.links = []
        self._line = self._transform_line(line).rstrip()

    def _transform_line(self, orig_line):
        line = orig_line.rstrip()
        line = self._link_re.sub(self._transform_link, line)
        line = self._toc_re.sub(self._transform_toc, line)
        line = self._image_link_matcher.sub(self._transform_image, line)
        line = self._enumerated_list_re.sub('  #.', line)
        return self._escaped_wiki_word_re.sub('\\1', line)

    def _transform_link(self, match):
        target = match.group(1)
        if self._wiki_word_matcher.match(target):
            wikiword = self._wiki_word_matcher.match(target).group(1)
            parts = re.findall(self._wiki_word_pattern, wikiword)
            return '[[%s|%s]]' % (match.group(2), ' '.join(parts))
        if target.startswith('#'):
            target = '`%s`_' % target[1:].replace('_', ' ')
        self.links.append('__ %s' % target)
        return '`%s`__' % match.group(2)

    def _transform_toc(self, match):
        toc = '.. contents::\n  :local:'
        if match.group(1):
            toc += '\n  :depth: %s' % match.group(2)
        return toc

    def _transform_image(self, match):
        return '[[%s]]' % match.group(1)

    def __str__(self):
        return self._line


class Table(object):
    _table_cell_separator = '||'

    def __init__(self):
        self._lines = []

    def matches(self, line):
        return line.startswith(self._table_cell_separator) and \
            line.endswith(self._table_cell_separator)

    def add(self, line):
        cells = [c.strip() for c in line.split(self._table_cell_separator)
                 if c.strip()]
        self._lines.append(cells)

    def __str__(self):
        return '\n'.join(self._get_table_lines()) + '\n'

    def _get_table_lines(self):
        table_indicator = '  '.join('=' * w for w in self._col_widths())
        lines = [self._pad(l) for l in self._lines]
        lines.insert(0, table_indicator)
        lines.insert(2, table_indicator)
        if len(self._lines) > 1:
            lines.append(table_indicator)
        return lines

    def _col_widths(self):
        widths = [len(c) for c in self._lines[0]]
        for row in self._lines:
            for idx, cell in enumerate(row):
                widths[idx] = max(widths[idx], len(cell))
        return widths

    def _pad(self, row):
        return '  '.join(c.ljust(w) for c, w in
                         zip(row, self._col_widths())).strip()


class BlockQuote(object):

    def __init__(self):
        self._lines = []
        self._started = False
        self._finished = False

    def matches(self, line):
        line = line.strip()
        if line.startswith('{{{'):
            self._started = True
        return self._started and not self._finished

    def add(self, line):
        if line.startswith('}}}'):
            self._finished = True
        if line not in ['{{{', '}}}']:
            self._lines.append(line)

    def __str__(self):
        return '::\n\n' + '\n'.join(['    ' + l for l in self._lines]) + '\n'


class Header(object):
    _levels = {1: '=', 2: '-', 3: "~"}

    def __init__(self):
        self._content = ''

    def matches(self, line):
        line = line.strip()
        return line.startswith('=') and line.endswith('=')

    def add(self, line):
        level = line.count('=') / 2
        line = line.strip('= ')
        self._content = line + '\n' + len(line) * self._levels[level]

    def __str__(self):
        return self._content


class Transformer(object):

    def __init__(self, title):
        self._links = []
        self._elements = []
        self._current = None
        self._title = title

    def transform(self, lines):
        for l in lines:
            if not self._is_ignored_pragma_line(l):
                self._transform_line(l)
        return self._format_title() + self._format_elements() + \
                self._format_links() + '\n'

    def _is_ignored_pragma_line(self, line):
        return not self._elements and (line.startswith('#') or not line.strip())

    def _transform_line(self, orig_line):
        line = Line(orig_line)
        self._links.extend(line.links)
        if self._extends_current_element(orig_line):
            self._current.add(str(line))
        else:
            self._elements.append(self._next_element(line))

    def _extends_current_element(self, line):
        return self._current and self._current.matches(line)

    def _next_element(self, line):
        for elem_class in Header, BlockQuote, Table:
            elem = elem_class()
            if elem.matches(str(line)):
                elem.add(str(line))
                self._current = elem
                return elem
        return line

    def _format_title(self):
        decoration = '=' * len(self._title)
        return '%s\n%s\n%s\n\n' % (decoration, self._title, decoration)

    def _format_elements(self):
        return '\n'.join([str(e) for e in self._elements])

    def _format_links(self):
        if self._links:
            return '\n' + '\n'.join(self._links)
        return ''


def transform(inpath, outpath=None):
    outpath = outpath or inpath
    title = os.path.splitext(os.path.basename(outpath))[0].replace('-', ' ')
    with open(inpath) as infile:
        content = infile.readlines()
    with open(outpath or inpath, 'w') as outfile:
        outfile.write(Transformer(title).transform(content))
    return 0


if __name__ == '__main__':
    if len(sys.argv) == 1 or '-h' in sys.argv or '--help' in sys.argv:
        print __doc__
        sys.exit(1)
    sys.exit(transform(*sys.argv[1:]))
