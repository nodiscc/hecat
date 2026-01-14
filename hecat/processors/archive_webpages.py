"""archive webpages
Downloads a local archive of webpages ('url:' key of items in the data file). It is designed to archive bookmarks of Shaarli instances
You probably want to import data from Shaarli to hecat using the importers/shaarli_api module first.
Each webpage is saved in a separate directory named after the item 'id' key, under the ouptout directory configured in the module options.
The exporters/html_table module will display links to local copies of webpages in the output HTML list.

Note that yo may want to setup a system-wide ad-blocking mechanism to prevent wget from downloading
ads and annoyances, and save bandwidth and disk space in the process. See
https://gitlab.com/nodiscc/toolbox/-/tree/master/ARCHIVE/ANSIBLE-COLLECTION/roles/adblock_hosts or
set it up manually. Example using NetworkManager in dns=dnsmasq mode:
$ sudo mkdir /var/lib/dnsmasq
$ sudo wget -O /var/lib/dnsmasq/unified-hosts.txt https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts
$ echo 'addn-hosts=/var/lib/dnsmasq/unified-hosts.txt' | sudo tee /etc/NetworkManager/dnsmasq.d/adblock
$ sudo systemctl reload NetworkManager

Since the output directory may grow very large with many archived pages, you can deduplicate files using jdupes and hard-linking identical files:
$ jdupes --link-hard --recurse /path/to/archive/directory/

# $ cat tests/.hecat.archive_webpages.yml
steps:
  - name: archive webpages
    module: processors/archive_webpages
    module_options:
      data_file: tests/shaarli.yml # path to the YAML data file
      only_tags: ['doc'] # only download items tagged with all these tags
      exclude_tags: ['nodl'] # (default []), don't download items tagged with any of these tags
      exclude_regex: # (default []) don't archive URLs matching these regular expressions
        - '^https://[a-z]\.wikipedia.org/wiki/.*$' # don't archive wikipedia pages, supposing you have a local copy of wikipedia dumps from https://dumps.wikimedia.org/
      output_directory: 'tests/webpages' # path to the output directory for archived pages
      skip_already_archived: True # (default True) skip processing when item already has a 'archive_path': key
      clean_removed: True # (default False) remove existing archived pages which do not match any id in the data file
      clean_excluded: True # (default False) remove existing archived pages matching exclude_regex
      skip_failed: False # (default False) don't attempt to archive items for which the previous archival attempt failed (archive_error: True)

# $ hecat --config tests/.hecat.archive_webpages.yml

Data file format (output of import_shaarli module):
# shaarli.yml
- id: 1234 # required, unique id
  url: https://solar.lowtechmagazine.com/2016/10/pigeon-towers-a-low-tech-alternative-to-synthetic-fertilizers
  tags:
    - tag1
    - tag2
    - diy
    - doc
    - readlater
  ...
  private: false
  archive_path: 1234/solar.lowtechmagazine.com/2016/...-fertilizers.html # (added automatically) path to the local archived page, relative to output_directory/{public,private}/

Source directory structure:
└── shaarli.yml

Output directory structure:
└── webpages/
    ├── public/
    │   ├── 1234/ # id of the item in the YAML file
    │   │   └── solar.lowtechmagazine.com/
    │   │       └── 2016/
    │   │           └── .../
    │   │               ├── index.html # file/directory structure mirroring the original website
    │   │               ├── .../
    │   │               └── image.jpg
    │   ├── 1235/
    │   ├── 1236/
    │   └── ...
    └── private/
        ├── 5678/
        ├── 91011/
        └── ...

"""

import sys
import os
import logging
import subprocess
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse, unquote, quote
import ruamel.yaml
from ..utils import load_yaml_data, write_data_file

yaml = ruamel.yaml.YAML()
yaml.indent(sequence=2, offset=0)
yaml.width = 99999

def wget(step, item, wget_output_directory):
    """archive a webpage with wget, return the local path of the archived file"""
    try:
        os.mkdir(wget_output_directory)
    except FileExistsError:
        pass
    wget_process = subprocess.Popen(['/usr/bin/wget',
                                     '--continue',
                                     '--span-hosts',
                                     '--adjust-extension',
                                     '--timestamping',
                                     '--convert-links',
                                     '--page-requisites',
                                     '--no-verbose',
                                     '--timeout=30',
                                     '--tries=3',
                                     '-e', 'robots=off',
                                     '--user-agent="Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0"',
                                     item['url']],
                                   cwd=wget_output_directory,
                                   stdout=sys.stdout,
                                   stderr=sys.stderr,
                                   universal_newlines=True)
    wget_process.communicate()
    archive_relative_path = wget_output_path(item, wget_output_directory)
    if archive_relative_path is not None:
        local_archive_path = quote(str(item['id']) + '/' + archive_relative_path)
    else:
        local_archive_path = None
        logging.error('error while archiving %s', item['url'])
    return local_archive_path

# adapted from https://github.com/ArchiveBox/ArchiveBox/blob/master/archivebox/extractors/wget.py, MIT license
def wget_output_path(item, wget_output_directory):
    """calculate the path to the wgetted .html file, since wget may
    adjust some paths to be different than the base_url path.
    See docs on wget --adjust-extension (-E)
    """
    # Wget downloads can save in a number of different ways depending on the url:
    #    https://example.com
    #       > example.com/index.html
    #    https://example.com?v=zzVa_tX1OiI
    #       > example.com/index.html?v=zzVa_tX1OiI.html
    #    https://www.example.com/?v=zzVa_tX1OiI
    #       > example.com/index.html?v=zzVa_tX1OiI.html
    #    https://example.com/abc
    #       > example.com/abc.html
    #    https://example.com/abc/
    #       > example.com/abc/index.html
    #    https://example.com/abc?v=zzVa_tX1OiI.html
    #       > example.com/abc?v=zzVa_tX1OiI.html
    #    https://example.com/abc/?v=zzVa_tX1OiI.html
    #       > example.com/abc/index.html?v=zzVa_tX1OiI.html
    #    https://example.com/abc/test.html
    #       > example.com/abc/test.html
    #    https://example.com/abc/test?v=zzVa_tX1OiI
    #       > example.com/abc/test?v=zzVa_tX1OiI.html
    #    https://example.com/abc/test/?v=zzVa_tX1OiI
    #       > example.com/abc/test/index.html?v=zzVa_tX1OiI.html
    # There's also lots of complexity around how the urlencoding and renaming
    # is done for pages with query and hash fragments or extensions like shtml / htm / php / etc
    # Since the wget algorithm for -E (appending .html) is incredibly complex
    # and there's no way to get the computed output path from wget
    # in order to avoid having to reverse-engineer how they calculate it,
    # we just look in the output folder read the filename wget used from the filesystem
    without_fragment = urlparse(item['url'])._replace(fragment='').geturl().strip('//')
    without_query = urlparse(without_fragment)._replace(query='').geturl().strip('//')
    domain = urlparse(item['url']).netloc
    full_path = without_query.strip('/')
    search_dir = Path(wget_output_directory + '/' + domain.replace(":", "+") + unquote(urlparse(item['url']).path))
    for _ in range(4):
        if search_dir.exists():
            if search_dir.is_dir():
                html_files = [
                    f for f in search_dir.iterdir()
                    if re.search(".+\\.[Ss]?[Hh][Tt][Mm][Ll]?$", str(f), re.I | re.M)
                ]
                if html_files:
                    return str(html_files[0].relative_to(wget_output_directory))
                # sometimes wget'd URLs have no ext and return non-html
                # e.g. /some/example/rss/all -> some RSS XML content)
                #      /some/other/url.o4g   -> some binary unrecognized ext)
                # test this with archivebox add --depth=1 https://getpocket.com/users/nikisweeting/feed/all
                last_part_of_url = unquote(full_path.rsplit('/', 1)[-1])
                for file_present in search_dir.iterdir():
                    if file_present == last_part_of_url:
                        return str((search_dir / file_present).relative_to(wget_output_directory))
        # Move up one directory level
        search_dir = search_dir.parent
        if str(search_dir) == wget_output_directory:
            break
    # check for literally any file present that isn't an empty folder
    domain_dir = Path(domain.replace(":", "+"))
    files_within = list((Path(wget_output_directory) / domain_dir).glob('**/*.*'))
    if files_within:
        return str((files_within[-1]))
    # fallback to just the domain dir
    search_dir = Path(wget_output_directory) / domain.replace(":", "+")
    if search_dir.is_dir():
        return domain.replace(":", "+")
    return None

def initialize_output_directories(output_directory):
    """Create public and private subdirectories in the output directory"""
    for visibility in ['/public', '/private']:
        try:
            os.mkdir(output_directory + visibility)
        except FileExistsError:
            pass


def set_default_options(module_options):
    """Set default values for module options if not present"""
    if 'clean_removed' not in module_options:
        module_options['clean_removed'] = False
    if 'skip_failed' not in module_options:
        module_options['skip_failed'] = False
    if 'only_tags' not in module_options:
        module_options['only_tags'] = []


def get_local_archive_dir(output_directory, item):
    """Get the local archive directory path for an item based on its privacy setting"""
    visibility = 'private' if item['private'] else 'public'
    return f"{output_directory}/{visibility}/{item['id']}"


def is_item_excluded(item, module_options):
    """Check if item should be excluded based on tags or regex patterns
    Returns: (is_excluded: bool, excluded_by_tags: bool, excluded_by_regex: bool)
    """
    excluded_by_tags = ('exclude_tags' in module_options and
                       any(tag in item['tags'] for tag in module_options['exclude_tags']))
    excluded_by_regex = ('exclude_regex' in module_options and
                        any(re.search(regex, item['url']) for regex in module_options['exclude_regex']))
    return (excluded_by_tags or excluded_by_regex, excluded_by_tags, excluded_by_regex)


def handle_excluded_item(item, local_archive_dir, excluded_by_tags, excluded_by_regex, clean_excluded):
    """Handle an excluded item: clean up if needed and log the reason"""
    if clean_excluded:
        if os.path.isdir(local_archive_dir):
            logging.info('removing local archive directory %s', local_archive_dir)
            shutil.rmtree(local_archive_dir)
        item.pop('archive_path', None)

    if excluded_by_tags:
        logging.debug('skipping %s (id %s): one or more tags are present in exclude_tags', item['url'], item['id'])
    else:
        logging.debug('skipping %s (id %s): URL matches exclude_regex', item['url'], item['id'])


def should_process_item(item, module_options):
    """Determine if an item should be processed for archiving
    Returns: (should_process: bool, reason: str)
    Reasons: 'process', 'already_archived', 'failed', 'no_matching_tags'
    """
    # skip already archived items when skip_already_archived: True
    if (('skip_already_archived' not in module_options or
            module_options['skip_already_archived']) and
        'archive_path' in item and item['archive_path'] is not None):
        return (False, 'already_archived')

    # skip failed items when skip_failed: True
    if (module_options.get('skip_failed', False) and
        item.get('archive_error', False)):
        return (False, 'failed')

    # archive items matching only_tags (ALL tags must be present)
    if set(module_options['only_tags']).issubset(set(item['tags'])):
        return (True, 'process')

    return (False, 'no_matching_tags')


def archive_webpages(step):
    """archive webpages linked from each item's 'url', if their tags match one of step['only_tags'],
    write path to local archive to a new key 'archive_path' in the original data file for each downloaded item
    """
    downloaded_count = 0
    skipped_count = 0
    error_count = 0

    initialize_output_directories(step['module_options']['output_directory'])

    items = load_yaml_data(step['module_options']['data_file'])

    set_default_options(step['module_options'])

    for item in items:
        local_archive_dir = get_local_archive_dir(step['module_options']['output_directory'], item)

        # Check if item should be excluded (tags or regex)
        is_excluded, excluded_by_tags, excluded_by_regex = is_item_excluded(item, step['module_options'])

        # Clean excluded items if clean_excluded is True
        if is_excluded:
            handle_excluded_item(item, local_archive_dir, excluded_by_tags, excluded_by_regex,
                               step['module_options'].get('clean_excluded', False))
            skipped_count = skipped_count + 1
        else:
            should_process, reason = should_process_item(item, step['module_options'])

            if should_process:
                logging.info('archiving %s (id %s)', item['url'], item['id'])
                local_archive_path = wget(step, item, local_archive_dir)
                if local_archive_path is not None:
                    item['archive_path'] = local_archive_path
                    downloaded_count = downloaded_count + 1
                    item.pop('archive_error', None)
                else:
                    item['archive_error'] = True
                    error_count = error_count + 1
                write_data_file(step, items)  # Checkpoint after each download
            else:
                if reason == 'already_archived':
                    logging.debug('skipping %s (id %s): already archived', item['url'], item['id'])
                elif reason == 'failed':
                    logging.debug('skipping %s (id %s): the previous archival attempt failed, and skip_failed is set to True', item['url'], item['id'])
                elif reason == 'no_matching_tags':
                    logging.debug('skipping %s (id %s): no tags matching only_tags', item['url'], item['id'])
                skipped_count = skipped_count + 1

    for visibility in ['public', 'private']:
        dirs_list = []
        if visibility == 'public':
            dirs_list = next(os.walk(step['module_options']['output_directory'] + '/public'))
            ids_in_data = [value['id'] for value in items if value['private'] == False]
        elif visibility == 'private':
            dirs_list = next(os.walk(step['module_options']['output_directory'] + '/private'))
            ids_in_data = [value['id'] for value in items if value['private'] == True]
        else:
            logging.error('invalid value for visibility: %s', visibility)
            sys.exit(1)

        for directory in dirs_list[1]:
            if not any(id == int(directory) for id in ids_in_data):
                if step['module_options']['clean_removed']:
                    # TODO if an item was changed from private to public or the other way around, the local archive will be deleted, but it will not be archived again since archive_path is already set
                    logging.info('local webpage archive found with id %s, but not in data. Deleting %s', directory, dirs_list[0] + '/' + directory)
                    shutil.rmtree(dirs_list[0] + '/' + directory)
                else:
                    logging.warning('local webpage archive found with id %s, but not in data. You may want to delete %s manually', directory, dirs_list[0] + '/' + directory)

    logging.info('processing complete. Downloaded: %s - Skipped: %s - Errors %s', downloaded_count, skipped_count, error_count)