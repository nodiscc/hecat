"""Single-page markdown rendering"""

import logging
import ruamel.yaml
from ..utils import list_files, to_kebab_case

yaml = ruamel.yaml.YAML(typ='safe')
yaml.indent(sequence=4, offset=2)

def to_markdown_anchor(string):
    """Convert a section name to a markdown anchor link in the form [Tag name](#tag-name)"""
    anchor_url = to_kebab_case(string)
    markdown_anchor = '[{}](#{})'.format(string, anchor_url)
    return markdown_anchor

def render_markdown_singlepage_category(tag, software_list):
    """Render a category for the single page markdown output format"""
    logging.debug('rendering tag %s' % tag['name'])
    # check optional fields
    markdown_delegate_to = ''
    markdown_related_tags = ''
    markdown_description = ''
    markdown_external_links = ''
    # DEBT factorize
    if 'related_tags' in tag and tag['related_tags']:
        markdown_related_tags = '_Related: {}_\n\n'.format(', '.join(
            to_markdown_anchor(related_tag) for related_tag in tag['related_tags']))
    if 'description' in tag and tag['description']:
        markdown_description = tag['description'] + '\n\n'
    if 'delegate_to' in tag and tag['delegate_to']:
        markdown_delegate_to = '**Please visit {}**\n'.format(', '.join(
            '[{}]({})'.format(
                link['title'], link['url']
        ) for link in tag['delegate_to']))
    if 'external_links' in tag and tag['external_links']:
        markdown_external_links = '_See also: {}_\n\n'.format(', '.join(
            '[{}]({})'.format(
                link['title'], link['url']
            ) for link in tag['external_links']))
    # build markdown-formatted category
    markdown_category = '### {}\n\n{}{}{}{}{}'.format(
        tag['name'],
        '**[`^        back to top        ^`](#)**\n\n',
        markdown_description,
        markdown_delegate_to,
        markdown_related_tags,
        markdown_external_links
    )
    # list all software whose first tag matches the current tag
    for software in software_list:
        if software['tags'][0] == tag['name']:
            markdown_list_item = render_markdown_list_item(software)
            logging.debug('adding project %s to category %s', software['name'], tag['name'])
            markdown_category = markdown_category + markdown_list_item + '\n'
    return markdown_category


def render_markdown_list_item(software):
    """render a software project info as a markdown list item"""
    # check optional fields
    # DEBT use ternary operator
    if 'demo_url' in software:
        markdown_demo = '[Demo]({})'.format(software['demo_url'])
    else:
        markdown_demo = ''
    if 'source_code_url' in software:
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
    markdown_list_item = '- [{}]({}) {}- {}{} {} {}'.format(
        software['name'],
        software['website_url'],
        markdown_depends_3rdparty,
        software['description'],
        markdown_links,
        '`' + '/'.join(software['licenses']) + '`',
        '`' + '/'.join(software['platforms']) + '`'
        )
    return markdown_list_item

# DEBT factorize yaml loading from single/multiple files
def load_yaml_tags(args):
    """load tags data from yaml source files, order alphabetically"""
    tags = list([])
    for file in sorted(list_files(args.source_directory + args.tags_directory)):
        source_file = args.source_directory + args.tags_directory + file
        logging.info('loading tag data from %s', source_file)
        with open(source_file, 'r') as data:
            tags.append(yaml.load(data))
            tags = sorted(tags, key=lambda k: k['name'])
    return tags

# DEBT factorize yaml loading from single/multiple files
def load_yaml_software(args):
    """load software projects definitions from yaml source files"""
    software_list = []
    for file in sorted(list_files(args.source_directory + args.software_directory)):
        source_file = args.source_directory + args.software_directory + file
        logging.info('loading software data from %s', source_file)
        with open(source_file, 'r') as yaml_data:
            software = yaml.load(yaml_data)
            software_list.append(software)
    return software_list

# DEBT factorize yaml loading from single/multiple files
def load_yaml_licenses(args):
    """load license definitions from a single yaml source file"""
    licenses_file = args.source_directory + '/licenses.yml'
    logging.info('loading license data from %s', licenses_file)
    with open(licenses_file, 'r') as data:
        licenses = yaml.load(data)
    return licenses

def render_markown_licenses(licenses):
    """render a markdown-formatted licenses list"""
    markdown_licenses = '---------------------\n\n## List of Licenses\n\n**[`^        back to top        ^`](#)**\n\n'
    for _license in licenses:
        try:
            markdown_licenses += '- `{}` - [{}]({})\n'.format(
                _license['identifier'],
                _license['name'],
                _license['url'])
        except KeyError as err:
            logging.warning('missing fields in license, will not be inserted: %s: KeyError: %s' % (_license, err))
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


def render_markdown_singlepage(args):
    """
    Render a single-page markdown list of all software, grouped by category
    Prepend/append header/footer, categorized list and footer
    A software item is only listed once, under the first item of its 'tags:' list
    @param tags List: tags (dicts) loaded from yaml source files
    @param software_list List: list of dicts loaded from yaml source files
    """
    # pylint: disable=consider-using-with
    tags = load_yaml_tags(args)
    software_list = load_yaml_software(args)
    licenses = load_yaml_licenses(args)
    markdown_header = open(args.source_directory + '/markdown/header.md', 'r').read()
    markdown_footer = open(args.source_directory + '/markdown/footer.md', 'r').read()
    markdown_software_list = '## Software\n\n'
    for tag in tags:
        markdown_category = render_markdown_singlepage_category(tag, software_list)
        markdown_software_list = markdown_software_list + markdown_category + '\n\n'
    markdown_licenses = render_markown_licenses(licenses)
    markdown_toc_section = render_markdown_toc(
        markdown_header,
        markdown_software_list,
        markdown_licenses,
        markdown_footer)
    markdown = '{}\n\n{}\n\n{}\n\n{}\n\n{}'.format(
        markdown_header, markdown_toc_section, markdown_software_list, markdown_licenses, markdown_footer)
    return markdown
