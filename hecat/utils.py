"""hecat - common utilities"""
import sys
import os
import ruamel.yaml
import logging

def list_files(directory):
    """list files in a directory, return an alphabetically sorted list"""
    source_files = []
    for _, _, files in os.walk(directory):
        for file in files:
            source_files.append(file)
    return source_files

def to_kebab_case(string):
    """convert a string to kebab-case, remove some special characters"""
    replacements = {
        ' ': '-',
        ':': '-',
        '(': '',
        ')': '',
        '&': '',
        '/': '',
        ',': '',
        '*': ''
    }
    newstring = string.translate(str.maketrans(replacements)).lower()
    return newstring

def load_yaml_data(path, sort_key=False):
    """load data from YAML source files
    if the path is a file, data will be loaded directly from it
    if the path is a directory, data will be loaded by adding the content of each file in the directory to a list
    if sort_key=SOMEKEY is passed, items will be sorted alphabetically by the specified key"""
    yaml = ruamel.yaml.YAML(typ='rt')
    data = []
    if os.path.isfile(path):
        logging.debug('loading data from %s', path)
        with open(path, 'r', encoding="utf-8") as yaml_data:
            data = yaml.load(yaml_data)
        if sort_key:
            data = sorted(data, key=lambda k: k[sort_key].upper())
        return data
    elif os.path.isdir(path):
        for file in sorted(list_files(path)):
            source_file = path + '/' + file
            logging.debug('loading data from %s', source_file)
            with open(source_file, 'r', encoding="utf-8") as yaml_data:
                item = yaml.load(yaml_data)
                data.append(item)
            if sort_key:
                data = sorted(data, key=lambda k: k[sort_key].upper())
        return data
    else:
        logging.error('%s is not a file or directory', path)
        sys.exit(1)

def load_config(config_file):
    """load steps/settings from a configuration file"""
    yaml = ruamel.yaml.YAML(typ='rt')
    logging.debug('loading configuration from %s', config_file)
    if not os.path.isfile(config_file):
        logging.error('configuration file %s does not exist')
        sys.exit(1)
    with open(config_file, 'r', encoding="utf-8") as cfg:
        config = yaml.load(cfg)
    return config

def render_markdown_licenses(step, licenses, back_to_top_url=None):
    """render a markdown-formatted licenses list"""
    if back_to_top_url is not None:
        markdown_licenses = '--------------------\n\n## List of Licenses\n\n**[`^        back to top        ^`](' + back_to_top_url + ')**\n\n'
    else:
        markdown_licenses = markdown_licenses = '\n--------------------\n\n## List of Licenses\n\n'
    for _license in licenses:
        if step['module_options']['exclude_licenses']:
            if _license['identifier'] in step['module_options']['exclude_licenses']:
                logging.debug('license identifier %s listed in exclude_licenses, skipping', _license['identifier'])
                continue
        elif step['module_options']['include_licenses']:
            if _license['identifier'] not in step['module_options']['include_licenses']:
                logging.debug('license identifier %s not listed in include_licenses, skipping', _license['identifier'])
                continue
        try:
            markdown_licenses += '- `{}` - [{}]({})\n'.format(
                _license['identifier'],
                _license['name'],
                _license['url'])
        except KeyError as err:
            logging.error('missing fields in license %s: KeyError: %s', _license, err)
            sys.exit(1)
    return markdown_licenses

def write_data_file(step, items):
    """write updated data back to the data file"""
    yaml = ruamel.yaml.YAML(typ='rt')
    yaml.indent(sequence=2, offset=0)
    yaml.width = 99999
    with open(step['module_options']['data_file'] + '.tmp', 'w', encoding="utf-8") as temp_yaml_file:
        logging.info('writing temporary data file %s', step['module_options']['data_file'] + '.tmp')
        yaml.dump(items, temp_yaml_file)
    logging.info('writing data file %s', step['module_options']['data_file'])
    os.rename(step['module_options']['data_file'] + '.tmp', step['module_options']['data_file'])
