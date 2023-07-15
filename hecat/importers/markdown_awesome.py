"""import data from the awesome-selfhosted markdown format
- https://gitlab.com/nodiscc/toolbox/-/raw/master/DOC/SCREENSHOTS/E4ra3V8.png

# hecat.yml
steps:
  - name: import
    module: importers/markdown_awesome
    module_options:
      source_file: tests/awesome-selfhosted/README.md
      output_directory: tests/awesome-selfhosted-data
      output_licenses_file: licenses.yml # optional, default licenses.yml
      overwrite_tags: False # optional, default False

Source directory structure:
└── README.md

Output directory structure:
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
└── licenses.yml # yaml list of licenses

In addition to the list item format
(https://github.com/awesome-selfhosted/awesome-selfhosted/blob/master/.github/PULL_REQUEST_TEMPLATE.md),
the importer assumes a few things about the original markdown file:
- all level 3 (`###`) titles/sections contain the actual list data/items, other sections must use level 2 headings
- the list of licenses is available in a `## List of Licenses` section

If the source/destination directories are `git` repositories, and you want to import the original
authors/committers list (`git log`) to the destination directory, you must do so manually.
This will let `hecat` generate an `AUTHORS` file retaining all contributors from the original repo:

NEW_REPO=https://github.com/awesome-selfhosted/awesome-selfhosted-data
OLD_REPO=https://github.com/awesome-selfhosted/awesome-selfhosted
git clone $NEW_REPO awesome-selfhosted-data # clone the target/new repository
cd awesome-selfhosted-data # enter the new repository
git remote add old-repo $OLD_REPO # add the old repository as git remote
git remote update # fetch the old repository's history
git checkout old-repo/master # checkout the old repository's master branch
git checkout -b old-repo-master # create a new local branch from this remote branch
git rm -rf * .github # delete all files from the original repository (please check that it is actually empty)
git commit -m "git c -m "clear repository, only import history reference for AUTHORS file generation"
git checkout master # checkout the new repository's master branch again
git merge --allow-unrelated-histories old-repo-master # merge the old repo's master branch instory into the new repo's history
git remote remove old-repo # remove the old repository from git remotes
"""

import os
import sys
import logging
import re
import ruamel.yaml
from ..utils import list_files, to_kebab_case

yaml = ruamel.yaml.YAML()
yaml.indent(sequence=4, offset=2)
yaml.width = 99999

def load_markdown_list_sections(source_file):
    """return original markdown list sections, as a list of dicts:
       title: section title
       text: full section text
    """
    with open(source_file, 'r', encoding="utf-8") as src_file:
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

def import_software(section, step, errors):
    """import all list items from a markdown section/category, to software yaml definitions/files"""
    entries = re.findall("^- .*", section['text'], re.MULTILINE)
    for line in entries:
        logging.debug('importing software from line: %s', line)
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
            error_msg = 'Missing required field in entry: {}'.format(line)
            logging.error(error_msg)
            errors.append(error_msg)
            continue
        if matches.group('links') is not None:
            source_code_url_match = re.match(r".*\[Source Code\]\(([^\)]+).*", matches.group('links'))
            if source_code_url_match is not None:
                entry['source_code_url'] = source_code_url_match.group(1)
            else:
                entry['source_code_url'] = entry['website_url']
            demo_url_match = re.match(r".*\[Demo\]\(([^\)]+).*", matches.group('links'))
            if demo_url_match is not None:
                entry['demo_url'] = demo_url_match.group(1)
            related_software_url_match = re.match(r".*\[Clients\]\(([^\)]+).*", matches.group('links'))
            if related_software_url_match is not None:
                entry['related_software_url'] = related_software_url_match.group(1)
        else:
            entry['source_code_url'] = entry['website_url']
        if matches.group('depends_3rdparty'):
            entry['depends_3rdparty'] = True

        dest_file = '{}/{}'.format(
            step['module_options']['output_directory'] + '/software',
            to_kebab_case(matches.group('name')) + '.yml')
        if os.path.exists(dest_file):
            logging.debug('overwriting target file %s', dest_file)
        while True:
            try:
                with open(dest_file, 'w+', encoding="utf-8") as yaml_file:
                    logging.debug('section %s: writing file %s', section['title'], dest_file)
                    yaml.dump(entry, yaml_file)
                    break
            except FileNotFoundError:
                os.mkdir(step['module_options']['output_directory'] + '/software')

# DEBT factorize extract_external_links, extract_related_tags, extract_redirect
def extract_related_tags(section):
    """Extract 'Related:' tags from markdown section"""
    related_tags = []
    related_markdown = re.findall("^_Related:.*_", section['text'], re.MULTILINE)
    if related_markdown:
        matches = re.findall(r"\[([^\]]*)\]\(([^\)]*)\)", related_markdown[0])
        for match in matches:
            related_tags.append(match[0])
    return related_tags

def extract_redirect(section):
    """extract 'Please visit' link titles/URLs from markdown"""
    redirect = []
    redirect_markdown = re.findall(r'^\*\*Please visit.*\*\*', section['text'], re.MULTILINE)
    if redirect_markdown:
        matches = re.findall(r"\[([^\]]*)\]\(([^\)]*)\)", redirect_markdown[0])
        for match in matches:
            redirect.append({ 'title': match[0], 'url': match[1]})
    return redirect

def extract_external_links(section):
    """Extract 'See also:' links titles/URLs from markdown section"""
    external_links = []
    external_links_markdown = re.findall("^_See also.*_", section['text'], re.MULTILINE)
    if external_links_markdown:
        matches = re.findall(r"\[([^\]]*)\]\(([^\)]*)\)", external_links_markdown[0])
        for match in matches:
            external_links.append({ 'title': match[0], 'url': match[1]})
    return external_links

def extract_description(section):
    """Extract section description from a markdown section"""
    description = ''
    description_markdown = re.findall(r'^(?![#\*_\-\n]).*', section['text'], re.MULTILINE)
    if description_markdown:
        if len(description_markdown) == 1:
            logging.warning("%s has no description", section['title'])
        if len(description_markdown) == 2:
            description = description_markdown[1]
        else:
            logging.warning("%s has more than one description line. Only the first line will be kept", section['title'])
            description = description_markdown[1]
    return description

def import_tag(section, step):
    """create a tag/category yaml file given a source markdown section/category"""
    if 'overwrite_tags' not in step['module_options']:
        step['module_options']['overwrite_tags'] = False
    dest_file = '{}/{}'.format(
        step['module_options']['output_directory'] + '/tags', to_kebab_case(section['title']) + '.yml')
    if os.path.exists(dest_file):
        if not step['module_options']['overwrite_tags']:
            logging.debug('file %s already exists, not overwriting it', dest_file)
            return
        logging.debug('overwriting tag in %s', dest_file)
    related_tags = extract_related_tags(section)
    redirect = extract_redirect(section)
    description = extract_description(section)
    external_links = extract_external_links(section)
    while True:
        try:
            with open(dest_file, 'w+', encoding="utf-8") as yaml_file:
                logging.debug('section %s: writing file %s', section['title'], dest_file)
                output_dict = {
                    'name': section['title'],
                    'description': description,
                }
                if external_links:
                    output_dict['external_links'] = external_links
                if redirect:
                    output_dict['redirect'] = redirect
                if related_tags:
                    output_dict['related_tags'] = related_tags
                yaml.dump(output_dict, yaml_file)
                break
        except FileNotFoundError:
            os.mkdir(step['module_options']['output_directory'] + '/tags')

def import_platforms(yaml_software_files, step):
    """builds a list of language/platforms from all software/YAML files,
    creates corresponding platform/*.yml files"""
    platforms = []
    for file in yaml_software_files:
        with open(step['module_options']['output_directory'] + '/software/' + file, 'r', encoding="utf-8") as file:
            data = yaml.load(file)
            platforms = platforms + data['platforms']
    platforms = list(set(platforms))
    for platform in platforms:
        dest_file = '{}/{}'.format(
            step['module_options']['output_directory'] + '/platforms', to_kebab_case(platform) + '.yml')
        if os.path.exists(dest_file):
            logging.debug('overwriting target file %s', dest_file)
        with open(dest_file, 'w+', encoding="utf-8") as yaml_file:
            logging.debug('writing file %s', dest_file)
            yaml_file.write('name: {}\ndescription: ""'.format(platform))

def import_licenses(step):
    """builds a YAML list of licenses from the List of Licenses section of a markdown file"""
    yaml_licenses = ''
    with open(step['module_options']['source_file'], 'r', encoding="utf-8") as markdown:
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
    if 'output_licenses_file' not in step['module_options']:
        step['module_options']['output_licenses_file'] = 'licenses.yml'
    dest_file = step['module_options']['output_directory'] + '/' + step['module_options']['output_licenses_file']
    with open(dest_file, 'w+', encoding="utf-8") as yaml_file:
        logging.debug('writing file %s', dest_file)
        yaml_file.write(yaml_licenses)

def import_markdown_awesome(step):
    """Import data from an "awesome"-formatted markdown list
    Original list sections must be level 3 titles (###)
    """
    errors = []
    sections = load_markdown_list_sections(step['module_options']['source_file'])
    for section in sections:
        import_software(section, step, errors)
        import_tag(section, step)
    if errors:
        logging.error("There were errors during processing")
        sys.exit(1)
    yaml_software_files = list_files(step['module_options']['output_directory'] + '/software')
    import_platforms(yaml_software_files, step)
    import_licenses(step)
