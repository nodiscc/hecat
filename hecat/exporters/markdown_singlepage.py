"""Single-page markdown rendering"""

import logging


def to_kebab_case(string):
    """convert a string to kebab-case, remove some special characters"""
    replacements = {
        ' ': '-',
        '(': '',
        ')': ''
    }
    string.translate(str.maketrans(replacements)).lower()
    return string

def to_camel_case(string):
    """convert a string to camel_case, remove some special characters"""
    replacements = {
        ' ': '_',
        '(': '',
        ')': ''
    }
    string.translate(str.maketrans(replacements)).lower()
    return string

def to_markdown_anchor(string):
    """Convert a section name to a markdown anchor link in the form [Tag name](#tag-name)"""
    anchor_url = to_kebab_case(string)
    markdown_anchor = '[{}](#{})'.format(string, anchor_url)
    logging.debug('markdown anchor: %s', markdown_anchor)
    return markdown_anchor

def render_markdown_singlepage_category(tag, software_list):
    """Render a catgeory for the single page markdown output format"""
    # check optional fields
    if 'delegate' in tag and tag['delegate']:
        markdown_delegated_to = '**Please visit {}**\n\n'.format(', '.join(tag['delegate']))
    else:
        markdown_delegated_to = ''
    if 'related_tags' in tag and tag['related_tags']:
        markdown_related_tags = '_Related: {}_\n\n'.format(', '.join(
            to_markdown_anchor(related_tag) for related_tag in tag['related_tags']))
    else:
        markdown_related_tags = ''
    if 'description' in tag and tag['description']:
        markdown_description = tag['description'] + '\n\n'
    else:
        markdown_description = ''
    if 'external_links' in tag and tag['external_links']:
        markdown_external_links = '_See also: {}_\n\n'.format(', '.join(tag['external_links']))
    else:
        markdown_external_links = ''
    # build markdown-formatted category
    markdown_category = '\n### {}\n\n{}{}{}{}{}'.format(
        tag['name'],
        '**[`^        back to top        ^`](#)**\n\n',
        markdown_description,
        markdown_delegated_to,
        markdown_related_tags,
        markdown_external_links
    )
    # list all software whose first tag matches the current tag
    for software in software_list:
        logging.debug('adding project %s to category %s', software['name'], tag['name'])
        if software['tags'][0] == tag['name']:
            markdown_list_item = render_markdown_list_item(software)
            markdown_category = markdown_category + markdown_list_item + '\n'
    return markdown_category

def render_markdown_list_item(software):
    """render a software project info as a markdown list item"""
    # check optional fields
    if 'demo_url' in software:
        markdown_demo = '[Demo]({})'.format(software['demo_url'])
    else:
        markdown_demo = ''
    if 'source_code_url' in software:
        markdown_source_code = '[Source Code]({})'.format(software['source_code_url'])
    else:
        markdown_source_code = ''
    if 'related_software_url' in software:
        markdown_related_software = '[Related software]({})'.format(
            software['related_software_url'])
    else:
        markdown_related_software = ''
    if 'depends_3rdparty' in software and software['depends_3rdparty']:
        markdown_depends_3rdparty = '`⚠` '
    else:
        markdown_depends_3rdparty = ''
    links_list = [markdown_demo, markdown_related_software, markdown_source_code]
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


def render_markdown_singlepage(tags, software_list, args):
    """
    Render a single-page markdown list of all software, grouped by category
    Prepend/append header/footer, categorized list and footer
    A software item is only listed once, under the first item of its 'tags:' list
    @param tags List: tags (dicts) loaded from yaml source files
    @param software_list List: list of dicts loaded from yaml source files
    """
    # pylint: disable=consider-using-with
    markdown_header = open(args.source_directory + '/markdown/header.md', 'r').read()
    markdown_footer = open(args.source_directory + '/markdown/footer.md', 'r').read()
    markdown_software_list = ''
    for tag in tags:
        markdown_category = render_markdown_singlepage_category(tag, software_list)
        markdown_software_list = markdown_software_list + markdown_category + '\n\n'
    markdown = '{}\n\n{}\n\n{}'.format(
        markdown_header, markdown_software_list, markdown_footer)
    return markdown
