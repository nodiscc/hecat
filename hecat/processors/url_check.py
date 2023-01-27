"""url_check processor
Check URL return codes

# .hecat.yml
steps:
  - name: check URLs
    module: processors/url_check
    module_options:
      source_directories: # check URLs in all .yml files under these directories
        - awesome-selfhosted-data/software
        - awesome-selfhosted-data/tags
      source_files: # check URLs in these files
        - shaarli.yml
        - awesome-selfhosted-data/licenses.yml
      check_keys: # (list) YAML keys containing URLs to check, if they exist
        - url
        - source_code_url
        - website_url
        - demo_url
      errors_are_fatal: False # (default False) if True exit with error code 1 at the end of processing, if any checks were unsuccessful
      exclude_regex: # (list, default empty) don't check URLs matching these regular expressions
        - '^https://github.com/[\w\.\-]+/[\w\.\-]+$' # don't check URLs that will be processed by the github_metadata module
"""

import sys
import ruamel.yaml
import logging
import re
from ..utils import load_yaml_data
import requests

VALID_HTTP_CODES = [200, 206]
# INVALID_HTTP_CODES = [403, 404, 500]

def check_return_code(url, errors):
    try:
        response = requests.get(url, headers={"Range": "bytes=0-200", "User-Agent": "hecat/0.0.1"}, timeout=10)
        if response.status_code in VALID_HTTP_CODES:
            logging.info('%s HTTP %s', url, response.status_code)
        else:
            error_msg = '{} - HTTP {}'.format(url, response.status_code)
            logging.error(error_msg)
            errors.append(error_msg)
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout, requests.exceptions.ContentDecodingError) as connection_error:
        error_msg = 'URL {} : {}'.format(url, connection_error)
        logging.error(error_msg)
        errors.append(error_msg)

def check_urls(step):
    data = []
    errors = []
    checked_urls = []
    if 'exclude_regex' not in step['module_options'].keys():
        step['module_options']['exclude_regex'] = []
    for source_directory in step['module_options']['source_directories']: # TODO factorize
        new_data = load_yaml_data(source_directory)
        data = data + new_data
    for source_file in step['module_options']['source_files']:
        new_data = load_yaml_data(source_file)
        data = data + new_data
    for item in data:
        for key_name in step['module_options']['check_keys']:
            for regex in step['module_options']['exclude_regex']:
                try:
                    if re.search(regex, item[key_name]):
                        logging.debug('skipping URL %s, matches exclude_regex', item[key_name])
                        continue
                    else:
                        if item[key_name] not in checked_urls:
                            check_return_code(item[key_name], errors)
                            checked_urls.append(item[key_name])
                except KeyError:
                    pass
    if errors:
        logging.error("There were errors during processing")
        print('\n'.join(errors))
        if 'errors_are_fatal' in step['module_options'].keys() and step['module_options']['errors_are_fatal']:
            sys.exit(1)
