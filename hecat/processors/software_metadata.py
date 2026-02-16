"""software_metadata processor
Gathers project/repository metadata from GitHub and GitLab APIs and adds some fields to YAML data (`updated_at`, `stargazers_count`, `archived`, `current_release`, `commit_history`).

Note: `commit_history` is GitHub-specific and will not be added to GitLab projects

# hecat.yml
steps:
  - step: process
    module: processors/software_metadata
    module_options:
      source_directory: tests/awesome-selfhosted-data   # directory containing YAML data and software subdirectory
      metadata_only_missing: False                      # (default False) only gather metadata for software entries in which one of stargazers_count,updated_at, archived, current_release, commit_history is missing
      commit_history_fetch_months: 6                    # (default 3) number of months to fetch commit history from GitHub API (GitHub only)
      commit_history_clean_months: 24                   # (default 12) number of months of commit history to keep after cleanup (GitHub only)
      sleep_time: 3.7                                   # (default 60) sleep for this amount of time before each request to API
      batch_size_github: 10                             # (default 30) number of repositories to include in each batch request to GitHub API
      batch_size_gitlab: 5                              # (default 10) number of repositories to include in each batch request to GitLab API
      max_retries: 3                                    # (default 3) maximum number of retries for API errors (502, 503, 504, 429) and connection errors (ChunkedEncodingError, ConnectionError, Timeout)

source_directory: path to directory where data files reside. Directory structure:
├── software
│   ├── mysoftware.yml # .yml files containing software data
│   ├── someothersoftware.yml
│   └── ...
├── platforms
├── tags
└── ...

Environment Variables:
    GITHUB_TOKEN: GitHub access token (required for GitHub repos)
    GITLAB_TOKEN: GitLab access token (required for GitLab repos)

Rate Limits:
    GitHub: 1,000 requests/hour/repository [[1]](https://docs.github.com/en/graphql/overview/rate-limits-and-node-limits-for-the-graphql-api#primary-rate-limit)
    GitLab: 2,000 requests/minute/user [[2]](https://docs.gitlab.com/user/gitlab_com/#rate-limits-on-gitlabcom)
"""

import calendar
import os
import re
import sys
import time
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
import requests
import ruamel.yaml
from requests.exceptions import ChunkedEncodingError, ConnectionError, Timeout, RequestException
from json import JSONDecodeError
from ..utils import load_yaml_data, to_kebab_case

# Variables
DEFAULT_SLEEP_TIME = 5
DEFAULT_BATCH_SIZE_GITHUB = 25
DEFAULT_BATCH_SIZE_GITLAB = 10
DEFAULT_MAX_RETRIES = 3
DEFAULT_COMMIT_HISTORY_FETCH_MONTHS = 3
DEFAULT_COMMIT_HISTORY_CLEAN_MONTHS = 12

RETRYABLE_STATUS_CODES = (502, 503, 504, 429)
RETRYABLE_EXCEPTIONS = (ChunkedEncodingError, ConnectionError, Timeout)

GITHUB_GRAPHQL_API = "https://api.github.com/graphql"
GITLAB_GRAPHQL_API = "https://gitlab.com/api/graphql"

GITHUB_REQUIRED_KEYS = ['stargazers_count', 'updated_at', 'archived', 'current_release', 'commit_history']
GITLAB_REQUIRED_KEYS = ['stargazers_count', 'updated_at', 'archived', 'current_release']

# YAML configuration
yaml = ruamel.yaml.YAML(typ='rt')
yaml.indent(sequence=4, offset=2)
yaml.width = 99999

# Provider detection
def detect_provider(url):
    """detect the hosting provider from a repository URL"""
    if re.search(r'^https://github\.com/[\w\.\-]+/[\w\.\-]+/?$', url):
        return 'github'
    if re.search(r'^https://gitlab\.com/[\w\.\-]+/[\w\.\-]+/?$', url):
        return 'gitlab'
    return None

def extract_github_repo_identifier(url):
    """extract 'owner/repo' from a GitHub URL"""
    re_result = re.search(r'^https?://github\.com/([^/]+)/([^/]+)/?$', url)
    if re_result:
        owner = re_result.group(1)
        repo = re_result.group(2)
        return f"{owner}/{repo}"
    logging.debug('extract_github_repo_identifier: failed to extract owner/repo from GitHub URL: %s', url)
    return None

def extract_gitlab_repo_identifier(url):
    """extract the full project path from a GitLab URL"""
    re_result = re.search(r'^https?://gitlab\.com/([^/]+(?:/[^/]+)*)/?$', url)
    if re_result:
        return re_result.group(1)
    logging.debug('extract_gitlab_repo_identifier: failed to extract project path from GitLab URL: %s', url)
    return None

# Other utilities
def get_config_option(step, key, default):
    """retrieve a configuration option with a fallback default value"""
    return step['module_options'].get(key, default)

def write_software_yaml(step, software):
    """write software data to its YAML file"""
    dest_file = (
        f"{step['module_options']['source_directory']}/software/"
        f"{to_kebab_case(software['name'])}.yml"
    )
    logging.debug('Writing file %s', dest_file)
    with open(dest_file, 'w+', encoding="utf-8") as yaml_file:
        yaml.dump(software, yaml_file)


def _parse_iso_date(iso_datetime_str):
    """Parse ISO 8601 datetime (Z or +HH:MM) and return YYYY-MM-DD."""
    s = iso_datetime_str.replace('Z', '+00:00')
    return datetime.fromisoformat(s).strftime('%Y-%m-%d')


def cleanup_old_commit_history(commit_history, months_to_keep=12):
    """remove commit history entries older than the specified number of months"""
    if not commit_history:
        return commit_history

    cutoff_date = datetime.now() - relativedelta(months=months_to_keep - 1)
    cutoff_year_month = cutoff_date.strftime('%Y-%m')

    filtered_history = {
        year_month: count
        for year_month, count in commit_history.items()
        if year_month >= cutoff_year_month
    }

    return dict(sorted(filtered_history.items()))

def build_month_queries(fetch_months):
    """
    build GraphQL query fragments for fetching commit history by month
    
    returns a list of tuples: (alias, year_month, query_fragment)
    """
    month_queries = []
    current_date = datetime.now()

    for i in range(fetch_months):
        month_date = current_date - relativedelta(months=i)
        year_month = month_date.strftime('%Y-%m')

        # Calculate last day of month
        last_day = calendar.monthrange(month_date.year, month_date.month)[1]

        month_alias = f"month_{year_month.replace('-', '_')}"
        query_fragment = f"""
            {month_alias}: history(since: "{year_month}-01T00:00:00Z", until: "{year_month}-{last_day:02d}T23:59:59Z") {{
                totalCount
            }}"""
        month_queries.append((month_alias, year_month, query_fragment))

    return month_queries

def create_batches(items, batch_size):
    """split a list into batches of the specified size"""
    return [
        items[i * batch_size:(i + 1) * batch_size]
        for i in range((len(items) + batch_size - 1) // batch_size)
    ]

def find_missing_repos(batch, found_repos, projects, extract_func, base_url, errors):
    """identify and log repositories from the batch that were not found in API results"""
    missing_repos = set(batch) - found_repos

    for missing_repo in missing_repos:
        # Repo from the batch wasn't returned by the API at all (repo not found in search results)
        # Try to find the original URL from our project list
        missing_url = f'{base_url}/{missing_repo}'
        for project in projects:
            project_repo = extract_func(project.get('source_code_url', ''))
            if project_repo and project_repo.casefold() == missing_repo:
                missing_url = project.get('source_code_url', missing_url)
                break

        logging.error('repository not found in search results: %s', missing_url)
        errors.append(f'repository not found in search results: {missing_url}')

def find_software_entry(projects, repo_id_lower, extract_func):
    """find a software entry matching the given repository identifier"""
    for project in projects:
        project_repo_id = extract_func(project.get('source_code_url', ''))
        if project_repo_id and project_repo_id.casefold() == repo_id_lower:
            return project
    return None

# GraphQL request handling
def process_graphql_request(query, graphql_api, headers, step, max_retries, errors, repo_identifier="", attempt=1, batch_items=None, on_batch_split=None):
    """
    execute a GraphQL request with retry logic and batch splitting support
    
    on failure, implements exponential backoff and optionally splits large batches into smaller chunks for retry
    """
    base_sleep_time = get_config_option(step, 'sleep_time', DEFAULT_SLEEP_TIME)

    try:
        response = requests.post(graphql_api, json={"query": query}, headers=headers, timeout=60)

        # Handle retryable HTTP errors
        if response.status_code in RETRYABLE_STATUS_CODES:
            return _handle_retry(
                response.status_code, query, graphql_api, headers, step,
                max_retries, errors, repo_identifier, attempt,
                batch_items, on_batch_split, base_sleep_time
            )

        # Handle non-retryable HTTP errors
        if response.status_code != 200:
            error_msg = f'GraphQL request failed with status {response.status_code}'
            if repo_identifier:
                error_msg = f'{repo_identifier}: {error_msg}'
            errors.append(error_msg)
            logging.error(error_msg)
            return None, None

        # Parse response
        resp_headers = {k.casefold(): v for k, v in response.headers.items()}

        # Log rate limits
        limit = resp_headers.get('x-ratelimit-limit', resp_headers.get('ratelimit-limit', '-1'))
        remaining = resp_headers.get('x-ratelimit-remaining', resp_headers.get('ratelimit-remaining', '-1'))
        used = resp_headers.get('x-ratelimit-used', resp_headers.get('ratelimit-observed', '-1'))
        reset = resp_headers.get('x-ratelimit-reset', resp_headers.get('ratelimit-reset', '-1'))
        logging.debug("Rate limit (Limit/Remain/Used/Reset): %s/%s/%s/%s", limit, remaining, used, reset)

        data = response.json()

        if 'errors' in data:
            for error in data['errors']:
                error_msg = error['message']
                if repo_identifier:
                    error_msg = f'{repo_identifier}: {error_msg}'
                errors.append(error_msg)

            if repo_identifier:
                logging.error('GraphQL errors for %s: %s', repo_identifier, data['errors'])
            else:
                logging.error('GraphQL errors: %s', data['errors'])
                sys.exit(1)
            return None, None

        return data, resp_headers

    except RETRYABLE_EXCEPTIONS as e:
        exception_type = type(e).__name__
        exception_details = str(e)

        return _handle_retry(
            exception_type, query, graphql_api, headers, step,
            max_retries, errors, repo_identifier, attempt,
            batch_items, on_batch_split, base_sleep_time,
            is_exception=True, exception_details=exception_details
        )

    except (RequestException, JSONDecodeError) as e:
        exception_type = type(e).__name__
        exception_details = str(e)

        if repo_identifier and repo_identifier.startswith('batch '):
            batch_num = repo_identifier.replace('batch ', '')
            logging.error('exception during GraphQL request for batch %s: %s', batch_num, exception_type)
            errors.append(f'Batch {batch_num}: {exception_type} - {exception_details}')
        else:
            target = repo_identifier if repo_identifier else 'request'
            logging.error('exception during GraphQL request for %s: %s', target, exception_type)
            errors.append(f'{target}: {exception_type} - {exception_details}')

        logging.debug('exception details: %s', exception_details)
        return None, None


def _handle_retry(error_code, query, graphql_api, headers, step, max_retries, errors, repo_identifier, attempt, batch_items, on_batch_split, base_sleep_time, is_exception=False, exception_details=""):
    """handle retry logic for failed GraphQL requests"""
    if is_exception:
        error_desc = f"exception {error_code}"
    else:
        error_desc = f"status {error_code}"

    if attempt > max_retries:
        error_msg = f'GraphQL request failed with {error_desc} after {max_retries} retries'
        if repo_identifier:
            error_msg = f'{repo_identifier}: {error_msg}'
        if is_exception:
            error_msg += f' - {exception_details}'
        errors.append(error_msg)
        logging.error(error_msg)
        return None, None

    backoff_time = base_sleep_time * (2 ** (attempt - 1))
    logging.warning(
        'GraphQL request failed with %s (attempt %s/%s), waiting %ss',
        error_desc, attempt, max_retries, backoff_time
    )
    time.sleep(backoff_time)

    # Attempt 1: Retry with same batch (no splitting)
    if attempt == 1:
        return process_graphql_request(
            query, graphql_api, headers, step, max_retries, errors,
            repo_identifier, attempt + 1, batch_items, on_batch_split
        )

    # Attempt 2+: Split batch and retry (if batch has more than 1 item)
    if batch_items and on_batch_split and len(batch_items) > 1:
        split_factor = 2 ** (attempt - 1)
        num_splits = min(split_factor, len(batch_items))

        logging.info('splitting batch into %s smaller chunks (attempt %s)', num_splits, attempt)

        # Create split batches
        chunk_size = max(1, len(batch_items) // num_splits)
        split_batches = []
        for i in range(num_splits):
            start_idx = i * chunk_size
            if i == num_splits - 1:
                chunk = batch_items[start_idx:]
            else:
                chunk = batch_items[start_idx:start_idx + chunk_size]
            if chunk:
                split_batches.append(chunk)

        # Process split batches
        for i, split_batch in enumerate(split_batches):
            on_batch_split(split_batch, attempt)
            if i < len(split_batches) - 1:
                logging.debug('sleeping %ss between split chunks', base_sleep_time)
                time.sleep(base_sleep_time)

        return {"split_processed": True}, None

    # Single item that keeps failing or no split callback
    if batch_items and len(batch_items) == 1:
        logging.error('single repository %s failed after attempt %s', batch_items[0], attempt)

    if attempt < max_retries:
        return process_graphql_request(
            query, graphql_api, headers, step, max_retries, errors,
            repo_identifier, attempt + 1, batch_items, on_batch_split
        )

    if batch_items and len(batch_items) == 1:
        errors.append(f'failed to fetch metadata for repository {batch_items[0]} after {max_retries} attempts')
        logging.error('failed to fetch metadata for repository %s after all retries', batch_items[0])

    return None, None

# GitHub provider
def add_github_metadata(step, github_projects, errors):
    """fetch metadata from GitHub API and update YAML files"""
    if not github_projects:
        return

    token = os.environ.get('GITHUB_TOKEN')
    headers = {"Authorization": f"Bearer {token}"}

    if not token:
        logging.warning('GITHUB_TOKEN environment variable is not set, github projects exist but no metadata will be added/updated')
        return

    repos = []
    for project in github_projects:
        repo_id = extract_github_repo_identifier(project['source_code_url'])
        if repo_id:
            repos.append(repo_id.rstrip('/').casefold())
        else:
            logging.error('failed to extract repo identifier from %s', project['source_code_url'])
            errors.append(f'failed to extract repo identifier from {project["source_code_url"]}')

    batch_size = get_config_option(step, 'batch_size_github', DEFAULT_BATCH_SIZE_GITHUB)
    clean_months = get_config_option(step, 'commit_history_clean_months', DEFAULT_COMMIT_HISTORY_CLEAN_MONTHS)
    fetch_months = get_config_option(step, 'commit_history_fetch_months', DEFAULT_COMMIT_HISTORY_FETCH_MONTHS)
    max_retries = get_config_option(step, 'max_retries', DEFAULT_MAX_RETRIES)
    sleep_time = get_config_option(step, 'sleep_time', DEFAULT_SLEEP_TIME)

    batches = create_batches(repos, batch_size)
    month_queries = build_month_queries(fetch_months)

    for batch_num, batch in enumerate(batches, start=1):
        _process_github_batch(
            batch, batch_num, len(batches), github_projects, step,
            headers, month_queries, clean_months, max_retries, errors
        )

        if batch_num < len(batches):
            logging.debug('sleeping %ss between batches', sleep_time)
            time.sleep(sleep_time)

def _process_github_batch( batch, batch_num, total_batches, github_projects, step, headers, month_queries, clean_months, max_retries, errors, attempt=1):
    """process a single batch of GitHub repositories"""
    logging.info("processing GitHub batch %s/%s (size: %s)", batch_num, total_batches, len(batch))
    logging.debug('batch contents: %s', batch)

    # Build query
    repos_query = "fork:true " + " ".join([f"repo:{repo}" for repo in batch])
    history_queries = "\n".join([mq[2] for mq in month_queries])

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
                        {history_queries}
                    }}
                }}
            }}
        }}
        }}
    }}
    }}
}}
    """

    # Create callback for batch splitting
    split_counter = {'index': 0}

    def handle_split(split_batch, split_attempt):
        suffix = chr(97 + split_counter['index'])
        split_counter['index'] += 1
        _process_github_batch(
            split_batch, f"{batch_num}{suffix}", total_batches, github_projects,
            step, headers, month_queries, clean_months, max_retries, errors, split_attempt
        )

    data, _ = process_graphql_request(
        query, GITHUB_GRAPHQL_API, headers, step, max_retries, errors,
        f"batch {batch_num}", attempt, batch, handle_split
    )

    if data is None:
        logging.error('no data received, skipping batch')
        errors.append('no data received from GraphQL API, skipping batch')
        return

    if isinstance(data, dict) and data.get("split_processed"):
        return

    # Process response
    found_repos = set()
    response_data = data.get("data", {})
    search_data = response_data.get("search", {})
    repos = search_data.get("repos", [])

    for edge in repos:
        repo = edge["repo"]
        repo_id = extract_github_repo_identifier(repo["url"])

        if not repo_id:
            logging.error('could not extract repo identifier from %s', repo["url"])
            errors.append(f'could not extract repo identifier from {repo["url"]}')
            continue

        repo_id_lower = repo_id.casefold()
        found_repos.add(repo_id_lower)

        software = find_software_entry(github_projects, repo_id_lower, extract_github_repo_identifier)
        if not software:
            logging.error('could not find software entry for %s', repo["url"])
            errors.append(f'could not find software entry for {repo["url"]}')
            continue

        # Update software entry
        software["stargazers_count"] = repo["stargazerCount"]
        software["updated_at"] = _parse_iso_date(repo["defaultBranchRef"]["target"]["committedDate"])
        software["archived"] = repo["isArchived"]

        # Add current_release if available
        releases = repo["releases"]["edges"]
        if releases:
            release = releases[0]["node"]
            software["current_release"] = {
                "tag": release["tagName"],
                "published_at": _parse_iso_date(release["publishedAt"])
            }

        # Process commit history
        commit_history = {}
        target = repo["defaultBranchRef"]["target"]
        for month_alias, year_month, _ in month_queries:
            if month_alias in target and "totalCount" in target[month_alias]:
                commit_history[year_month] = target[month_alias]["totalCount"]

        if 'commit_history' in software and software['commit_history']:
            software['commit_history'].update(commit_history)
            commit_history = software['commit_history']

        if commit_history:
            software["commit_history"] = cleanup_old_commit_history(commit_history, clean_months)

        try:
            write_software_yaml(step, software)
        except (OSError) as e:
            logging.error('could not write software entry for %s: %s', repo["url"], str(e))
            errors.append(f'could not write software entry for {repo["url"]}: {str(e)}')

    find_missing_repos(batch, found_repos, github_projects, extract_github_repo_identifier, 'https://github.com', errors)

# GitLab provider
def add_gitlab_metadata(step, gitlab_projects, errors):
    """fetch metadata from GitLab API and update YAML files"""
    if not gitlab_projects:
        return

    token = os.environ.get('GITLAB_TOKEN')
    headers = {"Authorization": f"Bearer {token}"}

    if not token:
        logging.warning('GITLAB_TOKEN environment variable is not set, gitlab projects exist but no metadata will be added/updated')
        return

    repos = []
    for project in gitlab_projects:
        repo_id = extract_gitlab_repo_identifier(project['source_code_url'])
        if repo_id:
            repos.append(repo_id.rstrip('/').casefold())
        else:
            logging.error('failed to extract repo identifier from %s', project['source_code_url'])
            errors.append(f'failed to extract repo identifier from {project["source_code_url"]}')

    batch_size = get_config_option(step, 'batch_size_gitlab', DEFAULT_BATCH_SIZE_GITLAB)
    max_retries = get_config_option(step, 'max_retries', DEFAULT_MAX_RETRIES)
    sleep_time = get_config_option(step, 'sleep_time', DEFAULT_SLEEP_TIME)

    batches = create_batches(repos, batch_size)

    for batch_num, batch in enumerate(batches, start=1):
        _process_gitlab_batch(
            batch, batch_num, len(batches), gitlab_projects, step,
            headers, max_retries, errors
        )

        if batch_num < len(batches):
            logging.debug('sleeping %ss between batches', sleep_time)
            time.sleep(sleep_time)


def _process_gitlab_batch( batch, batch_num, total_batches, gitlab_projects, step, headers, max_retries, errors, attempt=1):
    """process a single batch of GitLab repositories"""
    logging.info("processing GitLab batch %s/%s (size: %s)", batch_num, total_batches, len(batch))
    logging.debug('batch contents: %s', batch)

    # Build query
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
    repo_to_alias = {}
    project_queries = []

    for repo_path in batch:
        # Generate valid GraphQL alias
        alias = re.sub(r'[^a-zA-Z0-9_]', '_', repo_path)
        if not alias or alias[0].isdigit():
            alias = 'p' + alias
        repo_to_alias[repo_path] = alias
        project_queries.append(f'  {alias}: project(fullPath: "{repo_path}") {{ ...ProjectDetails }}')

    query = fragment + "\n{\n" + "\n".join(project_queries) + "\n}"

    # Create callback for batch splitting
    split_counter = {'index': 0}

    def handle_split(split_batch, split_attempt):
        suffix = chr(97 + split_counter['index'])
        split_counter['index'] += 1
        _process_gitlab_batch(
            split_batch, f"{batch_num}{suffix}", total_batches, gitlab_projects,
            step, headers, max_retries, errors, split_attempt
        )

    data, _ = process_graphql_request(
        query, GITLAB_GRAPHQL_API, headers, step, max_retries, errors,
        f"batch {batch_num}", attempt, batch, handle_split
    )

    if data is None:
        logging.error('no data received, skipping batch')
        errors.append('no data received from GraphQL API, skipping batch')
        return

    if isinstance(data, dict) and data.get("split_processed"):
        return

    # Process response
    found_repos = set()
    response_data = data.get("data", {})

    for repo_path in batch:
        alias = repo_to_alias[repo_path]
        project_data = response_data.get(alias)

        if not project_data:
            continue  # Will be reported by find_missing_repos

        software = find_software_entry(gitlab_projects, repo_path, extract_gitlab_repo_identifier)
        if not software:
            logging.error('could not find software entry for %s', repo_path)
            errors.append(f'could not find software entry for {repo_path}')
            continue

        found_repos.add(repo_path)

        # Update software entry
        software["stargazers_count"] = project_data.get("starCount", 0)
        last_commit = project_data.get("repository", {}).get("tree", {}).get("lastCommit")
        committed_date = last_commit["committedDate"]
        software["updated_at"] = _parse_iso_date(committed_date)
        software["archived"] = project_data.get("archived", False)

        releases = project_data.get("releases", {}).get("edges", [])
        if releases:
            release = releases[0]["node"]
            released_at = release["releasedAt"]
            software["current_release"] = {
                "tag": release.get("tagName", ""),
                "published_at": _parse_iso_date(released_at)
            }

        # Note: commit_history is GitHub-only (GitLab GraphQL API limitation)
        # GitLab doesn't provide a good way to retrieve commit history count through GraphQL API (see https://github.com/nodiscc/hecat/issues/48)

        try:
            write_software_yaml(step, software)
        except (OSError) as e:
            logging.error('could not write software entry for %s: %s', repo_path, str(e))
            errors.append(f'could not write software entry for {repo_path}: {str(e)}')

    find_missing_repos(batch, found_repos, gitlab_projects, extract_gitlab_repo_identifier, 'https://gitlab.com', errors)

# Main function
def software_metadata(step):
    """gather project data from GitHub/GitLab APIs and add it to source YAML files"""
    errors = []
    github_projects = []
    gitlab_projects = []

    # Load software data
    software_list = load_yaml_data(step['module_options']['source_directory'] + '/software')
    logging.info('updating software data from GitHub and GitLab APIs')

    metadata_only_missing = get_config_option(step, 'metadata_only_missing', False)

    # Check if the source code URL is a supported provider and add it to the appropriate queue
    for software in software_list:
        if 'source_code_url' not in software:
            continue

        provider = detect_provider(software['source_code_url'])

        if provider == 'github':
            # Check if we only want to update missing metadata or all metadata
            if not metadata_only_missing or any(k not in software for k in GITHUB_REQUIRED_KEYS):
                github_projects.append(software)
            else:
                logging.debug('all metadata present, skipping %s', software['source_code_url'])

        elif provider == 'gitlab':
            # Check if we only want to update missing metadata or all metadata
            if not metadata_only_missing or any(k not in software for k in GITLAB_REQUIRED_KEYS):
                gitlab_projects.append(software)
            else:
                logging.debug('all metadata present, skipping %s', software['source_code_url'])

    if github_projects:
        logging.info('processing %s GitHub projects', len(github_projects))
        add_github_metadata(step, github_projects, errors)

    if gitlab_projects:
        logging.info('processing %s GitLab projects', len(gitlab_projects))
        add_gitlab_metadata(step, gitlab_projects, errors)

    if errors:
        logging.error("errors occurred during processing")
        print('\n'.join(errors))
        sys.exit(1)
