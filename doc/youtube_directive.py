# $Id: misc.py 8257 2019-06-24 17:11:29Z milde $
# Authors: David Goodger <goodger@python.org>; Dethe Elza
# Copyright: This module has been placed in the public domain.

"""Miscellaneous directives."""

__docformat__ = 'reStructuredText'
__version__ = "0.1.0"

import sys
import re
from docutils import nodes
from docutils.parsers.rst import directives
from docutils.utils.error_reporting import ErrorString

from sphinx import addnodes
from sphinx.util import parselinenos
from sphinx.util.docutils import SphinxDirective

if False:
    # For type annotation
    from typing import Any, Dict, List, Tuple  # NOQA
    from sphinx.application import Sphinx  # NOQA
    from sphinx.config import Config  # NOQA


class Youtube(SphinxDirective):

    """
    Wrap YouTube URLs in embedding HTML

    Content is included in output based on type argument

    Content may be included inline (content section of directive) or
    imported from a file or url.
    """

    embed_template = """
<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; height: auto;">
  <iframe src="{url}" frameborder="0" allowfullscreen style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"></iframe>
</div>
"""

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {'target': directives.unchanged_required,
                   'encoding': directives.encoding}
    has_content = True

    def run(self):
        if not self.state.document.settings.raw_enabled:
            raise self.warning('"%s" directive disabled.' % self.name)
        attributes = {'format': 'html'}
        encoding = self.options.get(
            'encoding', self.state.document.settings.input_encoding)
        e_handler=self.state.document.settings.input_encoding_error_handler
        if self.content:
            raise self.error(
                '"%s" directive may not have content.' % self.name)

        target = self.arguments[0]

        id = ""
        try:
            results = re.match(
                r'https.*(embed/|/|\?v=)(?P<ID>[a-zA-Z0-9_-]*)(?:/?)$',
                target)
            if results and 'ID' in results.groupdict():
                id = results.group('ID')
            else:
                id = target
        except AttributeError:
            pass

        try:
            url = 'https://www.youtube.com/embed/{id}'.format(id=id)
            text = self.embed_template.format(url=url)
        except UnicodeError as error:
            raise self.severe('Problem with "%s" directive:\n%s'
                              % (self.name, ErrorString(error)))

        raw_node = nodes.raw('', text, **attributes)
        (raw_node.source, raw_node.line) = \
            self.state_machine.get_source_and_line(self.lineno)
        return [raw_node]


def setup(app):
    # type: (Sphinx) -> Dict[str, Any]
    directives.register_directive('youtube', Youtube)

    return {
        'version': __version__,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
