"""hecat CLI entrypoint"""
import logging
import os
import argparse
import yaml
from .exporters import render_markdown_singlepage

config = {
    'source_dir': 'awesome-selfhosted-data',
    'output_dir': 'awesome-selfhosted',
    'index_file': 'README.md',
    'software_dir': '/software/',
    'tags_dir': '/tags/'
}

##########################

def list_yaml_files(directory):
    """list files in a directory, return an alphabetically sorted list"""
    source_files = []
    for _, _, files in os.walk(directory):
        for file in files:
            source_files.append(file)
    source_files.sort()
    return source_files

def load_yaml_tags(args):
    """load tags data from yaml source files, order alphabetically"""
    tags = list([])
    for file in list_yaml_files(args.source_directory + args.tags_directory):
        source_file = args.source_directory + args.tags_directory + file
        logging.info('loading tag data from %s', source_file)
        with open(source_file, 'r') as yaml_data:
            tags.append(yaml.load(yaml_data, Loader=yaml.FullLoader))
            tags = sorted(tags, key=lambda k: k['name'])
    return tags

def load_yaml_software(args):
    """load software projects definitions from yaml source files"""
    software_list = []
    for file in list_yaml_files(args.software_directory):
        source_file = args.source_directory + args.software_directory + file
        logging.info('loading software data from %s', source_file)
        with open(source_file, 'r') as yaml_data:
            software = yaml.load(yaml_data, Loader=yaml.FullLoader)
            software_list.append(software)
    return software_list


#######################

def main():
    """Main loop"""
    # command-line parsing
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    build_parser = subparsers.add_parser('build', help='build markdown from YAML source files')
    build_parser.add_argument('--exporter', required=True, type=str, choices=['markdown_singlepage'], help='exporter to use')
    build_parser.add_argument('--source-directory', required=True, type=str, help='base directory for YAML data')
    build_parser.add_argument('--output-directory', required=True, type=str, help='base directory for markdown output')
    build_parser.add_argument('--output-file', required=True, type=str, help='output filename')
    build_parser.add_argument('--tags-directory', type=str, default='/tags/', help='name of the source tags subdirectory')
    build_parser.add_argument('--software-directory', type=str, default='/software/', help='name of the source software subdirectory')
    args = parser.parse_args()
    # load data from source files
    tags = load_yaml_tags(args)
    software_list = load_yaml_software(args)
    # render markdown
    if args.exporter == 'markdown_singlepage':
        markdown_singlepage = render_markdown_singlepage(tags, software_list, args)
        with open(args.output_directory + '/' + args.output_file, 'w+') as outfile:
            outfile.write(markdown_singlepage)
