"""AUTHORS.md markdown rendering"""

import logging
import subprocess
import re

def render_markdown_authors(args):
    table_header = "|Commits | Author |\n| :---: | --- |"
    git_process = subprocess.Popen(['/usr/bin/git', 'shortlog', '-s', '-n', '-e'],
                                   cwd=args.source_directory,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   universal_newlines=True)
    authors, err = git_process.communicate()
    authors = re.sub(r"^\s*(\d*?)\s(.*?)$", r"|\1|\2|", authors)
    markdown_authors = '{}\n{}'.format(table_header, authors)
    return markdown_authors
