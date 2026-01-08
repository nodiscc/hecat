"""software_metadata processor
Gathers project/repository metadata from GitHub and GitLab APIs and adds some fields to YAML data (`updated_at`, `stargazers_count`, `archived`, `current_release`, `commit_history`).
Note: `commit_history` is GitHub-specific and will not be added to GitLab projects.

# hecat.yml
steps:
  - step: process
    module: processors/software_metadata
    module_options:
      source_directory: tests/awesome-selfhosted-data # directory containing YAML data and software subdirectory
      metadata_only_missing: False # (default False) only gather metadata for software entries in which one of stargazers_count,updated_at, archived, current_release, commit_history is missing
      commit_history_fetch_months: 6 # (default 3) number of months to fetch from GitHub API (GitHub only)
      commit_history_clean_months: 24 # (default 12) number of months of commit history to keep after cleanup (GitHub only)
      sleep_time: 3.7 # (default 60) sleep for this amount of time before each request to API
      batch_size_github: 10 # (default 30) number of repositories to include in each batch request to GitHub API
      batch_size_gitlab: 5 # (default 10) number of repositories to include in each batch request to GitLab API
      max_retries: 3 # (default 3) maximum number of retries for API errors (502, 503, 504, 429)

source_directory: path to directory where data files reside. Directory structure:
├── software
│   ├── mysoftware.yml # .yml files containing software data
│   ├── someothersoftware.yml
│   └── ...
├── platforms
├── tags
└── ...

A GitHub access token (without privileges) must be defined in the `GITHUB_TOKEN` environment variable:
$ GITHUB_TOKEN=AAAbbbCCCdd... hecat -c .hecat.yml
A GitLab access token (without privileges) must be defined in the `GITLAB_TOKEN` environment variable:
$ GITLAB_TOKEN=AAAbbbCCCdd... hecat -c .hecat.yml
On Github Actions a GitHub token is created automatically for each job. To make it available in the environment use the following workflow configuration:
# .github/workflows/ci.yml
env:
  GITHUB_TOKEN: ${{secrets.GITHUB_TOKEN}}

When using GITHUB_TOKEN, the API rate limit is 1,000 requests per hour per repository [[1]](https://docs.github.com/en/graphql/overview/rate-limits-and-node-limits-for-the-graphql-api#primary-rate-limit)
When using GITLAB_TOKEN, the API rate limit is 2,000 requests per minute per user [[2]](https://docs.gitlab.com/user/gitlab_com/#rate-limits-on-gitlabcom)
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

# Provider detection
def detect_provider(url):
    """Detect the provider (github or gitlab) from the URL"""
    if re.search(r'^https://github\.com/[\w\.\-]+/[\w\.\-]+/?$', url):
        return 'github'
    if re.search(r'^https://gitlab\.com/[\w\.\-]+/[\w\.\-]+/?$', url):
        return 'gitlab'
    return None

def extract_github_repo_identifier(url):
    """extract the repository owner/name from the GitHub URL"""
    re_result = re.search(r'^https?:\/\/github\.com\/([^\/]+)\/([^\/]+)\/?$', url)
    if re_result:
        owner = re_result.group(1)
        repo = re_result.group(2)
        return f"{owner}/{repo}"
    logging.debug('extract_github_repo_identifier: failed to extract owner/repo from URL: %s', url)
    return None

def extract_gitlab_repo_identifier(url):
    """extract the repository full path from the GitLab URL"""
    re_result = re.search(r'^https?:\/\/gitlab\.com\/([^\/]+(?:\/[^\/]+)*)\/?$', url)
    if re_result:
        return re_result.group(1)
    logging.debug('extract_gitlab_repo_identifier: failed to extract full path from URL: %s', url)
    return None

# Common utilities
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

# Common GraphQL request handler
def process_graphql_request(query, graphql_api, headers, step, max_retries, errors, repo_identifier="", attempt=1, batch_items=None, on_batch_split=None):
    """Process a single GraphQL request with retry logic and batch splitting support"""
    graphql_response_header = None
    data = None

    # Get configured sleep_time
    if 'sleep_time' in step['module_options']:
        base_sleep_time = step['module_options']['sleep_time']
    else:
        base_sleep_time = 60

    try:
        graphql_response = requests.post(graphql_api, json={"query": query}, headers=headers, timeout=60)
        graphql_response_header = graphql_response.headers

        # Check for API errors that should be retried
        if graphql_response.status_code in [502, 503, 504, 429]:
            if attempt <= max_retries:
                backoff_time = base_sleep_time * (2 ** (attempt - 1))
                logging.warning('GraphQL request failed with status code %s (attempt %s/%s), waiting %s seconds', graphql_response.status_code, attempt, max_retries, backoff_time)
                logging.debug('sleeping for %s between attempts', backoff_time)
                time.sleep(backoff_time)

                # Attempt 1: Retry with same batch (no splitting)
                if attempt == 1:
                    if batch_items and on_batch_split:
                        logging.info('Retrying batch with same size')
                    return process_graphql_request(query, graphql_api, headers, step, max_retries, errors, repo_identifier, attempt + 1, batch_items, on_batch_split)

                # Attempt 2+: Split batch and retry (if batch has more than 1 item)
                elif batch_items and on_batch_split and len(batch_items) > 1:
                    # Calculate split size: halve the batch with each retry
                    split_factor = 2 ** (attempt - 1)  # 2, 4, 8...
                    num_splits = min(split_factor, len(batch_items))

                    logging.info('Splitting batch into %s smaller chunks (attempt %s)', num_splits, attempt)

                    # Split batch into chunks
                    chunk_size = max(1, len(batch_items) // num_splits)
                    split_batches = []
                    for i in range(num_splits):
                        start_idx = i * chunk_size
                        if i == num_splits - 1:
                            # Last chunk gets remaining items
                            chunk = batch_items[start_idx:]
                        else:
                            chunk = batch_items[start_idx:start_idx + chunk_size]

                        if chunk:
                            split_batches.append(chunk)

                    # Process split batches using callback (use same attempt number)
                    if split_batches:
                        for i, split_batch in enumerate(split_batches):
                            on_batch_split(split_batch, attempt)

                            # Sleep between split chunks to avoid rate limiting (not after the last chunk)
                            if i < len(split_batches) - 1:
                                logging.debug('sleeping for %s seconds between split chunks', base_sleep_time)
                                time.sleep(base_sleep_time)
                        # Return a marker dict instead of None to indicate batch was split and processed successfully
                        return {"split_processed": True}, graphql_response_header

                # Single item that keeps failing
                else:
                    if batch_items and len(batch_items) == 1:
                        errors.append(f'Failed to fetch metadata for repository {batch_items[0]} after {attempt} attempts')
                        logging.error('Single repository %s failed after attempt %s', batch_items[0] if batch_items else repo_identifier, attempt)
                    if attempt < max_retries:
                        return process_graphql_request(query, graphql_api, headers, step, max_retries, errors, repo_identifier, attempt + 1, batch_items, on_batch_split)
                    else:
                        if batch_items and len(batch_items) == 1:
                            errors.append(f'Failed to fetch metadata for repository {batch_items[0]} after {max_retries} attempts')
                            logging.error('Failed to fetch metadata for repository %s after all retries', batch_items[0])
                        return None, None
            else:
                errors.append(f'Response code of POST request (GraphQL): {graphql_response.status_code} after {max_retries} retries')
                if repo_identifier:
                    errors[-1] = f'Failed to fetch metadata for {repo_identifier} after {max_retries} attempts'
                errors.append(f'GraphQL request failed with status code {graphql_response.status_code} after {max_retries} retries')
                logging.error('GraphQL request failed with status code %s after %s retries', graphql_response.status_code, max_retries)
                logging.debug('Query: %s', query)
                logging.debug('Response: %s', graphql_response.text)
                return None, None

        # Check for other non-200 status codes (don't retry these)
        if graphql_response.status_code != 200:
            error_msg = f'Response code of POST request (GraphQL): {graphql_response.status_code}'
            if repo_identifier:
                error_msg = f'Response code of POST request (GraphQL) for {repo_identifier}: {graphql_response.status_code}'
            errors.append(error_msg)
            logging.error('GraphQL request failed with status code %s', graphql_response.status_code)
            return None, None

        # Success - parse the response
        data = graphql_response.json()
        if 'errors' in data:
            for error in data['errors']:
                error_msg = error['message']
                if repo_identifier:
                    error_msg = f'{repo_identifier}: {error_msg}'
                errors.append(error_msg)
            if repo_identifier:
                logging.error('GraphQL errors for %s: %s', repo_identifier, data['errors'])
                errors.append(f'GraphQL errors for {repo_identifier}: {data["errors"]}')
            else:
                logging.error('GraphQL errors: %s', data['errors'])
                errors.append(f'GraphQL errors: {data["errors"]}')
                sys.exit(1)
            return None, None

    except Exception as e:
        exception_type = type(e).__name__
        exception_details = str(e)
        if repo_identifier and repo_identifier.startswith('batch '):
            batch_num = repo_identifier.replace('batch ', '')
            logging.error('Exception during GraphQL request for batch %s: %s', batch_num, exception_type)
            errors.append(f'Batch {batch_num}: {exception_type} - {exception_details}')
        else:
            logging.error('Exception during GraphQL request for %s: %s', repo_identifier if repo_identifier else 'request', exception_type)
            errors.append(f'Exception during GraphQL request for {repo_identifier if repo_identifier else "request"}: {exception_type} - {exception_details}')
            if repo_identifier:
                errors.append(f'{repo_identifier}: {exception_type} - {exception_details}')
            else:
                errors.append(f'{exception_type} - {exception_details}')
        logging.debug('Exception details: %s - %s', exception_type, exception_details)
        return None, None

    # make header names lowercase for rate limit logging
    if graphql_response_header:
        graphql_response_header = {k.casefold(): v for k, v in graphql_response_header.items()}
        rate_limits = []
        # GitHub uses x-ratelimit-*, GitLab uses ratelimit-*
        rate_limits.append(graphql_response_header.get('x-ratelimit-limit', graphql_response_header.get('ratelimit-limit', '-1')))
        rate_limits.append(graphql_response_header.get('x-ratelimit-remaining', graphql_response_header.get('ratelimit-remaining', '-1')))
        rate_limits.append(graphql_response_header.get('x-ratelimit-used', graphql_response_header.get('ratelimit-observed', '-1')))
        rate_limits.append(graphql_response_header.get('x-ratelimit-reset', graphql_response_header.get('ratelimit-reset', '-1')))
        logging.debug("Rate limit (Limit/Remain/Used/Reset): %s", '/'.join(rate_limits))

    return data, graphql_response_header

# GitHub provider
def process_github_batch(batch, batch_num, total_batches, github_projects, step, headers, github_graphql_api, month_queries, commit_history_clean_months, max_retries, errors, attempt=1):
    """Process a single batch of GitHub repositories"""
    logging.info("Processing GitHub batch %s/%s (batch size: %s)", batch_num, total_batches, len(batch))
    logging.debug('current batch: ' + str(batch))
    repos_query = " ".join([f"repo:{repo}" for repo in batch])

    history_queries_str = "\n".join([mq[2] for mq in month_queries])

    query = f"""
{{
    search(
        type: REPOSITORY
        query: "{repos_query}"
        first: {len(batch)}
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
    # Define callback for batch splitting
    split_counter = {'index': 0}
    def handle_batch_split(split_batch, split_attempt):
        """Handle a split batch by processing it recursively"""
        chunk_suffix = chr(97 + split_counter['index'])
        split_counter['index'] += 1
        split_batch_num = f"{batch_num}{chunk_suffix}"
        process_github_batch(split_batch, split_batch_num, total_batches, github_projects, step, headers, github_graphql_api, month_queries, commit_history_clean_months, max_retries, errors, split_attempt)

    # Use unified GraphQL request handler
    data, _ = process_graphql_request(query, github_graphql_api, headers, step, max_retries, errors, f"batch {batch_num}", attempt, batch, handle_batch_split)

    # Skip this batch if data is None
    if data is None:
        logging.error('No data received from GraphQL API, skipping batch')
        errors.append(f'No data received from GraphQL API, skipping batch')
        return

    # If batch was split and processed via callback, no need to process data here
    if isinstance(data, dict) and data.get("split_processed"):
        return

    for edge in data["data"]["search"]["repos"]:
        repo = edge["repo"]
        software = None
        for project in github_projects:
            if extract_github_repo_identifier(repo["url"]).casefold() == extract_github_repo_identifier(project['source_code_url']).casefold():
                software = project
                break
        if not software:
            logging.error('could not find software entry for %s', repo["url"])
            errors.append(f'could not find software entry for {repo["url"]}')
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
            logging.error('could not write software entry for %s', repo["url"])
            errors.append(f'could not write software entry for {repo["url"]}')
            continue

def add_github_metadata(step, github_projects, errors):
    """gather github project data and add it to source YAML files"""
    if not github_projects:
        return

    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

    github_graphql_api = "https://api.github.com/graphql"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

    # Get the URLs of the queued repositories
    github_urls = [software['source_code_url'] for software in github_projects]
    repos = [re.sub('https://github.com/', '', url) for url in github_urls]

    # Split repo list into batches of batch_size_github
    if 'batch_size_github' in step['module_options']:
        batch_size = step['module_options']['batch_size_github']
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

    # Get the maximum number of retries for API errors
    if 'max_retries' in step['module_options']:
        max_retries = step['module_options']['max_retries']
    else:
        max_retries = 3

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

    # Get sleep time for spacing between batches (rate limit prevention)
    if 'sleep_time' in step['module_options']:
        between_batch_sleep = step['module_options']['sleep_time']
    else:
        between_batch_sleep = 60

    counter = 0
    for batch in batches:
        counter += 1
        process_github_batch(batch, counter, len(batches), github_projects, step, headers, github_graphql_api, month_queries, commit_history_clean_months, max_retries, errors)

        # Sleep between batches to avoid rate limiting (only if not the last batch)
        if counter < len(batches):
            logging.debug('sleeping for %s seconds between batches', between_batch_sleep)
            time.sleep(between_batch_sleep)

# GitLab provider
def generate_gitlab_alias(repo_path):
    """Generate a valid GraphQL alias from a repository path"""
    # Convert "gitlab-org/gitlab" to "gitlab_org_gitlab" or similar valid identifier
    alias = re.sub(r'[^a-zA-Z0-9_]', '_', repo_path)
    # Ensure it starts with a letter or underscore (GraphQL requirement)
    if not alias or alias[0].isdigit():
        alias = 'p' + alias
    return alias

def process_gitlab_batch(batch, batch_num, total_batches, gitlab_projects, step, headers, gitlab_graphql_api, max_retries, errors, attempt=1):
    """Process a single batch of GitLab repositories using GraphQL fragments"""
    logging.info("Processing GitLab batch %s/%s (batch size: %s)", batch_num, total_batches, len(batch))
    logging.debug('current batch: ' + str(batch))

    # Build fragment and query with aliases for each repo
    fragment = """
fragment ProjectDetails on Project {
  fullPath
  starCount
  archived
  releases(first: 1) {
    edges {
      node {
        tagName
        releasedAt
      }
    }
  }
  repository {
    tree {
      lastCommit {
        committedDate
      }
    }
  }
}
"""

    # Build query with aliases for each repo in batch
    project_queries = []
    repo_to_alias = {}
    for repo_path in batch:
        alias = generate_gitlab_alias(repo_path)
        repo_to_alias[repo_path] = alias
        project_queries.append(f'  {alias}: project(fullPath: "{repo_path}") {{ ...ProjectDetails }}')

    query = fragment + "\n{\n" + "\n".join(project_queries) + "\n}"

    # Define callback for batch splitting
    split_counter = {'index': 0}
    def handle_batch_split(split_batch, split_attempt):
        """Handle a split batch by processing it recursively"""
        chunk_suffix = chr(97 + split_counter['index'])
        split_counter['index'] += 1
        split_batch_num = f"{batch_num}{chunk_suffix}"
        process_gitlab_batch(split_batch, split_batch_num, total_batches, gitlab_projects, step, headers, gitlab_graphql_api, max_retries, errors, split_attempt)

    # Use unified GraphQL request handler
    data, _ = process_graphql_request(query, gitlab_graphql_api, headers, step, max_retries, errors, f"batch {batch_num}", attempt, batch, handle_batch_split)

    # Skip this batch if data is None
    if data is None:
        logging.error('No data received from GraphQL API, skipping batch')
        errors.append(f'No data received from GraphQL API, skipping batch')
        return

    # If batch was split and processed via callback, no need to process data here
    if isinstance(data, dict) and data.get("split_processed"):
        return

    # Process each project from the batch response
    response_data = data.get("data", {})
    for repo_path in batch:
        alias = repo_to_alias[repo_path]
        project_data = response_data.get(alias)

        # TODO: How do we handle GitLabs annoying sub-groups? (org/subgroup/repo) / (org/subgroup/subgroup/repo) / etc.
        # We can never be sure if the repo is an actual repo or a subgroup. Not throwing an error here, means that a rename of a repo will not be detected and metadata would get updated anymore leading to false data. Keeping this error here, means that we can't allow GitLab projects that point to a 2+ segment path to a non-repo as it will throw otherwise an error.
        if not project_data:
            logging.error('could not find project data for %s (alias: %s)', repo_path, alias)
            errors.append(f'could not find project data for {repo_path} (alias: {alias})')
            continue

        # Find the matching software entry
        software = None
        for project in gitlab_projects:
            if extract_gitlab_repo_identifier(project['source_code_url']).casefold() == repo_path.casefold():
                software = project
                break

        if not software:
            logging.error('could not find software entry for %s', repo_path)
            errors.append(f'could not find software entry for {repo_path}')
            continue

        software["stargazers_count"] = project_data.get("starCount", 0)

        # Get updated_at from last commit
        if project_data.get("repository", {}).get("tree", {}).get("lastCommit"):
            committed_date = project_data["repository"]["tree"]["lastCommit"]["committedDate"]
            # GitLab API returns the date in Z format, convert it to UTC
            if committed_date.endswith('Z'):
                committed_date = committed_date.replace('Z', '+00:00')
            software["updated_at"] = datetime.strptime(committed_date, '%Y-%m-%dT%H:%M:%S%z').strftime('%Y-%m-%d')
        else:
            logging.warning('no commit date found for %s', repo_path)

        software["archived"] = project_data.get("archived", False)

        # Add current_release if available
        if project_data.get("releases", {}).get("edges") and len(project_data["releases"]["edges"]) > 0:
            release_node = project_data["releases"]["edges"][0]["node"]
            released_at = release_node["releasedAt"]
            # GitLab API returns the date in Z format, convert it to UTC
            if released_at.endswith('Z'):
                released_at = released_at.replace('Z', '+00:00')
            software["current_release"] = {
                "tag": release_node.get("tagName", ""),
                "published_at": datetime.strptime(released_at, '%Y-%m-%dT%H:%M:%S%z').strftime('%Y-%m-%d')
            }

        # Note: commit_history is GitHub-only, not available for GitLab
        # GitLab doesn't provide a good way to retrieve commit history count through GraphQL API (see https://github.com/nodiscc/hecat/issues/48)

        try:
            write_software_yaml(step, software)
        except Exception as e:
            errors.append(str(e))
            logging.error('could not write software entry for %s', repo_path)
            errors.append(f'could not write software entry for {repo_path}')
            continue

def add_gitlab_metadata(step, gitlab_projects, errors):
    """gather gitlab project data and add it to source YAML files"""
    if not gitlab_projects:
        return

    GITLAB_TOKEN = os.environ.get('GITLAB_TOKEN')

    gitlab_graphql_api = "https://gitlab.com/api/graphql"
    headers = {"Authorization": f"Bearer {GITLAB_TOKEN}"}

    # Get the full paths of the queued repositories
    gitlab_urls = [software['source_code_url'] for software in gitlab_projects]
    repos = [extract_gitlab_repo_identifier(url) for url in gitlab_urls]

    # Split repo list into batches of batch_size_gitlab
    if 'batch_size_gitlab' in step['module_options']:
        batch_size = step['module_options']['batch_size_gitlab']
    else:
        batch_size = 10

    # Get the maximum number of retries for API errors
    if 'max_retries' in step['module_options']:
        max_retries = step['module_options']['max_retries']
    else:
        max_retries = 3

    # build a list of lists (batches) of repo paths, for each batch repositories will be processed
    batches = [repos[i * batch_size:(i + 1) * batch_size] for i in range((len(repos) + batch_size - 1) // batch_size )]

    # Get sleep time for spacing between batches (rate limit prevention)
    if 'sleep_time' in step['module_options']:
        between_batch_sleep = step['module_options']['sleep_time']
    else:
        between_batch_sleep = 60

    counter = 0
    for batch in batches:
        counter += 1
        process_gitlab_batch(batch, counter, len(batches), gitlab_projects, step, headers, gitlab_graphql_api, max_retries, errors)

        # Sleep between batches to avoid rate limiting (only if not the last batch)
        if counter < len(batches):
            logging.debug('sleeping for %s seconds between batches', between_batch_sleep)
            time.sleep(between_batch_sleep)

# Main function
def software_metadata(step):
    """gather project data from GitHub and GitLab APIs and add it to source YAML files"""
    errors = []
    github_projects = []
    gitlab_projects = []

    # Load software data
    software_list = load_yaml_data(step['module_options']['source_directory'] + '/software')
    logging.info('updating software data from GitHub and GitLab APIs')

    # Check if the source code URL is a supported provider and add it to the appropriate queue
    for software in software_list:
        if 'source_code_url' in software:
            provider = detect_provider(software['source_code_url'])

            if provider == 'github':
                # Check if we only want to update missing metadata or all metadata
                if 'metadata_only_missing' in step['module_options'].keys() and step['module_options']['metadata_only_missing']:
                    required_keys = ['stargazers_count', 'updated_at', 'archived', 'current_release', 'commit_history']
                    if any(key not in software for key in required_keys):
                        github_projects.append(software)
                    else:
                        logging.debug('all metadata already present, skipping %s', software['source_code_url'])
                # If key is not present, update all metadata
                else:
                    github_projects.append(software)

            elif provider == 'gitlab':
                # Check if we only want to update missing metadata or all metadata
                if 'metadata_only_missing' in step['module_options'].keys() and step['module_options']['metadata_only_missing']:
                    required_keys = ['stargazers_count', 'updated_at', 'archived', 'current_release']
                    if any(key not in software for key in required_keys):
                        gitlab_projects.append(software)
                    else:
                        logging.debug('all metadata already present, skipping %s', software['source_code_url'])
                # If key is not present, update all metadata
                else:
                    gitlab_projects.append(software)

    # Process GitHub projects
    if github_projects:
        logging.info('Processing %s GitHub projects', len(github_projects))
        add_github_metadata(step, github_projects, errors)

    # Process GitLab projects
    if gitlab_projects:
        logging.info('Processing %s GitLab projects', len(gitlab_projects))
        add_gitlab_metadata(step, gitlab_projects, errors)

    if errors:
        logging.error("There were errors during processing")
        print('\n'.join(errors))
        sys.exit(1)
