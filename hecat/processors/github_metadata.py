"""github_metadata processor
Gathers project/repository metadata from GitHub API and adds some fields to YAML data (`updated_at`, `stargazers_count`, `archived`, `current_release`, `commit_history`).

# hecat.yml
steps:
  - step: process
    module: processors/github_metadata
    module_options:
      source_directory: tests/awesome-selfhosted-data # directory containing YAML data and software subdirectory
      gh_metadata_only_missing: False # (default False) only gather metadata for software entries in which one of stargazers_count,updated_at, archived, current_release, commit_history is missing
      sleep_time: 3.7 # (default 45) sleep for this amount of time before each request to Github API
      batch_size: 10 # (default 30) number of repositories to include in each batch request to Github API
      commit_history_clean_months: 24 # (default 12) number of months of commit history to keep after cleanup
      commit_history_fetch_months: 6 # (default 3) number of months to fetch from GitHub API

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
The call to add_github_metadata() performs an API request for every batch with `batch_size` repositories (which returns all metadata in one request).
"""

import os
import re
import sys
import time
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
import requests
import ruamel.yaml
from ..utils import load_yaml_data, to_kebab_case

yaml = ruamel.yaml.YAML(typ='rt')
yaml.indent(sequence=4, offset=2)
yaml.width = 99999

def extract_repo_name(url):
    """extract the repository name from the URL"""
    re_result = re.search(r'^https?:\/\/github\.com\/[^\/]+\/([^\/]+)\/?$', url)
    return re_result.group(1) if re_result else None

def cleanup_old_commit_history(commit_history, months_to_keep=12):
    """Remove commit history entries older than the specified number of months"""
    if not commit_history:
        return commit_history

    # Go back (N-1) months to keep exactly N months including current month
    cutoff_date = datetime.now() - relativedelta(months=months_to_keep - 1)
    cutoff_year_month = cutoff_date.strftime('%Y-%m')

    filtered_history = {}
    for year_month, count in commit_history.items():
        if year_month >= cutoff_year_month:
            filtered_history[year_month] = count

    # Sort by year-month (oldest to newest)
    return dict(sorted(filtered_history.items()))

def write_software_yaml(step, software):
    """write software data to yaml file"""
    dest_file = (f"{step['module_options']['source_directory']}/software/"
                 f"{to_kebab_case(software['name'])}.yml")
    logging.debug('writing file %s', dest_file)
    with open(dest_file, 'w+', encoding="utf-8") as yaml_file:
        yaml.dump(software, yaml_file)

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
                    required_keys = ['stargazers_count', 'updated_at', 'archived', 'current_release', 'commit_history']
                    if any(key not in software for key in required_keys):
                        github_projects.append(software)
                    else:
                        logging.debug('all metadata already present, skipping %s', software['source_code_url'])
                # If key is not present, update all metadata
                else:
                    github_projects.append(software)
    # Get the metadata for the GitHub repositories
    github_graphql_api = "https://api.github.com/graphql"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

    # Get the URLs of the queued repositories
    github_urls = [software['source_code_url'] for software in github_projects]
    repos = [re.sub('https://github.com/', '', url) for url in github_urls]

    # This limit was tested with a personal access token, batch_size = 30, timeout = 45 (new default if not provided in a config); Worked fine for the full repo (enable debug messages to see usage of API Rate limit stats)
    # Split repo list into batches of batch_size
    if 'batch_size' in step['module_options']:
        batch_size = step['module_options']['batch_size']
    else:
        batch_size = 30

    # Get the number of months to keep for commit history
    if 'commit_history_clean_months' in step['module_options']:
        commit_history_clean_months = step['module_options']['commit_history_clean_months']
    else:
        commit_history_clean_months = 12

    # Get the number of months to fetch from GitHub API
    if 'commit_history_fetch_months' in step['module_options']:
        commit_history_fetch_months = step['module_options']['commit_history_fetch_months']
    else:
        commit_history_fetch_months = 3

    # build a list of lists (batches) of repo names, for each batch a graphql query will be made
    batches = [repos[i * batch_size:(i + 1) * batch_size] for i in range((len(repos) + batch_size - 1) // batch_size )]

    # Build month queries for commit history
    month_queries = []
    current_date = datetime.now()
    for i in range(commit_history_fetch_months):
        month_date = current_date - relativedelta(months=i)
        year_month = month_date.strftime('%Y-%m')
        # Calculate the last day of the month
        if month_date.month == 12:
            last_day = 31
        else:
            next_month = month_date.replace(day=28) + relativedelta(days=4)
            last_day = (next_month - relativedelta(days=next_month.day)).day

        month_alias = f"month_{year_month.replace('-', '_')}"
        month_query = f"""
            {month_alias}: history(since: "{year_month}-01T00:00:00Z", until: "{year_month}-{last_day:02d}T23:59:59Z") {{
                totalCount
            }}"""
        month_queries.append((month_alias, year_month, month_query))

    history_queries_str = "\n".join([mq[2] for mq in month_queries])

    counter = 0
    for batch in batches:
        counter += 1
        logging.info("Processing batch %s/%s", counter, len(batches))
        repos_query = " ".join([f"repo:{repo}" for repo in batch])

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
                        {history_queries_str}
                    }}
                }}
            }}
        }}
        }}
    }}
    }}
}}
        """
        graphql_response_header = None
        data = None
        try:
            graphql_response = requests.post(github_graphql_api,
                                           json={"query": query},
                                           headers=headers,
                                           timeout=60)
            graphql_response_header = graphql_response.headers
            # Check status code
            if graphql_response.status_code != 200:
                # print body
                errors.append(f'Response code of POST request (GraphQL): {graphql_response.status_code}')
                logging.error('GraphQL request failed with status code %s, skipping batch', graphql_response.status_code)
                continue
            data = graphql_response.json()
            if 'errors' in data:
                for error in data['errors']:
                    errors.append(error['message'])
                sys.exit(1)
        except Exception as e:
            errors.append(str(e))
            logging.error('Exception during GraphQL request: %s, skipping batch', str(e))
            continue

        # make header names lowercase
        if graphql_response_header:
            graphql_response_header = {k.casefold(): v for k, v in graphql_response_header.items()}
            rate_limits = []
            rate_limits.append(graphql_response_header.get('x-ratelimit-limit', '-1'))
            rate_limits.append(graphql_response_header.get('x-ratelimit-remaining', '-1'))
            rate_limits.append(graphql_response_header.get('x-ratelimit-used', '-1'))
            rate_limits.append(graphql_response_header.get('x-ratelimit-reset', '-1'))
            logging.debug("Rate limit (Limit/Remain/Used/Reset): %s", '/'.join(rate_limits))

        # Skip this batch if data is None
        if data is None:
            # This should be catched earlier, however I somehow still get here
            logging.error('No data received from GraphQL API, skipping batch')
            continue

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
            software["updated_at"] = datetime.strptime(repo["defaultBranchRef"]["target"]["committedDate"], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
            software["archived"] = repo["isArchived"]

            # Add current_release if available
            if repo["releases"]["edges"] and len(repo["releases"]["edges"]) > 0:
                software["current_release"] = {
                    "tag": repo["releases"]["edges"][0]["node"]["tagName"],
                    "published_at": datetime.strptime(repo["releases"]["edges"][0]["node"]["publishedAt"], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
                }

            # Process commit history
            commit_history = {}
            target = repo["defaultBranchRef"]["target"]
            for month_alias, year_month, _ in month_queries:
                if month_alias in target and "totalCount" in target[month_alias]:
                    count = target[month_alias]["totalCount"]
                    commit_history[year_month] = count

            # Merge with existing commit history if present
            if 'commit_history' in software and software['commit_history']:
                existing_history = software['commit_history']
                for year_month, count in commit_history.items():
                    existing_history[year_month] = count
                commit_history = existing_history

            # Clean up old commit history entries
            if commit_history:
                software["commit_history"] = cleanup_old_commit_history(commit_history, commit_history_clean_months)

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
            time.sleep(45)

    if errors:
        logging.error("There were errors during processing")
        print('\n'.join(errors))
        sys.exit(1)
