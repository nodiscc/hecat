"""github metadata processor"""

import ruamel.yaml
import logging
import subprocess
import re
import os
from collections import OrderedDict
from datetime import datetime, timedelta
from ..utils import load_yaml_data, to_kebab_case
from github import Github

yaml = ruamel.yaml.YAML(typ='rt')
yaml.indent(sequence=4, offset=2)

GH_API_SLEEP_TIME = 0.1
GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
LAST_UPDATED_INFO_DAYS = 186 # ~6 months
LAST_UPDATED_WARN_DAYS = 365

def get_gh_metadata(github_url, g):
    """get github project metadata from Github API"""
    project = re.sub('https://github.com/', '', github_url)
    gh_metadata = g.get_repo(project)
    return gh_metadata

def write_software_yaml(args, software):
    """write software data to yaml file"""
    dest_file = '{}/{}'.format(
                               args.source_directory + args.software_directory,
                               to_kebab_case(software['name']) + '.yml')
    logging.debug('writing file %s', dest_file)
    with open(dest_file, 'w+') as yaml_file:
        yaml.dump(software, yaml_file)

def add_github_metadata(args, options):
    """gather github project data and add it to source YAML files
    supports a list of options:
    gh-metadata-only-missing: only add/populate missing fields/keys, do not update existing keys
    """
    g = Github(GITHUB_TOKEN)
    software_list = load_yaml_data(args.source_directory + args.software_directory)
    for software in software_list:
        github_url = ''
        if 'website_url' in software:
            if re.search(r'^https://github.com/[\w\.\-]+/[\w\.\-]+$', software['website_url']):
                github_url = software['website_url']
        elif 'source_code_url' in software:
            if re.search(r'^https://github.com/[\w\.\-]+/[\w\.\-]+$', software['source_code_url']):
                github_url = software['source_code_url']
        if github_url:
            logging.debug('%s is a github project URL', github_url)
            if 'gh-metadata-only-missing' in options:
                if ('stargazers_count' not in software) or ('updated_at' not in software):
                    logging.info('Missing metadata for %s, gathering it from Github API', software['name'])
                    gh_metadata = get_gh_metadata(github_url, g)
                    software['stargazers_count'] = gh_metadata.stargazers_count
                    software['updated_at'] = datetime.strftime(gh_metadata.updated_at, "%Y-%m-%d")
                    write_software_yaml(args, software)
                else:
                    logging.debug('all metadata already present, skipping %s', github_url)
            else:
                logging.info('Gathering metadata for %s from Github API', github_url)
                gh_metadata = get_gh_metadata(github_url, g)
                software['stargazers_count'] = gh_metadata.stargazers_count
                software['updated_at'] = datetime.strftime(gh_metadata.updated_at, "%Y-%m-%d")
                write_software_yaml(args, software)

def check_github_last_updated(args):
    """checks the date of last update to a project, warn if older than configured threshold"""
    software_list = load_yaml_data(args.source_directory + args.software_directory)
    for software in software_list:
        if 'updated_at' in software:
            last_update_time = datetime.strptime(software['updated_at'], "%Y-%m-%d")
            time_since_last_update = last_update_time - datetime.now()
            if last_update_time < datetime.now() - timedelta(days=LAST_UPDATED_WARN_DAYS):
                logging.warning('%s: last updated %s ago, older than %s days', software['name'], time_since_last_update, LAST_UPDATED_WARN_DAYS)
            elif last_update_time < datetime.now() - timedelta(days=LAST_UPDATED_INFO_DAYS):
                logging.info('%s: last updated %s ago, older than %s days', software['name'], time_since_last_update, LAST_UPDATED_INFO_DAYS)
            else:
                logging.debug('%s: last updated %s ago', software['name'], time_since_last_update)