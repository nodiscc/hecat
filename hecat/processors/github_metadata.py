"""github_metadata processor
Gathers project/repository metadata from GitHub API and adds some fields to YAML data (`updated_at`, `stargazers_count`, `archived`).

# hecat.yml
steps:
  - step: process
    module: processors/github_metadata
    module_options:
      source_directory: tests/awesome-selfhosted-data # directory containing YAML data and software subdirectory
      gh_metadata_only_missing: False # (default False) only gather metadata for software entries in which one of stargazers_count,updated_at, archived is missing
      sleep_time: 3.7 # (default 0) sleep for this amount of time before each request to Github API

source_directory: path to directory where data files reside. Directory structure:
├── software
│   ├── mysoftware.yml # .yml files containing software data
│   ├── someothersoftware.yml
│   └── ...
├── platforms
├── tags
└── ...

A Github access token (without privileges) must be defined in the `GITHUB_TOKEN` environment variable:
$ GITHUB_TOKEN=AAAbbbCCCdd... hecat -c .hecat.yml
On Github Actions a token is created automatically for each job. To make it available in the environment use the following workflow configuration:
# .github/workflows/ci.yml
env:
  GITHUB_TOKEN: ${{secrets.GITHUB_TOKEN}}

When using GITHUB_TOKEN, the API rate limit is 1,000 requests per hour per repository [[1]](https://docs.github.com/en/rest/overview/resources-in-the-rest-api?apiVersion=2022-11-28#rate-limits-for-requests-from-github-actions)
Not that each call to get_gh_metadata() results in 2 API requests (on for the repo/stargazers count, one for the latest commit date)
"""

import sys
import logging
import re
import os
import time
from datetime import datetime
import ruamel.yaml
import github
from ..utils import load_yaml_data, to_kebab_case

yaml = ruamel.yaml.YAML(typ='rt')
yaml.indent(sequence=4, offset=2)
yaml.width = 99999

class DummyGhMetadata(dict):
    """a dummy metadata object that will be returned when fetching metadata from github API fails"""
    def __init__(self):
        self.stargazers_count = 0
        self.archived = False

def get_gh_metadata(step, github_url, g, errors):
    """get github project metadata from Github API"""
    if 'sleep_time' in step['module_options']:
        time.sleep(step['module_options']['sleep_time'])
    project = re.sub('https://github.com/', '', github_url)
    project = re.sub('/$', '', project)
    try:
        gh_metadata = g.get_repo(project)
        latest_commit_date = gh_metadata.get_commits()[0].commit.committer.date
    except github.GithubException as github_error:
        error_msg = '{} : {}'.format(github_url, github_error)
        logging.error(error_msg)
        errors.append(error_msg)
        gh_metadata = DummyGhMetadata()
        latest_commit_date = datetime.strptime('1970-01-01', '%Y-%m-%d')
    return gh_metadata, latest_commit_date

def write_software_yaml(step, software):
    """write software data to yaml file"""
    dest_file = '{}/{}'.format(
                               step['module_options']['source_directory'] + '/software',
                               to_kebab_case(software['name']) + '.yml')
    logging.debug('writing file %s', dest_file)
    with open(dest_file, 'w+', encoding="utf-8") as yaml_file:
        yaml.dump(software, yaml_file)

def add_github_metadata(step):
    """gather github project data and add it to source YAML files"""
    GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
    g = github.Github(GITHUB_TOKEN)
    errors = []
    software_list = load_yaml_data(step['module_options']['source_directory'] + '/software')
    logging.info('updating software data from Github API')
    for software in software_list:
        github_url = ''
        if 'source_code_url' in software:
            if re.search(r'^https://github.com/[\w\.\-]+/[\w\.\-]+/?$', software['source_code_url']):
                github_url = software['source_code_url']
        elif 'website_url' in software:
            if re.search(r'^https://github.com/[\w\.\-]+/[\w\.\-]+/?$', software['website_url']):
                github_url = software['website_url']
        if github_url:
            logging.debug('%s is a github project URL', github_url)
            if 'gh_metadata_only_missing' in step['module_options'].keys() and step['module_options']['gh_metadata_only_missing']:
                if ('stargazers_count' not in software) or ('updated_at' not in software) or ('archived' not in software):
                    logging.info('Missing metadata for %s, gathering it from Github API', software['name'])
                    gh_metadata, latest_commit_date = get_gh_metadata(step, github_url, g, errors)
                    software['stargazers_count'] = int(gh_metadata.stargazers_count)
                    software['updated_at'] = datetime.strftime(latest_commit_date, "%Y-%m-%d")
                    software['archived'] = bool(gh_metadata.archived)
                    write_software_yaml(step, software)
                else:
                    logging.debug('all metadata already present, skipping %s', github_url)
            else:
                logging.info('Gathering metadata for %s from Github API', github_url)
                gh_metadata, latest_commit_date = get_gh_metadata(step, github_url, g, errors)
                software['stargazers_count'] = gh_metadata.stargazers_count
                software['updated_at'] = datetime.strftime(latest_commit_date, "%Y-%m-%d")
                software['archived'] = gh_metadata.archived
                write_software_yaml(step, software)
    if errors:
        logging.error("There were errors during processing")
        print('\n'.join(errors))
        sys.exit(1)
