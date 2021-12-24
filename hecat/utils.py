"""hecat - common utilities"""
import os
import ruamel.yaml
import logging

yaml = ruamel.yaml.YAML(typ='rt')

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
def load_yaml_data(directory):
    """load data from yaml source files"""
    data = []
    for file in sorted(list_files(directory)):
        source_file = directory + file
        logging.debug('loading data from %s', source_file)
        with open(source_file, 'r') as yaml_data:
            item = yaml.load(yaml_data)
            data.append(item)
    return data
