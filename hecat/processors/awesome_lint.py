"""awesome_lint processor
Checks entries against awesome-selfhosted guidelines
https://github.com/awesome-selfhosted/awesome-selfhosted

# .hecat.yml
steps:
  - name: lint
    module: processors/awesome_lint
    module_options:
      source_directory: tests/awesome-selfhosted-data
      items_in_redirect_fatal: False # (optional, default True) fail when entries have a tag with 'redirect' set in their `tags` list
      last_updated_error_days: 3650 # (optional, default 3650) raise an error message for projects that have not been updated in this number of days
      last_updated_warn_days: 365 # (optional, default 365) raise a warning message for projects that have not been updated in this number of days
      last_updated_info_days: 186 # (optional, default 186) raise an info message for projects that have not been updated in this number of days
      licenses_files: # (optional, default ['licenses.yml']) path to files containing lists of licenses
        - licenses.yml
        - licenses-nonfree.yml
      last_updated_skip: # (optional, default []) list of items (source_code_url) for which the last update date check should not produce errors/warnings
        - https://github.com/tomershvueli/homepage # simple/no maintenance required https://github.com/awesome-selfhosted/awesome-selfhosted-data/pull/242
        - https://github.com/abrenaut/posio # simple/no maintenance required
        - https://github.com/knrdl/bicimon # simple/no maintenance required
        - https://github.com/Kshitij-Banerjee/Cubiks-2048 # simple/no maintenance required
      platforms_required_fields: ['description'] # (optional, default ['description']) attributes that must be defined for all platforms


source_directory: path to directory where data can be found. Directory structure:
├── software
│   ├── mysoftware.yml # .yml files containing software data
│   ├── someothersoftware.yml
│   └── ...
├── platforms
│   ├── bash.yml # .yml files containing language/platforms data
│   ├── python.yml
│   └── ...
├── tags
│   ├── groupware.yml # .yml files containing tags/categories data
│   ├── enterprise-resource-planning.yml
│   └── ...
├── licenses.yml # yaml list of licenses
└── licenses-nonfree.yml # yaml list of licenses
"""

import re
import logging
import sys
from datetime import datetime, timedelta
from ..utils import load_yaml_data

SOFTWARE_REQUIRED_FIELDS = ['description', 'website_url', 'source_code_url', 'licenses', 'tags']
SOFTWARE_REQUIRED_LISTS = ['licenses', 'tags']
TAGS_REQUIRED_FIELDS = ['description']
LICENSES_REQUIRED_FIELDS= ['identifier', 'name', 'url']

def check_required_fields(item, errors, required_fields=[], required_lists=[], severity=logging.error):
    """check that keys (required_fields) are defined and do not have length zero
       check that each item in required_lists is defined and does not have length zero
    """
    for key in required_fields:
        try:
            assert len(item[key]) > 0
        except KeyError:
            message = "{}: {} is undefined".format(item['name'], key)
            log_exception(message, errors, severity)
        except AssertionError:
            message = "{}: {} is empty".format(item['name'], key)
            log_exception(message, errors, severity)
    for key in required_lists:
        try:
            for value in item[key]:
                try:
                    assert len(value) > 0
                except AssertionError:
                    message = "{}: {} list contains an empty string".format(item['name'], key)
                    log_exception(message, errors, severity)
        except KeyError:
            message = "{}: {} is undefined".format(item['name'], key)
            log_exception(message, errors, severity)


def log_exception(message, errors, severity=logging.error):
    """log a warning or error message, append the error to the global error list if severity=logging.error"""
    severity(message)
    if severity == logging.error:
        errors.append(message)


def check_description_syntax(software, errors):
    """check that description is shorter than 250 characters, starts with a capital letter and ends with a dot"""
    try:
        assert len(software['description']) <= 250
    except AssertionError:
        message = "{}: description is longer than 250 characters".format(software['name'])
        log_exception(message, errors)
    # not blocking/only raise a warning since description might not start with a capital for a good reason (see üwave, groceri.es...)
    try:
        assert software['description'][0].isupper()
    except AssertionError:
        message = ("{}: description does not start with a capital letter").format(software['name'])
        log_exception(message, errors, severity=logging.warning)
    try:
        assert software['description'].endswith('.')
    except AssertionError:
        message = ("{}: description does not end with a dot").format(software['name'])
        log_exception(message, errors)

def check_attribute_in_list(item, attribute_name, key, attributes_list, errors):
    """check that all licenses/tags/platforms/related_tags for a software/tag item are listed in the main licenses/tags/platforms list.
    :param dict software: the objet containing data to check (e.g. software item or tag item)
    :param str attribute_name: attribute name (e.g. 'licenses' or 'tags')
    :param str key: key name to check against the main list (e.g. 'identifier' or 'name')
    :param list attributes_list: main list to check the value of each key/value pair against (eg licenses_list or tags_list)
    :param list errors: the list of previous errors
    """
    if attribute_name in item:
        for attr in list(item[attribute_name]):
            try:
                assert any(item2[key] == attr for item2 in attributes_list)
            except AssertionError:
                message = "{}: {} {} is not listed in the main {} list".format(item['name'], attribute_name, attr, attribute_name)
                log_exception(message, errors)

def check_tag_has_at_least_items(tag, software_list, tags_with_redirect, errors, min_items=3):
    """check that a tag has at least N software items attached to it"""
    tag_items_count = 0
    for software in software_list:
        if tag['name'] in software['tags']:
            tag_items_count += 1
    try:
        assert tag_items_count >= min_items
        logging.debug('{} items tagged {}'.format(tag_items_count, tag['name']))
    except AssertionError:
        if tag['name'] in tags_with_redirect and tag_items_count == 0:
            logging.debug('0 items tagged {}, but this tag has the redirect attribute set'.format(tag['name']))
        else:
            message = "{} items tagged {}, each tag must have at least {} items attached".format(tag_items_count, tag['name'], min_items)
            log_exception(message, errors)

def check_redirect_sections_empty(step, software, tags_with_redirect, errors):
    """check that any tag in the tags list does not match a tag with redirect set"""
    for tag in software['tags']:
        try:
            assert tag not in tags_with_redirect
        except AssertionError:
            message = "{}: tag {} points to a tag which redirects to another list.".format(software['name'], tag)
            if 'items_in_redirect_fatal' in step['module_options'].keys() and not step['module_options']['items_in_redirect_fatal']:
                log_exception(message, errors, severity=logging.warning)
            else:
                log_exception(message, errors)


def check_external_link_syntax(software, errors):
    """check that external links are of the form [text](url)"""
    try:
        for link in software['external_links']:
            try:
                assert re.match(r'^\[.*\]\(.*\)$', link)
            except AssertionError:
                message = ("{}: the syntax for external link {} is incorrect").format(software['name'], link)
                log_exception(message, errors)
    except KeyError:
        pass


def check_not_archived(software, errors):
    """check that a software item is not marked as archived: True"""
    try:
        assert not software['archived']
    except AssertionError:
        message = ("{}: the project is archived").format(software['name'])
        log_exception(message, errors)
    except KeyError:
        pass

def check_last_updated(software, step, errors):
    """checks the date of last update to a project, emit info/warn/error message if older than configured thresholds"""
    if 'updated_at' in software:
        last_update_time = datetime.strptime(software['updated_at'], "%Y-%m-%d")
        time_since_last_update = last_update_time - datetime.now()
        if software['source_code_url'] in step['module_options']['last_updated_skip']:
           logging.info('%s: skipping last update time check as per configuration (last_updated_skip) (%s)', software['name'], time_since_last_update)
        elif last_update_time < datetime.now() - timedelta(days=step['module_options']['last_updated_error_days']):
            message = '{}: last updated {} ago, older than {} days'.format(software['name'], time_since_last_update, step['module_options']['last_updated_error_days'])
            log_exception(message, errors, severity=logging.error)
        elif last_update_time < datetime.now() - timedelta(days=step['module_options']['last_updated_warn_days']):
            logging.warning('%s: last updated %s ago, older than %s days', software['name'], time_since_last_update, step['module_options']['last_updated_warn_days'])
        elif last_update_time < datetime.now() - timedelta(days=step['module_options']['last_updated_info_days']):
            logging.info('%s: last updated %s ago, older than %s days', software['name'], time_since_last_update, step['module_options']['last_updated_info_days'])
        else:
            logging.debug('%s: last updated %s ago', software['name'], time_since_last_update)

def check_boolean_attributes(software, errors):
    """check if the depends_3rdparty attribute is a boolean"""
    if 'depends_3rdparty' in software:
        if not type(software['depends_3rdparty']) == bool:
            message = '{}: depends_3rdparty must be a valid boolean value (true/false/True/False), got "{}"'.format(software['name'], software['depends_3rdparty'])
            log_exception(message, errors, severity=logging.error)

def awesome_lint(step):
    """check all software entries against formatting guidelines"""
    logging.info('checking software entries/tags against formatting guidelines.')
    software_list = load_yaml_data(step['module_options']['source_directory'] + '/software')
    if 'last_updated_info_days' not in step['module_options']:
        step['module_options']['last_updated_info_days'] = 186
    if 'last_updated_warn_days' not in step['module_options']:
        step['module_options']['last_updated_warn_days'] = 365
    if 'last_updated_error_days' not in step['module_options']:
        step['module_options']['last_updated_error_days'] = 3650
    if 'licenses_files' not in step['module_options']:
        step['module_options']['licenses_files'] = ['/licenses.yml']
    if  'last_updated_skip' not in step['module_options']:
        step['module_options']['last_updated_skip'] = []
    if 'platforms_required_fields' not in step['module_options']:
        step['module_options']['platforms_required_fields'] = ['description']
    licenses_list = []
    for filename in step['module_options']['licenses_files']:
        licenses_list = licenses_list + load_yaml_data(step['module_options']['source_directory'] + '/' + filename)
    tags_list = load_yaml_data(step['module_options']['source_directory'] + '/tags')
    tags_with_redirect = []
    for tag in tags_list:
        if 'redirect' in tag and tag['redirect']:
            tags_with_redirect.append(tag['name'])
    platforms_list = load_yaml_data(step['module_options']['source_directory'] + '/platforms')
    errors = []
    for tag in tags_list:
        check_attribute_in_list(tag, 'related_tags', 'name', tags_list, errors)
        check_required_fields(tag, errors, required_fields=TAGS_REQUIRED_FIELDS, severity=logging.warning)
        check_tag_has_at_least_items(tag, software_list, tags_with_redirect, errors, min_items=3)
    for platform in platforms_list:
        check_required_fields(platform, errors, required_fields=step['module_options']['platforms_required_fields'])
    for software in software_list:
        check_required_fields(software, errors, required_fields=SOFTWARE_REQUIRED_FIELDS, required_lists=SOFTWARE_REQUIRED_LISTS)
        check_description_syntax(software, errors)
        check_attribute_in_list(software, 'licenses', 'identifier', licenses_list, errors)
        check_attribute_in_list(software, 'tags', 'name', tags_list, errors)
        check_attribute_in_list(software, 'platforms', 'name', platforms_list, errors)
        check_redirect_sections_empty(step, software, tags_with_redirect, errors)
        check_external_link_syntax(software, errors)
        check_not_archived(software, errors)
        check_last_updated(software, step, errors)
        check_boolean_attributes(software, errors)
    for license in licenses_list:
        check_required_fields(license, errors, required_fields=LICENSES_REQUIRED_FIELDS)
    if errors:
        logging.error("There were errors during processing")
        sys.exit(1)
