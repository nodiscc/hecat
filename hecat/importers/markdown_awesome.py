"""Import data to YAML from an "awesome"-formatted markdown list"""

import os
import sys
import logging
import re
from ..utils import list_files, to_kebab_case
import ruamel.yaml

yaml = ruamel.yaml.YAML()
yaml.indent(sequence=4, offset=2)

def load_markdown_list_sections(args):
    """return original markdown list sections, as a list of dicts:
       title: section title
       text: full section text
    """
    with open(args.source_file) as src_file:
        src = src_file.read()
        sections = []
        for section in src.split('### '):
            title = section.partition('\n')[0]
            sections.append({ 'title': title, 'text': section })
        # remove everything before first ###
        sections.pop(0)
        # only keep the part above ## (beginning of next level 2 section) from the last section
        sections[-1]['text'] = sections[-1]['text'].split('## ')[0]
    return sections

def import_software(section, args):
    """import all list items from a markdown section/category, to software yaml definitions/files"""
    entries = re.findall("^- .*", section['text'], re.MULTILINE)
    for line in entries:
        logging.debug('importing software from line: %s' % line)
        matches = re.match(r"\- \[(?P<name>.*)\]\((?P<website_url>[^\)]+)\) (?P<depends_3rdparty>`⚠` )?- (?P<description>.*\.) ((?P<links>.*)\)\) )?`(?P<license>.*)` `(?P<language>.*)`", line) # pylint: disable=line-too-long
        entry = {}
        try:
            entry['name'] = matches.group('name')
            entry['website_url'] = matches.group('website_url')
            entry['description'] = matches.group('description')
            entry['licenses'] = matches.group('license').split('/')
            entry['platforms'] = matches.group('language').split('/')
            entry['tags'] = [section['title']]
        except AttributeError:
            logging.exception('Missing required field in entry: %s' % line)
            raise
        if matches.group('links') is not None:
            source_code_url_match = re.match(r".*\[Source Code\]\(([^\)]+).*", matches.group('links'))
            if source_code_url_match is not None:
                entry['source_code_url'] = source_code_url_match.group(1)
            demo_url_match = re.match(r".*\[Demo\]\(([^\)]+).*", matches.group('links'))
            if demo_url_match is not None:
                entry['demo_url'] = demo_url_match.group(1)
            related_software_url_match = re.match(r".*\[Clients\]\(([^\)]+).*", matches.group('links'))
            if related_software_url_match is not None:
                entry['related_software_url'] = related_software_url_match.group(1)
        if matches.group('depends_3rdparty'):
            entry['depends_3rdparty'] = True

        dest_file = '{}/{}'.format(
            args.output_directory + args.software_directory, to_kebab_case(matches.group('name')) + '.yml')
        if os.path.exists(dest_file):
            logging.error('target file %s already exists.', dest_file)
            sys.exit(1)
        with open(dest_file, 'w+') as yaml_file:
            logging.info('section %s: writing file %s', section['title'], dest_file)
            yaml.dump(entry, yaml_file)

# DEBT factorize extract_external_links, extract_related_tags, extract_delegate_to
def extract_related_tags(section):
    related_tags = []
    related_markdown = re.findall("^_Related:.*_", section['text'], re.MULTILINE)
    if related_markdown:
        matches = re.findall(r"\[([^\]]*)\]\(([^\)]*)\)", related_markdown[0])
        for match in matches:
            related_tags.append(match[0])
    return related_tags

def extract_delegate_to(section):
    delegate_to = []
    delegate_to_markdown = re.findall("^\*\*Please visit.*\*\*", section['text'], re.MULTILINE)
    if delegate_to_markdown:
        matches = re.findall(r"\[([^\]]*)\]\(([^\)]*)\)", delegate_to_markdown[0])
        for match in matches:
            delegate_to.append({ 'title': match[0], 'url': match[1]})
    return delegate_to

def extract_external_links(section):
    external_links = []
    external_links_markdown = re.findall("^_See also.*_", section['text'], re.MULTILINE)
    if external_links_markdown:
        matches = re.findall(r"\[([^\]]*)\]\(([^\)]*)\)", external_links_markdown[0])
        for match in matches:
            external_links.append({ 'title': match[0], 'url': match[1]})
    return external_links

def extract_description(section):
    description = ''
    description_markdown = re.findall("^(?![#\*_\-\n]).*", section['text'], re.MULTILINE)
    if description_markdown:
        if len(description_markdown) == 1:
            logging.warning("%s has no description" % section['title'])
        if len(description_markdown) == 2:
            description = description_markdown[1]
        else:
            logging.warning("%s has more than one description line. Only the first line will be kept" % section['title'])
            description = description_markdown[1]
    return description

def import_tag(section, args):
    """create a tag/category yaml file given a source markdown section/category"""
    dest_file = '{}/{}'.format(
        args.output_directory + args.tags_directory, to_kebab_case(section['title']) + '.yml')
    if os.path.exists(dest_file):
        logging.error('target file %s already exists.', dest_file)
        sys.exit(1)
    related_tags = extract_related_tags(section)
    delegate_to = extract_delegate_to(section)
    description = extract_description(section)
    external_links = extract_external_links(section)
    with open(dest_file, 'w+') as yaml_file:
        logging.info('section %s: writing file %s', section['title'], dest_file)
        output_dict = {
            'name': section['title'],
            'description': description,
            'related_tags': related_tags,
            'delegate_to': delegate_to,
            'external_links': external_links
        }
        yaml.dump(output_dict, yaml_file)

def import_platforms(yaml_software_files, args):
    """builds a list of language/platforms from all software/YAML files,
    creates corresponding platform/*.yml files"""
    platforms = []
    for file in yaml_software_files:
        with open(args.output_directory + args.software_directory + '/' + file, 'r') as file:
            data = yaml.load(file)
            platforms = platforms + data['platforms']
    platforms = list(set(platforms))
    for platform in platforms:
        dest_file = '{}/{}'.format(
            args.output_directory + args.platforms_directory, to_kebab_case(platform) + '.yml')
        if os.path.exists(dest_file):
            logging.error('target file %s already exists.', dest_file)
            sys.exit(1)
        with open(dest_file, 'w+') as yaml_file:
            logging.info('writing file %s', dest_file)
            yaml_file.write('name: {}\ndescription: ""'.format(platform))

def convert_licenses(args):
    """builds a YAML list of licenses from the List of Licenses section of a markdown file"""
    yaml_licenses = ''
    with open(args.source_file, 'r') as markdown:
        data = markdown.read()
        licenses_section = data.split('## List of Licenses')[1].split('## ')[0]
        entries = re.findall("^- .*", licenses_section, re.MULTILINE)
        # pylint: disable=line-too-long
        for line in entries:
            matches = re.match(r"\- \`(?P<identifier>.*)\` - (\[(?P<name>.*)\]\((?P<url>.*)\))?", line)
            yaml_identifier = '- identifier: {}\n'.format(matches.group('identifier'))
            yaml_name = ('  name: {}\n'.format(matches.group('name')) if (matches.group('name')) is not None else '')
            yaml_url = ('  url: {}\n'.format(matches.group('url')) if (matches.group('url')) is not None else '')
            yaml_list_item = '{}{}{}'.format(yaml_identifier, yaml_name, yaml_url)
            yaml_licenses = yaml_licenses + '\n' + yaml_list_item
    dest_file = args.output_directory + '/licenses.yml'
    with open(dest_file, 'w+') as yaml_file:
        logging.info('writing file %s', dest_file)
        yaml_file.write(yaml_licenses)

def import_markdown_awesome(args):
    """Import data from an "awesome"-formatted markdown list
    Original list sections must be level 3 titles (###)
    """
    sections = load_markdown_list_sections(args)
    # output yaml
    for section in sections:
        import_software(section, args)
        import_tag(section, args)
    yaml_software_files = list_files(args.output_directory + args.software_directory)
    import_platforms(yaml_software_files, args)
    convert_licenses(args)
