"""hecat - common utilities"""
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
        '(': '',
        ')': '',
        '&': '',
        '/': '',
        ',': ''
    }
    newstring = string.translate(str.maketrans(replacements)).lower()
    return newstring

# DEBT factorize yaml loading from single/multiple files
def load_yaml_data(path, sort_key=False):
    """load data from YAML source files
    if the path is a file, data will be loaded directly from it
    if the path is a directory, data will be loaded by adding the content of each file in the directory to a list
    if sort_key=SOMEKEY is passed, items will be sorted alphabetically by the specified key"""
    yaml = ruamel.yaml.YAML(typ='rt')
    data = []
    if os.path.isfile(path):
        logging.info('loading data from %s', path)
        with open(path, 'r', encoding="utf-8")) as yaml_data:
            data = yaml.load(yaml_data)
        if sort_key:
            data = sorted(data, key=lambda k: k[sort_key])
        return data
    elif os.path.isdir(path):
        for file in sorted(list_files(path)):
            source_file = path + '/' + file
            logging.debug('loading data from %s', source_file)
            with open(source_file, 'r', encoding="utf-8") as yaml_data:
                item = yaml.load(yaml_data)
                data.append(item)
            if sort_key:
                data = sorted(data, key=lambda k: k[sort_key])
        return data
    else:
        logging.error('%s is not a file or directory', path)
        exit(1)

# DEBT factorize yaml loading from single/multiple files
def load_config(config_file):
    """load steps/settings from a configuration file"""
    yaml = ruamel.yaml.YAML(typ='rt')
    logging.debug('loading configuration from %s', config_file)
    if not os.path.isfile(config_file):
        logging.error('configuration file %s does not exist')
        exit(1)
    with open(config_file, 'r', encoding="utf-8") as cfg:
        config = yaml.load(cfg)
    return config