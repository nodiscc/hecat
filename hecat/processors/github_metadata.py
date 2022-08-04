"""github_metadata processor
Gathers project/repository metadata from GitHub API and adds some fields to YAML data (`updated_at`, `stargazers_count`, `archived`).
Checks the last `updated_at` date of GitHub projects against a "freshness" threshold in days.

# hecat.yml
steps:
  - step: process
    module: processors/github_metadata
    module_options:
      source_directory: awesome-selfhosted-data
      gh_metadata_only_missing: True # optional, default False

If gh_metadata_only_missing is True, metadata will only be gathered/added for software entries missing one of:
stargazers_count, updated_at, archived

A Github access token (without privileges) must be defined in the `GITHUB_TOKEN` environment variable.
$ GITHUB_TOKEN=AAAbbbCCCdd... hecat -c .hecat.yml

On Github Actions a token is created automatically for each job. To make it available in the environment use the following workflow configuration:

# .github/workflows/ci.yml
env:
  GITHUB_TOKEN: ${{secrets.GITHUB_TOKEN}}
"""

import ruamel.yaml
import logging
import re
import os
from collections import OrderedDict
from datetime import datetime, timedelta
from ..utils import load_yaml_data, to_kebab_case
from github import Github

yaml = ruamel.yaml.YAML(typ='rt')
yaml.indent(sequence=4, offset=2)

LAST_UPDATED_INFO_DAYS = 186 # ~6 months
LAST_UPDATED_WARN_DAYS = 365

def get_gh_metadata(github_url, g):
    """get github project metadata from Github API"""
    project = re.sub('https://github.com/', '', github_url)
    gh_metadata = g.get_repo(project)
    return gh_metadata

def write_software_yaml(step, software):
    """write software data to yaml file"""
    dest_file = '{}/{}'.format(
                               step['module_options']['source_directory'] + '/software',
                               to_kebab_case(software['name']) + '.yml')
    logging.debug('writing file %s', dest_file)
    with open(dest_file, 'w+') as yaml_file:
        yaml.dump(software, yaml_file)

def add_github_metadata(step):
    """gather github project data and add it to source YAML files
    supports a list of options:
    """
    GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
    g = Github(GITHUB_TOKEN)
    software_list = load_yaml_data(step['module_options']['source_directory'] + '/software')
    logging.info('updating software data from Github API')
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
            if 'gh_metadata_only_missing' in step['module_options'].keys() and step['module_options']['gh_metadata_only_missing']:
                if ('stargazers_count' not in software) or ('updated_at' not in software) or ('archived' not in software):
                    logging.info('Missing metadata for %s, gathering it from Github API', software['name'])
                    gh_metadata = get_gh_metadata(github_url, g)
                    software['stargazers_count'] = gh_metadata.stargazers_count
                    software['updated_at'] = datetime.strftime(gh_metadata.pushed_at, "%Y-%m-%d")
                    software['archived'] = gh_metadata.archived
                    write_software_yaml(step, software)
                else:
                    logging.debug('all metadata already present, skipping %s', github_url)
            else:
                logging.info('Gathering metadata for %s from Github API', github_url)
                gh_metadata = get_gh_metadata(github_url, g)
                software['stargazers_count'] = gh_metadata.stargazers_count
                software['updated_at'] = datetime.strftime(gh_metadata.updated_at, "%Y-%m-%d")
                software['archived'] = gh_metadata.archived
                write_software_yaml(step, software)

def check_github_last_updated(step):
    """checks the date of last update to a project, warn if older than configured threshold"""
    logging.info('checking software last update dates against info (%s days)/warning (%s days) thresholds', LAST_UPDATED_INFO_DAYS, LAST_UPDATED_WARN_DAYS)
    software_list = load_yaml_data(step['module_options']['source_directory'] + '/software')
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
