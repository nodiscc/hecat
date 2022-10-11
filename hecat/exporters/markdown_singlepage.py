"""export data to single markdown document suitable for "awesome" lists
- https://github.com/sindresorhus/awesome
- https://i.imgur.com/rJyCEFw.png

$ git clone https://github.com/awesome-selfhosted/awesome-selfhosted
$ git clone https://github.com/awesome-selfhosted/awesome-selfhosted-data
$ $EDITOR .hecat.yml
$ hecat

# .hecat.yml
steps:
  - name: export YAML data to single-page markdown
    module: exporters/markdown_singlepage
    module_options:
      source_directory: awesome-selfhosted-data
      output_directory: awesome-selfhosted
      output_file: README.md
      authors_file: AUTHORS.md # optional, default no authors file
      exclude_licenses: # optional, default []
        - 'CC-BY-NC-4.0'
        - '⊘ Proprietary'
        - 'SSPL-1.0'

Output directory structure:
└── README.md
└── AUTHORS.md

Source YAML directory structure:
├── markdown
│   ├── header.md # markdown footer to render in the final single-page document
│   └── footer.md # markdown header to render in the final single-page document
├── software
│   ├── mysoftware.yml # .yml files containing software data
│   ├── someothersoftware.yml
│   └── ...
├── platforms
│   ├── bash.yml # .yml files containing language/platforms data
│   ├── python.yml
│   └── ...
├── tags
│   ├── groupware.yml # .yml files containing tags/categories data
│   ├── enterprise-resource-planning.yml
│   └── ...
├── licenses.yml # yaml list of licenses
└── tools

Files containing software data must be formatted as follows:

# software/my-awesome-software.yml
name: "My awesome software" # required
website_url: "https://my.awesome.softwar.e" # required
source_code_url: "https://gitlab.com/awesome/software" # required
description: "A description of my awesome software." # required
licenses: # required, all licenses must be listed in licenses.yml
  - Apache-2.0
  - AGPL-3.0
platforms: # required, all platforms must be listed in platforms/*.yml
  - Java
  - Python
  - PHP
  - Nodejs
  - Deb
  - Docker
tags: # required, all tags must be listed in tags/*.yml
  - Automation
  - Calendar
  - File synchronization
demo_url: "https://my.awesome.softwar.e/demo" # optional
related_software_url: "https://my.awesome.softwar.e/apps" # optional
depends_3rdparty: yes # optional, default no
github_last_update: "20200202T20:20:20Z" # optional, auto-generated, last update/commit date for github projects
stargazers_count: "999"  # optional, auto-generated, number of stars for github projects

Files containing platforms/languages must be formatted as follows:

name: Document management # required
description: "[Document management systems (DMS)](https://en.wikipedia.org/wiki/Document_management_system) are used to receive, track, manage and store documents and reduce paper" # required, markdown
related_tags: # optional
  - E-books and Integrated Library Systems (ILS)
  - Archiving and Digital Preservation
redirect: # optional, URLs of other collaborative lists which should be used instead
  - https://another.awesome.li.st
  - https://gitlab.com/user/awesome-list

the authors_file, if set, will be generated from the `git shortlog` of your source directory.
"""

import logging
import ruamel.yaml
from ..utils import to_kebab_case, load_yaml_data

yaml = ruamel.yaml.YAML(typ='safe')
yaml.indent(sequence=4, offset=2)

def to_markdown_anchor(string):
    """Convert a section name to a markdown anchor link in the form [Tag name](#tag-name)"""
    anchor_url = to_kebab_case(string)
    markdown_anchor = '[{}](#{})'.format(string, anchor_url)
    return markdown_anchor

def render_markdown_singlepage_category(step, tag, software_list):
    """Render a category for the single page markdown output format"""
    logging.debug('rendering tag %s', tag['name'])
    # check optional fields
    markdown_redirect = ''
    markdown_related_tags = ''
    markdown_description = ''
    markdown_external_links = ''
    # DEBT factorize
    if 'related_tags' in tag and tag['related_tags']:
        markdown_related_tags = '_Related: {}_\n\n'.format(', '.join(
            to_markdown_anchor(related_tag) for related_tag in tag['related_tags']))
    if 'description' in tag and tag['description']:
        markdown_description = tag['description'] + '\n\n'
    if 'redirect' in tag and tag['redirect']:
        markdown_redirect = '**Please visit {}**\n\n'.format(', '.join(
            '[{}]({})'.format(
                link['title'], link['url']
        ) for link in tag['redirect']))
    if 'external_links' in tag and tag['external_links']:
        markdown_external_links = '_See also: {}_\n\n'.format(', '.join(
            '[{}]({})'.format(
                link['title'], link['url']
            ) for link in tag['external_links']))
    # build markdown-formatted category
    markdown_category = '### {}{}{}{}{}{}'.format(
        tag['name'] + '\n\n',
        '**[`^        back to top        ^`](#)**\n\n',
        markdown_description,
        markdown_redirect,
        markdown_related_tags,
        markdown_external_links
    )
    # list all software whose first tag matches the current tag, and does not have a license excluded by module options
    for software in software_list:
        if any(license in software['licenses'] for license in step['module_options']['exclude_licenses']):
            logging.debug("%s has a license listed in exclude_licenses, skipping", software['name'])
        elif software['tags'][0] == tag['name']:
            markdown_list_item = render_markdown_list_item(software)
            logging.debug('adding project %s to category %s', software['name'], tag['name'])
            markdown_category = markdown_category + markdown_list_item
    return markdown_category + '\n\n'


def render_markdown_list_item(software):
    """render a software project info as a markdown list item"""
    # check optional fields
    # DEBT use ternary operator
    if 'demo_url' in software:
        markdown_demo = '[Demo]({})'.format(software['demo_url'])
    else:
        markdown_demo = ''
    if not software['source_code_url'] == software['website_url']:
        markdown_source_code = '[Source Code]({})'.format(software['source_code_url'])
    else:
        markdown_source_code = ''
    if 'related_software_url' in software:
        markdown_related_software = '[Clients]({})'.format(
            software['related_software_url'])
    else:
        markdown_related_software = ''
    if 'depends_3rdparty' in software and software['depends_3rdparty']:
        markdown_depends_3rdparty = '`⚠` '
    else:
        markdown_depends_3rdparty = ''
    links_list = [markdown_demo, markdown_source_code, markdown_related_software]
    # remove empty links from list
    links = [link for link in links_list if link]
    markdown_links = ' ({})'.format(', '.join(links)) if links else ''
    # build markdown-formatted list item
    markdown_list_item = '- [{}]({}) {}- {}{} {} {}\n'.format(
        software['name'],
        software['website_url'],
        markdown_depends_3rdparty,
        software['description'],
        markdown_links,
        '`' + '/'.join(software['licenses']) + '`',
        '`' + '/'.join(software['platforms']) + '`'
        )
    return markdown_list_item



def render_markown_licenses(licenses):
    """render a markdown-formatted licenses list"""
    markdown_licenses = '--------------------\n\n## List of Licenses\n\n**[`^        back to top        ^`](#)**\n\n'
    for _license in licenses:
        try:
            markdown_licenses += '- `{}` - [{}]({})\n'.format(
                _license['identifier'],
                _license['name'],
                _license['url'])
        except KeyError as err:
            logging.warning('missing fields in license, will not be inserted: %s: KeyError: %s', _license, err)
    return markdown_licenses

def render_markdown_toc(*args):
    """render a markdown-formatted table of contents"""
    markdown = ''
    for i in args:
        markdown += i
    markdown_toc = '## Table of contents\n\n'
    # DEBT factorize
    for line in markdown.split('\n'):
        if line.startswith('## '):
            toc_entry = '- [{}](#{})\n'.format(line[3:], to_kebab_case(line)[3:])
            markdown_toc = markdown_toc + toc_entry
        if line.startswith('### '):
            toc_entry = '  - [{}](#{})\n'.format(line[4:], to_kebab_case(line)[4:])
            markdown_toc = markdown_toc + toc_entry
    markdown_toc = markdown_toc + '\n--------------------'
    return markdown_toc

def render_markdown_authors(step):
    """render a markdown-formatted table of authors"""
    import subprocess
    import re
    logging.info('generating authors file %s', step['module_options']['authors_file'])
    table_header = "|Commits | Author |\n| :---: | --- |"
    git_process = subprocess.Popen(['/usr/bin/git', 'shortlog', '-s', '-n', '-e'],
                                   cwd=step['module_options']['source_directory'],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   universal_newlines=True)
    authors, err = git_process.communicate()
    authors = re.sub(r"^\s*(\d*?)\s(.*?)$", r"|\1|\2|", authors)
    markdown_authors = '{}\n{}'.format(table_header, authors)
    with open(step['module_options']['output_directory'] + '/AUTHORS.md', 'w+', encoding="utf-8") as outfile:
        outfile.write(markdown_authors)

def render_markdown_singlepage(step):
    """
    Render a single-page markdown list of all software, grouped by category
    Prepend/append header/footer, categorized list and footer
    A software item is only listed once, under the first item of its 'tags:' list
    """
    # pylint: disable=consider-using-with
    tags = load_yaml_data(step['module_options']['source_directory'] + '/tags', sort_key='name')
    software_list = load_yaml_data(step['module_options']['source_directory'] + '/software')
    licenses = load_yaml_data(step['module_options']['source_directory'] + '/licenses.yml')
    markdown_header = open(step['module_options']['source_directory'] + '/markdown/header.md', 'r').read()
    markdown_footer = open(step['module_options']['source_directory'] + '/markdown/footer.md', 'r').read()
    markdown_software_list = '## Software\n\n'
    if 'exclude_licenses' not in step['module_options']:
        step['module_options']['exclude_licenses'] = []
    for tag in tags:
        markdown_category = render_markdown_singlepage_category(step, tag, software_list)
        markdown_software_list = markdown_software_list + markdown_category
    markdown_licenses = render_markown_licenses(licenses)
    markdown_toc_section = render_markdown_toc(
        markdown_header,
        markdown_software_list,
        markdown_licenses,
        markdown_footer)
    markdown = '{}\n\n{}\n\n{}{}\n\n{}'.format(
        markdown_header, markdown_toc_section, markdown_software_list, markdown_licenses, markdown_footer)
    with open(step['module_options']['output_directory'] + '/' + step['module_options']['output_file'], 'w+', encoding="utf-8") as outfile:
        outfile.write(markdown)
    if 'authors_file' in step['module_options']:
        render_markdown_authors(step)
