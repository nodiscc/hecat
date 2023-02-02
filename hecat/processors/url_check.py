"""url_check processor
Check data for dead links/URLs not responding

# .hecat.yml
steps:
  - name: check URLs
    module: processors/url_check
    module_options:
      source_directories: # (default []) check URLs in all .yml files under these directories
        - awesome-selfhosted-data/software
        - awesome-selfhosted-data/tags
      source_files: # (default []) check URLs in these files
        - shaarli.yml
        - awesome-selfhosted-data/licenses.yml
      check_keys: # (default ['url', 'source_code_url', 'website_url', 'demo_url']) YAML keys containing URLs to check, if they exist
        - url
        - source_code_url
        - website_url
        - demo_url
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

def check_return_code(url, current_item_index, total_item_count, errors):
    try:
        response = requests.get(url, headers={"Range": "bytes=0-200", "User-Agent": "hecat/0.0.1"}, timeout=10)
        if response.status_code in VALID_HTTP_CODES:
            logging.info('[%s/%s] %s HTTP %s', current_item_index, total_item_count, url, response.status_code)
        else:
            error_msg = '{} - HTTP {}'.format(url, response.status_code)
            logging.error('[%s/%s] %s', current_item_index, total_item_count, error_msg)
            errors.append(error_msg)
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout, requests.exceptions.ContentDecodingError) as connection_error:
        error_msg = 'URL {} : {}'.format(url, connection_error)
        logging.error('[%s/%s] %s', current_item_index, total_item_count, error_msg)
        errors.append(error_msg)

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
    for source_directory in step['module_options']['source_directories']: # TODO factorize
        new_data = load_yaml_data(source_directory)
        data = data + new_data
    for source_file in step['module_options']['source_files']:
        new_data = load_yaml_data(source_file)
        data = data + new_data
    total_item_count = len(data)
    logging.info('loaded %s items', total_item_count)
    current_item_index = 1
    for item in data:
        for key_name in step['module_options']['check_keys']:
            try:
                if any(re.search(regex, item[key_name]) for regex in step['module_options']['exclude_regex']):
                    logging.debug('[%s/%s] skipping URL %s, matches exclude_regex', current_item_index, total_item_count, item[key_name])
                    continue
                else:
                    if item[key_name] not in checked_urls:
                        check_return_code(item[key_name], current_item_index, total_item_count, errors)
                        checked_urls.append(item[key_name])
                current_item_index = current_item_index + 1
            except KeyError:
                pass
    if errors:
        logging.error("There were errors during processing")
        print('\n'.join(errors))
        if 'errors_are_fatal' in step['module_options'].keys() and step['module_options']['errors_are_fatal']:
            sys.exit(1)