"""Import data to YAML from an "awesome"-formatted markdown list"""

import os
import sys
import logging
import re
import yaml
from ..utils import list_files, to_kebab_case


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
    if len(entries) == 0:
        logging.warning('%s has no entries, no .yml file will be created for this tag',
                        section['title'])
    for line in entries:
        matches = re.match(r"\- \[(?P<name>.*)\]\((?P<website_url>[^\)]+)\) (?P<depends_3rdparty>`⚠` )?- (?P<description>.*\.) ((?P<links>.*)\)\) )?`(?P<license>.*)` `(?P<language>.*)`", line) # pylint: disable=line-too-long
        name = 'name: {}'.format(matches.group('name'))
        website_url = 'website_url: "{}"'.format(matches.group('website_url'))
        tags = 'tags:\n  - {}'.format(section['title'])
        description = 'description: "{}"'.format(matches.group('description'))
        licenses = 'licenses:\n{}'.format(
            yaml.dump(matches.group('license').split('/'), default_flow_style=False)
            ).replace('\n-','\n  -')[:-1]
        platforms = 'platforms:\n{}'.format(
            yaml.dump(matches.group('language').split('/'), default_flow_style=False)
            ).replace('\n-','\n  -')[:-1]

        # pylint: disable=line-too-long
        source_code_url = ''
        demo_url = ''
        related_software_url = ''
        if matches.group('links') is not None:
            source_code_url_match = re.match(r".*\[Source Code\]\(([^\)]+).*", matches.group('links'))
            demo_url_match = re.match(r".*\[Demo\]\(([^\)]+).*", matches.group('links'))
            related_software_url_match = re.match(r".*\[Clients\]\(([^\)]+).*", matches.group('links'))
            source_code_url = ''
            demo_url = ''
            related_software_url = ''
            if source_code_url_match is not None:
                source_code_url = 'source_code_url: "{}"\n'.format(source_code_url_match.group(1))
            if demo_url_match is not None:
                demo_url = 'demo_url: "{}"\n'.format(demo_url_match.group(1))
            if related_software_url_match is not None:
                related_software_url = 'related_software_url: "{}"\n'.format(related_software_url_match.group(1))

        depends_3rdparty = ''
        if matches.group('depends_3rdparty'):
            depends_3rdparty = 'depends_3rdparty: yes'

        yaml_list_item = '{}\n{}\n{}{}{}\n{}\n{}\n{}\n{}\n{}\n'.format(
            name, website_url, source_code_url, demo_url, description, licenses,
            platforms, tags, depends_3rdparty, related_software_url)
        dest_file = '{}/{}'.format(
            args.output_directory + args.software_directory, matches.group('name').lower().replace(' ', '-') + '.yml')
        if os.path.exists(dest_file):
            logging.error('target file %s already exists.', dest_file)
            sys.exit(1)
        with open(dest_file, 'w+') as yaml_file:
            logging.info('section %s: writing file %s', section['title'], dest_file)
            yaml_file.write(yaml_list_item)

def import_tag(section, args):
    """create a tag/category yaml file given a source markdown section/category"""
    dest_file = '{}/{}'.format(
        args.output_directory + args.tags_directory, to_kebab_case(section['title']) + '.yml')
    if os.path.exists(dest_file):
        logging.error('target file %s already exists.', dest_file)
        sys.exit(1)
    with open(dest_file, 'w+') as yaml_file:
        logging.info('section %s: writing file %s', section['title'], dest_file)
        yaml_file.write('name: {}\ndescription: ""\nrelated_tags: []'.format(
            section['title']))

def import_platforms(yaml_software_files, args):
    """builds a list of language/platforms from all software/YAML files,
    creates corresponding platform/*.yml files"""
    platforms = []
    for file in yaml_software_files:
        with open(args.output_directory + args.software_directory + '/' + file, 'r') as file:
            logging.debug('working on %s', file)
            data = yaml.load(file, Loader=CLoader)
            platforms = platforms + data['platforms']
    platforms = list(set(platforms))
    logging.debug('platforms: %s', platforms)
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
