"""github_metadata processor
Gathers project/repository metadata from GitHub API and adds some fields to YAML data (`updated_at`, `stargazers_count`, `archived`, `current_release`, `commit_history`).

# hecat.yml
steps:
  - step: process
    module: processors/github_metadata
    module_options:
      source_directory: tests/awesome-selfhosted-data # directory containing YAML data and software subdirectory
      gh_metadata_only_missing: False # (default False) only gather metadata for software entries in which one of stargazers_count,updated_at, archived, current_release, commit_history is missing
      commit_history_fetch_months: 6 # (default 3) number of months to fetch from GitHub API
      commit_history_clean_months: 24 # (default 12) number of months of commit history to keep after cleanup
      sleep_time: 3.7 # (default 60) sleep for this amount of time before each request to Github API
      batch_size: 10 # (default 30) number of repositories to include in each batch request to Github API
      max_retries: 3 # (default 3) maximum number of retries for API errors (502, 503, 504, 429)

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

def extract_repo_identifier(url):
    """extract the repository owner/name from the URL"""
    re_result = re.search(r'^https?:\/\/github\.com\/([^\/]+)\/([^\/]+)\/?$', url)
    if re_result:
        owner = re_result.group(1)
        repo = re_result.group(2)
        return f"{owner}/{repo}"
    logging.debug('extract_repo_identifier: failed to extract owner/repo from URL: %s', url)
    return None

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

    history_queries_str = "\n".join([mq[2] for mq in month_queries])

    def process_batch(batch, batch_num, total_batches, attempt=1):
        """Process a single batch of repositories"""
        logging.info("Processing batch %s/%s (batch size: %s)", batch_num, total_batches, len(batch))
        logging.debug('current batch: ' + str(batch))
        repos_query = " ".join([f"repo:{repo}" for repo in batch])

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
        graphql_response_header = None
        data = None
        batch_success = False
        
        # Get configured sleep_time
        if 'sleep_time' in step['module_options']:
            base_sleep_time = step['module_options']['sleep_time']
        else:
            base_sleep_time = 60
        
        try:
            graphql_response = requests.post(github_graphql_api,
                                           json={"query": query},
                                           headers=headers,
                                           timeout=60)
            graphql_response_header = graphql_response.headers
            
            # Check for API errors that should be retried
            if graphql_response.status_code in [502, 503, 504, 429]: # i.e error codes that probably will be resolved by retrying
                if attempt <= max_retries:
                    backoff_time = base_sleep_time * (2 ** (attempt - 1))
                    logging.warning('GraphQL request failed with status code %s (attempt %s/%s), waiting %s seconds', 
                                  graphql_response.status_code, attempt, max_retries, backoff_time)
                    logging.debug('sleeping for %s between attempts', backoff_time)
                    time.sleep(backoff_time)
                    
                    # Attempt 1: Retry with same batch
                    if attempt == 1:
                        logging.info('Retrying batch %s with same size', batch_num)
                        return process_batch(batch, batch_num, total_batches, attempt + 1)
                    
                    # Attempt 2+: Split batch and retry
                    elif len(batch) > 1:
                        # Calculate split size: halve the batch with each retry
                        split_factor = 2 ** (attempt - 1)  # 2, 4, 8...
                        num_splits = min(split_factor, len(batch))
                        
                        logging.info('Splitting batch %s into %s smaller chunks (attempt %s)', 
                                   batch_num, num_splits, attempt)
                        
                        # Split batch into chunks
                        chunk_size = max(1, len(batch) // num_splits)
                        for i in range(num_splits):
                            start_idx = i * chunk_size
                            if i == num_splits - 1:
                                # Last chunk gets remaining items
                                chunk = batch[start_idx:]
                            else:
                                chunk = batch[start_idx:start_idx + chunk_size]
                            
                            if chunk:
                                chunk_suffix = chr(97 + i)  # a, b, c, ...
                                process_batch(chunk, f"{batch_num}{chunk_suffix}", total_batches, attempt)
                                
                                # Sleep between split chunks to avoid rate limiting (not after the last chunk)
                                if i < num_splits - 1:
                                    logging.debug('sleeping for %s seconds between split chunks', base_sleep_time)
                                    time.sleep(base_sleep_time)
                        return
                    
                    # Single repo that keeps failing
                    else:
                        logging.error('Single repository %s failed after attempt %s', batch[0], attempt)
                        if attempt < max_retries:
                            return process_batch(batch, batch_num, total_batches, attempt + 1)
                        else:
                            errors.append(f'Failed to fetch metadata for repository {batch[0]} after {max_retries} attempts')
                            logging.error('Failed to fetch metadata for repository %s after all retries', batch[0])
                            return
                else:
                    errors.append(f'Response code of POST request (GraphQL): {graphql_response.status_code} after {max_retries} retries')
                    logging.error('GraphQL request failed with status code %s after %s retries, skipping batch', 
                                graphql_response.status_code, max_retries)
                    logging.debug('Query: %s', query)
                    logging.debug('Headers: %s', headers)
                    logging.debug('Response: %s', graphql_response.text)
                    return
            
            # Check for other non-200 status codes (don't retry these)
            if graphql_response.status_code != 200:
                errors.append(f'Response code of POST request (GraphQL): {graphql_response.status_code}')
                logging.error('GraphQL request failed with status code %s, skipping batch', graphql_response.status_code)
                return
            
            # Success - parse the response
            data = graphql_response.json()
            if 'errors' in data:
                for error in data['errors']:
                    errors.append(error['message'])
                sys.exit(1)
            
            batch_success = True
            
        except Exception as e:
            exception_type = type(e).__name__
            exception_details = str(e)
            logging.error('Exception during GraphQL request for batch %s: %s', batch_num, exception_type)
            logging.debug('Exception details: %s - %s', exception_type, exception_details)
            errors.append(f'Batch {batch_num}: {exception_type} - {exception_details}')
            return
        
        # If we didn't succeed, return early (already handled above)
        if not batch_success:
            return

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
            return

        for edge in data["data"]["search"]["repos"]:
            repo = edge["repo"]
            software = None
            for project in github_projects:
                if extract_repo_identifier(repo["url"]).casefold() == extract_repo_identifier(project['source_code_url']).casefold():
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

    # Get sleep time for spacing between batches (rate limit prevention)
    if 'sleep_time' in step['module_options']:
        between_batch_sleep = step['module_options']['sleep_time']
    else:
        between_batch_sleep = 60

    counter = 0
    for batch in batches:
        counter += 1
        process_batch(batch, counter, len(batches))
        
        # Sleep between batches to avoid rate limiting (only if not the last batch)
        if counter < len(batches):
            logging.debug('sleeping for %s seconds between batches', between_batch_sleep)
            time.sleep(between_batch_sleep)

    if errors:
        logging.error("There were errors during processing")
        print('\n'.join(errors))
        sys.exit(1)
