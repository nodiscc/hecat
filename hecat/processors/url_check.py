"""url_check processor
Check data for dead links (HTTP error codes, timeouts, SSL/TLS errors...)

# .hecat.yml
steps:
  - name: check URLs
    module: processors/url_check
    module_options:
      source_directories: # (default []) check URLs in all .yml files under these directories
        - tests/awesome-selfhosted-data/software
        - tests/awesome-selfhosted-data/tags
      source_files: # (default []) check URLs in these files
        - tests/shaarli.yml
        - tests/awesome-selfhosted-data/licenses.yml
      check_keys: # (default ['url', 'source_code_url', 'website_url', 'demo_url']) YAML keys containing URLs to check, if they exist
        - url
        - source_code_url
        - website_url
        - demo_url
      failed_urls_file: 'failed_urls.txt'  # specify the file to store failed URLs
      escalation_limit: 3  # raise an error instead of a warning after this number of consecutive failures on a single URL
      errors_are_fatal: False # (default False) if True exit with error code 1 at the end of processing, if any checks were unsuccessful
      exclude_regex: # (default []) don't check URLs matching these regular expressions
        - '^https://github.com/[\w\.\-]+/[\w\.\-]+$' # don't check URLs that will be processed by the github_metadata module
        - '^https://www.youtube.com/watch.*$' # don't check youtube video URLs, always returns HTTP 200 even for unavailable videos
"""

import sys
import ruamel.yaml
import logging
import re
from ..utils import load_yaml_data
import requests

VALID_HTTP_CODES = [200, 206]
# INVALID_HTTP_CODES = [403, 404, 500]

def check_return_code(url, current_item_index, total_item_count, errors, failed_urls_file, escalation_limit):
    try:
        # GET only first 200 bytes when possible, servers that do not support the Range: header will simply return the entire page
        response = requests.get(url, headers={"Range": "bytes=0-200", "User-Agent": "hecat/0.0.1"}, timeout=10)
        if response.status_code in VALID_HTTP_CODES:
            logging.info('[%s/%s] %s HTTP %s', current_item_index, total_item_count, url, response.status_code)
            return True
        else:
            error_msg = '{} : HTTP {}'.format(url, response.status_code)
            logging.warning('[%s/%s] %s', current_item_index, total_item_count, error_msg)
            handle_failed_url(url, failed_urls_file, escalation_limit)
            return False
    # Invalid URL should be handled as an error directly
    except (requests.exceptions.InvalidURL, requests.exceptions.InvalidSchema) as invalid_url_error:
        error_msg = '{} : {}'.format(url, invalid_url_error)
        logging.error('[%s/%s] %s', current_item_index, total_item_count, error_msg)
        errors.append(error_msg)
        return False
    # Connection errors should be handled as warnings, but escalate to errors after a certain number of attempts
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout, requests.exceptions.ContentDecodingError) as connection_error:
        error_msg = '{} : {}'.format(url, connection_error)
        if should_escalate(url, failed_urls_file, escalation_limit):
            logging.error('[%s/%s] %s', current_item_index, total_item_count, error_msg)
        else:
            logging.warning('[%s/%s] %s', current_item_index, total_item_count, error_msg)
        handle_failed_url(url, failed_urls_file, escalation_limit)
        return False

def check_urls(step):
    data = []
    errors = []
    checked_urls = []
    if 'exclude_regex' not in step['module_options'].keys():
        step['module_options']['exclude_regex'] = []
    if 'source_directories' not in step['module_options'].keys():
        step['module_options']['source_directories'] = []
    if 'source_files' not in step['module_options'].keys():
        step['module_options']['source_files'] = []
    if 'check_keys' not in step['module_options'].keys():
        step['module_options']['check_keys'] = ['url', 'source_code_url', 'website_url', 'demo_url']
    for source_dir_or_file in step['module_options']['source_directories'] + step['module_options']['source_files']:
        new_data = load_yaml_data(source_dir_or_file)
        data = data + new_data
    total_item_count = len(data)
    logging.info('loaded %s items', total_item_count)
    skipped_count = 0
    success_count = 0
    error_count = 0
    current_item_index = 1
    for item in data:
        for key_name in step['module_options']['check_keys']:
            try:
                if any(re.search(regex, item[key_name]) for regex in step['module_options']['exclude_regex']):
                    ...
                else:
                    if item[key_name] not in checked_urls:
                        if check_return_code(item[key_name], current_item_index, total_item_count, errors,
                                             step['module_options']['failed_urls_file'],
                                             step['module_options']['escalation_limit']):
                            success_count = success_count + 1
                            remove_from_failed_urls(item[key_name], step['module_options']['failed_urls_file'])
                        else:
                            error_count = error_count + 1
                            checked_urls.append(item[key_name])
            except KeyError:
                pass
        current_item_index = current_item_index + 1
    logging.info('processing complete. Successful: %s - Skipped: %s - Errors: %s', success_count, skipped_count, error_count)
    if errors:
        logging.error("There were errors during processing")
        print('\n'.join(errors))
        if 'errors_are_fatal' in step['module_options'].keys() and step['module_options']['errors_are_fatal']:
            sys.exit(1)

def should_escalate(url, failed_urls_file, escalation_limit):
    # Load existing failed URLs or create an empty list
    try:
        with open(failed_urls_file, 'r') as file:
            failed_urls = [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        return False

    # Check if the URL has reached the escalation limit
    if url in failed_urls:
        index = failed_urls.index(url)
        count = int(failed_urls[index + 1])
        return count >= escalation_limit

    return False

def handle_failed_url(url, failed_urls_file, escalation_limit):
    # Load existing failed URLs or create an empty list
    try:
        with open(failed_urls_file, 'r') as file:
            failed_urls = [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        failed_urls = []

    # Update the count for the current URL
    if url in failed_urls:
        index = failed_urls.index(url)
        count = int(failed_urls[index + 1]) + 1
        failed_urls[index + 1] = str(count)
        if count >= escalation_limit:
            logging.error('URL %s reached the escalation limit (%s).', url, escalation_limit)
    else:
        # Add the URL to the list with count 1
        failed_urls.extend([url, '1'])

    # Write the updated failed URLs list back to the file
    with open(failed_urls_file, 'w') as file:
        file.write('\n'.join(failed_urls))

def remove_from_failed_urls(url, failed_urls_file):
    # Load existing failed URLs or create an empty list
    try:
        with open(failed_urls_file, 'r') as file:
            failed_urls = [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        return

    # Remove the URL from the list
    if url in failed_urls:
        index = failed_urls.index(url)
        failed_urls.pop(index)
        failed_urls.pop(index)  # Remove the corresponding count

    # Write the updated failed URLs list back to the file
    with open(failed_urls_file, 'w') as file:
        file.write('\n'.join(failed_urls))
