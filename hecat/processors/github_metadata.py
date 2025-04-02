"""github_metadata processor
Gathers project/repository metadata from GitHub API and adds some fields to YAML data (`updated_at`, `stargazers_count`, `archived`).

# hecat.yml
steps:
  - step: process
    module: processors/github_metadata
    module_options:
      source_directory: tests/awesome-selfhosted-data # directory containing YAML data and software subdirectory
      gh_metadata_only_missing: False # (default False) only gather metadata for software entries in which one of stargazers_count,updated_at, archived is missing
      sleep_time: 3.7 # (default 60) sleep for this amount of time before each request to Github API
      batch_size: 10 # (default 30) number of repositories to include in each batch request to Github API

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

When using GITHUB_TOKEN, the API rate limit is 1,000 requests per hour per repository [[1]](https://docs.github.com/en/graphql/overview/rate-limits-and-node-limits-for-the-graphql-api#primary-rate-limit)
The call to get_gh_metadata() performs an API request for every batch with `batch_size` repositories (which returns all metadata in one request).
"""

import sys
import logging
import requests
import re
import json
import os
import time
from datetime import datetime
import ruamel.yaml
from ..utils import load_yaml_data, to_kebab_case

yaml = ruamel.yaml.YAML(typ='rt')
yaml.indent(sequence=4, offset=2)
yaml.width = 99999

class DummyGhMetadata(dict):
    """a dummy metadata object that will be returned when fetching metadata from github API fails"""
    def __init__(self):
        self.stargazers_count = 0
        self.archived = False
        self.current_release = {
            "tag": None,
            "published_at": None
        }
        self.last_commit_date = None
        self.commit_history = {}

def write_software_yaml(step, software):
    """write software data to yaml file"""
    dest_file = '{}/{}'.format(
                               step['module_options']['source_directory'] + '/software',
                               to_kebab_case(software['name']) + '.yml')
    logging.debug('writing file %s', dest_file)
    with open(dest_file, 'w+', encoding="utf-8") as yaml_file:
        yaml.dump(software, yaml_file)

def extract_repo_name(url):
    re_result = re.search(r'^https?:\/\/github\.com\/[^\/]+\/([^\/]+)\/?$', url)
    return re_result.group(1) if re_result else None

def add_github_metadata(step):
    """gather github project data and add it to source YAML files"""
    GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
    errors = []
    github_projects = []
    # Load software data
    software_list = load_yaml_data(step['module_options']['source_directory'] + '/software')
    logging.info('updating software data from Github API')
    # Check if the source code URL is a GitHub repository and add it to the queue to be processed
    for software in software_list:
        if 'source_code_url' in software:
            if re.search(r'^https://github.com/[\w\.\-]+/[\w\.\-]+/?$', software['source_code_url']):
                # Check if we only want to update missing metadata or all metadata
                if 'gh_metadata_only_missing' in step['module_options'].keys() and step['module_options']['gh_metadata_only_missing']:
                    if ('stargazers_count' not in software) or ('updated_at' not in software) or ('archived' not in software) or ('current_release' not in software) or ('last_commit_date' not in software) or ('commit_history' not in software):
                        github_projects.append(software)
                    else:
                        logging.debug('all metadata already present, skipping %s', software['source_code_url'])
                # If key is not present, update all metadata
                else:
                    github_projects.append(software)
        # TODO: Why do we need to check the website_url? We can exspect that the source_code_url is always present and the website_url is optional and even if changed it would not point to a github repository
        elif 'website_url' in software:
            if re.search(r'^https://github.com/[\w\.\-]+/[\w\.\-]+/?$' , software['website_url']):
                # Check if we only want to update missing metadata or all metadata
                if 'gh_metadata_only_missing' in step['module_options'].keys() and step['module_options']['gh_metadata_only_missing']:
                    if ('stargazers_count' not in software) or ('updated_at' not in software) or ('archived' not in software) or ('current_release' not in software) or ('last_commit_date' not in software) or ('commit_history' not in software):
                        github_projects.append(software)
                    else:
                        logging.debug('all metadata already present, skipping %s', software['website_url'])
                # If key is not present, update all metadata
                else:
                    github_projects.append(software)
    # Get the metadata for the GitHub repositories
    GITHUB_GRAPHQL_API = "https://api.github.com/graphql"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

    # Get the URLs of the queued repositories
    github_urls = [software['source_code_url'] for software in github_projects]
    repos = [re.sub('https://github.com/', '', url) for url in github_urls]

    # TODO: While more should be supported, I don't get it to work with 50 or more, as the API returns an error
    # This limit was tested with a personal access token, batch_size = 30, timeout = 60 (new default if not provided in a config); Worked fine for the full repo (enable debug messages to see usage of API Rate limit stats)
    # Split repo list into batches of batch_size
    if 'batch_size' in step['module_options']:
        batch_size = step['module_options']['batch_size']
    else:
        # Default batch_size of repos if not specified in config file
        batch_size = 30
    batches = [repos[i * batch_size:(i + 1) * batch_size] for i in range((len(repos) + batch_size - 1) // batch_size )]

    counter = 0
    for batch in batches:
        counter += 1
        logging.info(f"Processing batch {counter}/{len(batches)}")
        
        repos_query = " ".join([f"repo:{repo}" for repo in batch])

        # Get the current year and month
        now = datetime.now()
        year_month = now.strftime("%Y-%m")
        # TODO: More accurate lookup would be for last month, but would mean we lag 1 month behind
        #dateMonth = (now.month - 2) % 12 + 1
        #dateYear = now.year - 1 if dateMonth == 12 else now.year
        #year_last_month = datetime.date(dateYear, dateMonth, 1).strftime("%Y-%m")

        query = f"""
{{
    search(
        type: REPOSITORY
        query: "{repos_query}"
        first: {batch_size}
    ) {{
    repos: edges {{
        repo: node {{
        ... on Repository {{
            url
            stargazerCount
            isArchived
            releases(first: 1) {{
                edges {{
                    node {{
                        tagName
                        publishedAt
                    }}
                }}
            }}
            defaultBranchRef {{
                target {{
                    ... on Commit {{
                        committedDate
                        history(since: "{year_month}-01T00:00:00", until: "{year_month}-31T23:59:59") {{
                            totalCount
                        }}
                    }}
                }}
            }}
        }}
        }}
    }}
    }}
}}
        """
        res_header = None
        try:
            response = requests.post(GITHUB_GRAPHQL_API, json={"query": query}, headers=headers)
            res_header = response.headers
            # Check status code
            if response.status_code != 200:
                # print body
                errors.append(f'Response code of POST request (GraphQL): {response.status_code}')
            data = response.json()
            if 'errors' in data:
                for error in data['errors']:
                    errors.append(error['message'])
                sys.exit(4)
        except Exception as e:
            errors.append(str(e))
            
        # casefold header names
        if res_header:
            res_header = {k.casefold(): v for k, v in res_header.items()}
            rl_arr = []
            rl_arr.append(res_header['x-ratelimit-limit']) if 'x-ratelimit-limit' in res_header else rl_arr.append('-1')
            rl_arr.append(res_header['x-ratelimit-remaining']) if 'x-ratelimit-remaining' in res_header else rl_arr.append('-1')
            rl_arr.append(res_header['x-ratelimit-used']) if 'x-ratelimit-used' in res_header else rl_arr.append('-1')
            rl_arr.append(res_header['x-ratelimit-reset']) if 'x-ratelimit-reset' in res_header else rl_arr.append('-1')
            logging.debug(f"Rate limit (Limit/Remain/Used/Reset): {'/'.join(rl_arr)}")
            
        for edge in data["data"]["search"]["repos"]:
            repo = edge["repo"]
            software = None
            for project in github_projects:
                if extract_repo_name(repo["url"]).casefold() == extract_repo_name(project['source_code_url']).casefold():
                    software = project
                    break
            if not software:
                logging.error('could not find software entry for %s', repo["url"])
                continue
            
            software["stargazers_count"] = repo["stargazerCount"]
            software["archived"] = repo["isArchived"]
            if repo["releases"]["edges"] and len(repo["releases"]["edges"]) > 0:
                software["current_release"] = {
                    "tag": repo["releases"]["edges"][0]["node"]["tagName"],
                    "published_at": datetime.strptime(repo["releases"]["edges"][0]["node"]["publishedAt"], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
                }
            software["updated_at"] = datetime.strptime(repo["defaultBranchRef"]["target"]["committedDate"], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
            if 'commit_history' not in software:
                software['commit_history'] = {}
            if year_month in software["commit_history"]:
                software["commit_history"][year_month] = repo["defaultBranchRef"]["target"]["history"]["totalCount"]
            else:
                software["commit_history"].update({
                    year_month: repo["defaultBranchRef"]["target"]["history"]["totalCount"]
                })
            try:
                write_software_yaml(step, software)
            except Exception as e:
                errors.append(str(e))
                logging.error('could not write software entry for %s', repo["url"])
                continue

        # Sleep for the specified amount of time before the next request
        if 'sleep_time' in step['module_options']:
            time.sleep(step['module_options']['sleep_time'])
        else:
            # Default time between Github GraphQL API requests if not specified in config file
            time.sleep(60)
    
    if errors:
        logging.error("There were errors during processing")
        print('\n'.join(errors))
        sys.exit(2)

def gh_metadata_cleanup(step):
    """remove github metadata from source YAML files"""
    software_list = load_yaml_data(step['module_options']['source_directory'] + '/software')
    logging.info('cleaning up old github metadata from software data')
    # Get the current year and month
    now = datetime.now()
    year_month_12_months_ago = (now.replace(year = now.year - 1)).strftime("%Y-%m")
    # Check if commit_history exists and remove any entries that are older the 12 months
    for software in software_list:
        if 'commit_history' in software:
            for key in list(software['commit_history'].keys()):
                if key < year_month_12_months_ago:
                    del software['commit_history'][key]
                    logging.debug('removing commit history %s for %s', key, software['name'])
        write_software_yaml(step, software)
