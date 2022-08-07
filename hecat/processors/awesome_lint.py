"""awesome_lint processor
Checks entries against awesome-selfhosted guidelines
https://github.com/awesome-selfhosted/awesome-selfhosted

# .hecat.yml
steps:
  - name: lint
    module: processors/awesome_lint
    module_options:
      source_directory: awesome-selfhosted-data
      items_in_delegate_to_fatal: False # optional, default True
      licenses_files: # optional default ['licenses.yml']
        - licenses.yml
        - licenses-nonfree.yml

If items_in_delegate_to_fatal is False, don't abort when entries are found in a section with 'delegate_to' set
"""

import re
import logging
import sys
from ..utils import load_yaml_data

SOFTWARE_REQUIRED_FIELDS = ['description', 'website_url', 'source_code_url', 'licenses', 'tags']
SOFTWARE_REQUIRED_LISTS = ['licenses', 'tags']
TAGS_REQUIRED_FIELDS = ['description']
LICENSES_REQUIRED_FIELDS= ['identifier', 'name', 'url']

def check_required_fields(item, errors, required_fields=[], required_lists=[], severity='error'):
    """check that keys (required_fields) are defined and do not have length zero
       check that each item in required_lists is defined and does not have length zero
    """
    for key in required_fields:
        try:
            assert len(item[key]) > 0
        except KeyError:
            error_msg = "{}: {} is undefined".format(item['name'], key)
            if severity == 'error':
                logging.error(error_msg)
                errors.append(error_msg)
            else:
                logging.warning(error_msg)
        except AssertionError:
            error_msg = "{}: {} is empty".format(item['name'], key)
            if severity == 'error':
                logging.error(error_msg)
                errors.append(error_msg)
            else:
                logging.warning(error_msg)
    for key in required_lists:
        try:
            for value in item[key]:
                try:
                    assert len(value) > 0
                except AssertionError:
                    error_msg = "{}: {} list contains an empty string".format(item['name'], key, value)
                    if severity == 'error':
                        logging.error(error_msg)
                        errors.append(error_msg)
                    else:
                        logging.warning(error_msg)
        except KeyError:
            error_msg = "{}: {} is undefined".format(item['name'], key)
            if severity == 'error':
                logging.error(error_msg)
                errors.append(error_msg)
            else:
                logging.warning(error_msg)


def check_description_syntax(software, errors):
    """check that description is shorter than 250 characters, starts with a capital letter and ends with a dot"""
    try:
        assert len(software['description']) <= 250
    except AssertionError:
        error_msg = "{}: description is longer than 250 characters".format(software['name'])
        logging.error(error_msg)
        errors.append(error_msg)
    # not blocking/only raise a warning since description might not start with a capital for a good reason (see üwave, groceri.es...)
    try:
        assert software['description'][0].isupper()
    except AssertionError:
        warning_msg = ("{}: description does not start with a capital letter").format(software['name'])
        logging.warning(warning_msg)
    try:
        assert software['description'].endswith('.')
    except AssertionError:
        error_msg = ("{}: description does not end with a dot").format(software['name'])
        logging.error(error_msg)
        errors.append(error_msg)


def check_licenses_in_licenses_list(software, licenses_list, errors):
    """check that all licenses for a software item are listed in the main licenses list"""
    for license_name in list(software['licenses']):
        try:
            assert any(license['identifier'] == license_name for license in licenses_list)
        except AssertionError:
            error_msg = "{}: license {} is not listed in the main licenses list".format(software['name'], license_name)
            logging.error(error_msg)
            errors.append(error_msg)


def check_tags_in_tags_list(software, tags_list, errors):
    """check that all tags for a software item are listed in the main tags list"""
    for tag_name in list(software['tags']):
        try:
            assert any(tag['name'] == tag_name for tag in tags_list)
        except AssertionError:
            error_msg = "{}: tag {} is not listed in the main tags list".format(software['name'], tag_name)
            logging.error(error_msg)
            errors.append(error_msg)


def check_related_tags_in_tags_list(tag, tags_list, errors):
    """check that all related_tags for a tag are listed in the main tags list"""
    for related_tag_name in tag['related_tags']:
        try:
            assert any(tag2['name'] == related_tag_name for tag2 in tags_list)
        except AssertionError:
            error_msg = "{}: related tag {} is not listed in the main tags list".format(tag['name'], related_tag_name)
            logging.error(error_msg)
            errors.append(error_msg)

def check_delegate_to_sections_empty(step, software, tags_with_delegate_to, errors):
    """check that the first tag in the tags list does not match a tag with delegate_to set"""
    first_tag = software['tags'][0]
    try:
        assert first_tag not in tags_with_delegate_to
    except AssertionError:
        error_msg = "{}: the first tag {} points to a tag delegated to another list.".format(software['name'], first_tag)
        if 'items_in_delegate_to_fatal' in step['module_options'].keys() and not step['module_options']['items_in_delegate_to_fatal']:
            logging.warning(error_msg)
        else:
            logging.error(error_msg)
            errors.append(error_msg)

def check_external_link_syntax(software, errors):
    """check that external links are of the form [text](url)"""
    try:
        for link in software['external_links']:
            try:
                assert re.match(r'^\[.*\]\(.*\)$', link)
            except AssertionError:
                error_msg = ("{}: the syntax for external link {} is incorrect").format(software['name'], link)
                logging.error(error_msg)
                errors.append(error_msg)
    except KeyError:
        pass


def check_not_archived(software, errors):
    """check that a software item is not marked as archived: True"""
    try:
        assert not software['archived']
    except AssertionError:
        error_msg = ("{}: the project is archived").format(software['name'])
        logging.error(error_msg)
        errors.append(error_msg)
    except KeyError:
        pass


def awesome_lint(step):
    """check all software entries against awesome-selfhosted formatting guidelines"""
    logging.info('checking software entries/tags against awesome-selfhosted formatting guidelines.')
    software_list = load_yaml_data(step['module_options']['source_directory'] + '/software')
    if 'licenses_files' not in step['module_options']:
        step['module_options']['licenses_files'] = ['/licenses.yml']
    licenses_list = []
    for filename in step['module_options']['licenses_files']:
        licenses_list = licenses_list + load_yaml_data(step['module_options']['source_directory'] + '/' + filename)
    tags_list = load_yaml_data(step['module_options']['source_directory'] + '/tags')
    tags_with_delegate_to = []
    for tag in tags_list:
        if 'delegate_to' in tag and tag['delegate_to']:
            tags_with_delegate_to.append(tag['name'])
    errors = []
    for software in software_list:
        check_required_fields(software, errors, required_fields=SOFTWARE_REQUIRED_FIELDS, required_lists=SOFTWARE_REQUIRED_LISTS)
        check_description_syntax(software, errors)
        check_licenses_in_licenses_list(software, licenses_list, errors)
        check_tags_in_tags_list(software, tags_list, errors)
        check_delegate_to_sections_empty(step, software, tags_with_delegate_to, errors)
        check_external_link_syntax(software, errors)
        check_not_archived(software, errors)
    for tag in tags_list:
        check_related_tags_in_tags_list(tag, tags_list, errors)
        check_required_fields(tag, errors, required_fields=TAGS_REQUIRED_FIELDS, severity='warning')
    for license in licenses_list:
        check_required_fields(license, errors, required_fields=LICENSES_REQUIRED_FIELDS)
    if errors:
        logging.error("There were errors during processing")
        sys.exit(1)
