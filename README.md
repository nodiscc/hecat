# hecat

A generic automation tool around data stored as plaintext YAML files.

[![CI](https://github.com/nodiscc/hecat/actions/workflows/ci.yml/badge.svg)](https://github.com/nodiscc/hecat/actions)

This program uses YAML files to store data about various kind of items (bookmarks, software projects, ...) and apply various processing tasks.
Functionality is implemented in separate modules.

### Importers

Import data from various input formats:

- [importers/markdown_awesome](hecat/importers/markdown_awesome.py): import data from the [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) markdown format
- [importers/shaarli_api](hecat/importers//shaarli_api.py): import data from a [Shaarli](https://github.com/shaarli/Shaarli) instance using the [API](https://shaarli.github.io/api-documentation/)

[![](https://gitlab.com/nodiscc/toolbox/-/raw/master/DOC/SCREENSHOTS/tMAxhLw.png)](hecat/importers/markdown_awesome.py)


### Processors

Perform processing tasks on YAML data:

- [processors/github_metadata](hecat/processors/github_metadata.py): enrich software project metadata from GitHub API (stars, last commit date...)
- [processors/awesome_lint](hecat/processors/awesome_lint.py): check data against [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) consistency/completeness guidelines
- [processors/download_media](hecat/processors/download_media.py): download video/audio files using [yt-dlp](https://github.com/yt-dlp/yt-dlp) for bookmarks imported from Shaarli
- [processors/url_check](hecat/processors/url_check.py): check data for dead links
- [processors/archive_webpages](hecat/processors/archive_webpages.py): archive webpages locally

[![](https://gitlab.com/nodiscc/toolbox/-/raw/master/DOC/SCREENSHOTS/Heg3Esg.png)](hecat/processors/url_check.py)
[![](https://gitlab.com/nodiscc/toolbox/-/raw/master/DOC/SCREENSHOTS/RtiDE91.png)](hecat/processors/download_media.py)
[![](https://gitlab.com/nodiscc/toolbox/-/raw/master/DOC/SCREENSHOTS/hecat-processor-github-metadata.png)](hecat/processors/github_metadata.py)

#### Exporters

Export data to other formats:
- [exporters/markdown_singlepage](hecat/exporters/markdown_singlepage.py): render data as a single markdown document
- [exporters/markdown_multipage](hecat/exporters/markdown_multipage.py): render data as a multipage markdown site which can be used to generate a HTML site with Sphinx
- [exporters/html_table](hecat/exporters/html_table.py): render data as single-page HTML table

[![](https://gitlab.com/nodiscc/toolbox/-/raw/master/DOC/SCREENSHOTS/NvCOeiK.png)](hecat/exporters/markdown_singlepage.py)
[![](https://gitlab.com/nodiscc/toolbox/-/raw/master/DOC/SCREENSHOTS/FFMPdaw.png)](hecat/exporters/html_table.py)
[![](https://gitlab.com/nodiscc/toolbox/-/raw/master/DOC/SCREENSHOTS/hecat-exporter-markdown-multipage.png)](hecat/exporters/markdown_multipage.py)


## Installation

```bash
# install requirements
sudo apt install python3-venv python3-pip
# create a python virtualenv
python3 -m venv ~/.venv
# activate the virtualenv
source ~/.venv/bin/activate
# install the program
pip3 install git+https://gitlab.com/nodiscc/hecat.git
```

To install from a local copy instead:

```bash
# grab a copy
git clone https://gitlab.com/nodiscc/hecat.git
# install the python package
cd hecat && python3 -m pip install .
```

To install a specific [release](https://github.com/nodiscc/hecat/releases), adapt the `git clone` or `pip3 install` command:

```bash
pip3 install git+https://gitlab.com/nodiscc/hecat.git@1.0.2
git clone -b 1.0.2 https://gitlab.com/nodiscc/hecat.git
```

## Usage

```bash
$ hecat --help
usage: hecat [-h] [--config CONFIG_FILE] [--log-level {ERROR,WARNING,INFO,DEBUG}]

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG_FILE  configuration file (default .hecat.yml)
  --log-level {ERROR,WARNING,INFO,DEBUG} log level (default INFO)
  --log-file LOG_FILE   log file (default none)
```

If no configuration file is specified, configuration is read from `.hecat.yml` in the current directory.


## Configuration

hecat executes all steps defined in the configuration file. For each step:

```yaml
steps:
  - name: example step # arbitrary name for this step
    module: processor/example # the module to use, see list of modules above
    module_options: # a dict of options specific to the module, see list of modules above
      option1: True
      option2: some_value
```

### Examples

#### Awesome lists

Import data from [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted)'s markdown list format:

```yaml
# .hecat.import.yml
# $ git clone https://github.com/awesome-selfhosted/awesome-selfhosted
# $ git clone https://github.com/awesome-selfhosted/awesome-selfhosted-data
steps:
  - name: import awesome-selfhosted README.md to YAML
    module: importers/markdown_awesome
    module_options:
      source_file: awesome-selfhosted/README.md
      output_directory: ./
      output_licenses_file: licenses.yml # optional, default licenses.yml
      overwrite_tags: False # optional, default False
```

Check data against awesome-selfhosted formatting guidelines, export to single page markdown and static HTML site (see [awesome-selfhosted-data](https://github.com/awesome-selfhosted/awesome-selfhosted-data), its [`Makefile`](https://github.com/awesome-selfhosted/awesome-selfhosted-data/blob/master/Makefile) and [Github Actions workflows](https://github.com/awesome-selfhosted/awesome-selfhosted-data/tree/master/.github/workflows) for complete usage examples. See [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) and [awesome-selfhosted-html](https://github.com/nodiscc/awesome-selfhosted-html-preview/) for example output):

```yaml
# .hecat.export.yml
steps:
  - name: check data against awesome-selfhosted guidelines
    module: processors/awesome_lint
    module_options:
      source_directory: awesome-selfhosted-data
      licenses_files:
        - licenses.yml
        - licenses-nonfree.yml

  - name: export YAML data to single-page markdown
    module: exporters/markdown_singlepage
    module_options:
      source_directory: awesome-selfhosted-data # source/YAML data directory
      output_directory: awesome-selfhosted # output directory
      output_file: README.md # output markdown file
      markdown_header: markdown/header.md # (optional, default none) path to markdown file to use as header (relative to source_directory)
      markdown_footer: markdown/footer.md # (optional, default none) path to markdown file to use as footer (relative to source_directory)
      back_to_top_url: '#awesome-selfhosted' # (optional, default #) the URL/anchor to use in 'back to top' links
      exclude_licenses: # (optional, default none) do not write software items with any of these licenses to the output file
        - '⊘ Proprietary'
        - 'BUSL-1.1'
        - 'CC-BY-NC-4.0'
        - 'CC-BY-NC-SA-3.0'
        - 'CC-BY-ND-3.0'
        - 'Commons-Clause'
        - 'DPL'
        - 'SSPL-1.0'
        - 'DPL'
        - 'Elastic-1.0'
        - 'Elastic-2.0'

  - name: export YAML data to single-page markdown (non-free.md)
    module: exporters/markdown_singlepage
    module_options:
      source_directory: awesome-selfhosted-data
      output_directory: awesome-selfhosted
      output_file: non-free.md
      markdown_header: markdown/non-free-header.md
      licenses_file: licenses-nonfree.yml # (optional, default licenses.yml) YAML file to load licenses from
      back_to_top_url: '##awesome-selfhosted---non-free-software'
      render_empty_categories: False # (optional, default True) do not render categories which contain 0 items
      render_category_headers: False # (optional, default True) do not render category headers (description, related categories, external links...)
      include_licenses: # (optional, default none) only render items matching at least one of these licenses (cannot be used together with exclude_licenses) (by identifier)
        - '⊘ Proprietary'
        - 'BUSL-1.1'
        - 'CC-BY-NC-4.0'
        - 'CC-BY-NC-SA-3.0'
        - 'CC-BY-ND-3.0'
        - 'Commons-Clause'
        - 'DPL'
        - 'SSPL-1.0'
        - 'DPL'
        - 'Elastic-1.0'
        - 'Elastic-2.0'

  - name: export YAML data to multi-page markdown/HTML site
    module: exporters/markdown_multipage
    module_options:
      source_directory: awesome-selfhosted-data # directory containing YAML data
      output_directory: awesome-selfhosted-html # directory to write markdown pages to
      exclude_licenses: # optional, default []
        - '⊘ Proprietary'
        - 'BUSL-1.1'
        - 'CC-BY-NC-4.0'
        - 'CC-BY-NC-SA-3.0'
        - 'CC-BY-ND-3.0'
        - 'Commons-Clause'
        - 'DPL'
        - 'SSPL-1.0'
        - 'DPL'
        - 'Elastic-1.0'
        - 'Elastic-2.0'

# $ sphinx-build -b html -c awesome-selfhosted-data/ awesome-selfhosted-html/md/ awesome-selfhosted-html/html/
# $ rm -r tests/awesome-selfhosted-html/html/.buildinfo tests/awesome-selfhosted-html/html/objects.inv awesome-selfhosted-html/html/.doctrees
```

<details><summary>Example automation using Github actions:</summary>

```yaml
# .github/workflows/build.yml
jobs:
  build-markdown:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          ref: ${{ github.ref }}
      - run: python3 -m venv .venv && source .venv/bin/activate && pip3 install wheel && pip3 install --force git+https://github.com/nodiscc/hecat.git@1.2.0
      - run: source .venv/bin/activate && hecat --config .hecat/awesome-lint.yml
      - run: source .venv/bin/activate && hecat --config .hecat/export-markdown.yml

  build-html:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          ref: ${{ github.ref }}
      - run: python3 -m venv .venv && source .venv/bin/activate && pip3 install wheel && pip3 install --force git+https://github.com/nodiscc/hecat.git@1.2.0
      - run: source .venv/bin/activate && hecat --config .hecat/awesome-lint.yml
      - run: source .venv/bin/activate && hecat --config .hecat/export-html.yml
```
</details>

Update metadata before rebuilding HTML/markdown output:

```yaml
# .hecat.update_metadata.yml
steps:
  - name: update github projects metadata
    module: processors/github_metadata
    module_options:
      source_directory: awesome-selfhosted-data # directory containing YAML data and software subdirectory
      gh_metadata_only_missing: True # (default False) only gather metadata for software entries in which one of stargazers_count,updated_at, archived is missing
      sleep_time: 7.3 # (default 0) sleep for this amount of time before each request to Github API
```

<details><summary>Example automation using Github actions:</summary>

```yaml
# .github/workflows/update-metadata.yml
name: update metadata
on:
  schedule:
    - cron: '22 22 * * *'
  workflow_dispatch:

env:
  GITHUB_TOKEN: ${{secrets.GITHUB_TOKEN}}

concurrency:
  group: update-metadata-${{ github.ref }}
  cancel-in-progress: true

jobs:
  update-metadata:
    if: github.repository == 'awesome-selfhosted/awesome-selfhosted-data'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: python3 -m venv .venv && source .venv/bin/activate && pip3 install wheel && pip3 install --force git+https://github.com/nodiscc/hecat.git@1.2.0
      - run: source .venv/bin/activate && hecat --config .hecat/update-metadata.yml
      - name: commit and push changes
        run: |
          git config user.name awesome-selfhosted-bot
          git config user.email github-actions@github.com
          git add software/ tags/ platforms/ licenses*.yml
          git diff-index --quiet HEAD || git commit -m "[bot] update projects metadata"
          git push
  build:
    if: github.repository == 'awesome-selfhosted/awesome-selfhosted-data'
    needs: update-metadata
    uses: ./.github/workflows/build.yml
    secrets: inherit
```

</details>


Check URLs for dead links:

```yaml
# .hecat.url_check.yml
steps:
  - name: check URLs
    module: processors/url_check
    module_options:
      source_directories:
        - awesome-selfhosted-data/software
        - awesome-selfhosted-data/tags
      source_files:
        - awesome-selfhosted-data/licenses.yml
      errors_are_fatal: True
      exclude_regex:
        - '^https://github.com/[\w\.\-]+/[\w\.\-]+$' # don't check URLs that will be processed by the github_metadata module
        - '^https://retrospring.net/$' # DDoS protection page, always returns 403
        - '^https://www.taiga.io/$' # always returns 403 Request forbidden by administrative rules
        - '^https://docs.paperless-ngx.com/$' # DDoS protection page, always returns 403
        - '^https://demo.paperless-ngx.com/$' # DDoS protection page, always returns 403
        - '^https://git.dotclear.org/dev/dotclear$' # DDoS protection page, always returns 403
        - '^https://word-mastermind.glitch.me/$' # the demo instance takes a long time to spin up, times out with the default 10s timeout
        - '^https://getgrist.com/$' # hecat/python-requests bug? 'Received response with content-encoding: gzip,br, but failed to decode it.'
        - '^https://www.uvdesk.com/$' # DDoS protection page, always returns 403
        - '^https://demo.uvdesk.com/$' # DDoS protection page, always returns 403
        - '^https://notes.orga.cat/$' # DDoS protection page, always returns 403
        - '^https://cytu.be$' # DDoS protection page, always returns 403
        - '^https://demo.reservo.co/$' # hecat/python-requests bug? always returns 404 but the website works in a browser
        - '^https://crates.io/crates/vigil-server$' # hecat/python-requests bug? always returns 404 but the website works in a browser
        - '^https://nitter.net$' # always times out from github actions but the website works in a browser
```

<details><summary>Example automation using Github actions:</summary>

```yaml
# .github/workflows/url-check.yml
name: dead links

on:
  schedule:
    - cron: '22 22 * * *'
  workflow_dispatch:

env:
  GITHUB_TOKEN: ${{secrets.GITHUB_TOKEN}}

concurrency:
  group: dead-links-${{ github.ref }}
  cancel-in-progress: true

jobs:
  check-dead-links:
    if: github.repository == 'awesome-selfhosted/awesome-selfhosted-data'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: python3 -m venv .venv && source .venv/bin/activate && pip3 install wheel && pip3 install --force git+https://github.com/nodiscc/hecat.git@1.2.0
      - run: source .venv/bin/activate && hecat --config .hecat/url-check.yml
```

</details>

#### Shaarli

Import data from a Shaarli instance, download video/audio files identified by specific tags, check for dead links, export to single-page HTML page/table:

```bash
# hecat consumes output from https://github.com/shaarli/python-shaarli-client
# install the python API client
python3 -m venv .venv && source .venv/bin/activate && pip3 install shaarli-client
# edit python-shaarli-client configuration file
mkdir -p ~/.config/shaarli/ && nano ~/.config/shaarli/client.ini
```
```ini
# ~/.config/shaarli/client.ini
[shaarli]
url = https://links.example.org
secret = AAAbbbZZZvvvSSStttUUUvvVXYZ
```
```bash
# download data from your shaarli instance
shaarli --outfile /path/to/shaarli-export.json get-links --limit=all
```
```yaml
# .hecat.yml
steps:
  - name: import data from shaarli API JSON
      module: importers/shaarli_api
      module_options:
        source_file: /path/to/shaarli-export.json
        output_file: shaarli.yml
        skip_existing: True # (default True) skip importing items whose 'url:' already exists in the output file
        clean_removed: False # (default False) remove items from the output file, whose 'url:' was not found in the input file
        sort_by: created # (default 'created') key by which to sort the output list
        sort_reverse: True # (default True) sort the output list in reverse order

  - name: download video files
      module: processors/download_media
      module_options:
        data_file: shaarli.yml # path to the YAML data file
        only_tags: ['video'] # only download items tagged with all these tags
        exclude_tags: ['nodl'] # (default []), don't download items tagged with any of these tags
        output_directory: '/path/to/video/directory' # path to the output directory for media files
        download_playlists: False # (default False) download playlists
        skip_when_filename_present: True # (default True) skip processing when item already has a 'video_filename/audio_filename': key
        retry_items_with_error: True # (default True) retry downloading items for which an error was previously recorded
        use_download_archive: True # (default True) use a yt-dlp archive file to record downloaded items, skip them if already downloaded

  - name: download audio files
    module: processors/download_media
    module_options:
      data_file: shaarli.yml
      only_tags: ['music']
      exclude_tags: ['nodl']
      output_directory: '/path/to/audio/directory'
      only_audio: True # (default False) download the 'bestaudio' format instead of the default 'best'

  - name: check URLs
    module: processors/url_check
    module_options:
      source_files:
        - shaarli.yml
      check_keys:
        - url
      errors_are_fatal: True
      exclude_regex:
        - '^https://www.youtube.com/watch.*$' # don't check youtube video URLs, always returns HTTP 200 even for unavailable videos```

  - name: archive webpages for items tagged 'hecat' or 'doc'
    module: processors/archive_webpages
    module_options:
      data_file: shaarli.yml
      only_tags: ['hecat', 'doc']
      exclude_tags: ['nodl']
      exclude_regex:
        - '^https://[a-z]\.wikipedia.org/wiki/.*$' # don't archive wikipedia pages, we have a local copy of wikipedia dumps from https://dumps.wikimedia.org/
      output_directory: webpages
      clean_removed: True
      clean_excluded: True

  - name: export shaarli data to HTML table
    module: exporters/html_table
    module_options:
      source_file: shaarli.yml # file from which data will be loaded
      output_file: index.html # (default index.html) output HTML table file
      html_title: "Shaarli export - shaarli.example.org" # (default "hecat HTML export") output HTML title
      description_format: paragraph # (details/paragraph, default details) wrap the description in a HTML details tag
```

[ffmpeg](https://ffmpeg.org/) must be installed for audio/video conversion support. [jdupes](https://github.com/jbruchon/jdupes), [soundalike](https://github.com/derat/soundalike) and [videoduplicatefinder](https://github.com/0x90d/videoduplicatefinder) may further help dealing with duplicate files and media.

[yq](https://github.com/kislyuk/yq) can be used to manipulate YAML data produced/used by hecat. For example, to remove the `archive_path` key/value of all items that have one of their tags with a value of `cuisine` from a shaarli export:

```bash
# DOES NOT WORK, INFINITE LOOP (reverse-i-search)`del': yq --yaml-output -s '.[] | select(.[].tags[] == "cuisine") | del(.[].archive_path)' Nextcloud/data/shaarli.yml > shaarli.yml.new

```

## Support

Please submit any questions to <https://gitlab.com/nodiscc/hecat/-/issues> or <https://github.com/nodiscc/hecat/issues>


## Contributing

Bug reports, suggestions, code cleanup, documentation, tests, improvements, support for other input/output formats are welcome at <https://gitlab.com/nodiscc/hecat/-/merge_requests> or <https://github.com/nodiscc/hecat/pulls>


## Testing

```bash
# install pyvenv, pip and make
$ sudo apt install python3-pip python3-venv make
# run tests using the Makefile
$ make help 
USAGE: make TARGET
Available targets:
help                generate list of targets with descriptions
clean               clean files generated by make install/test_run
install             install in a virtualenv
test                run tests
test_short          run tests except those that consume github API requests/long URL checks
test_pylint         run linter (non blocking)
clone_awesome_selfhosted                clone awesome-selfhosted/awesome-selfhosted-data
test_import_awesome_selfhosted          test import from awesome-sefhosted
test_process_awesome_selfhosted         test all processing steps on awesome-selfhosted-data
test_url_check      test URL checker on awesome-sefhosted-data
test_update_github_metadata             test github metadata updater/processor on awesome-selfhosted-data
test_awesome_lint   test linter/compliance checker on awesome-sefhosted-data
test_export_awesome_selfhosted_md       test export to singlepage markdown from awesome-selfhosted-data
test_export_awesome_selfhosted_html     test export to singlepage HTML from awesome-selfhosted-data
test_import_shaarli test import from shaarli JSON
test_download_video test downloading videos from the shaarli import, test log file creation
test_download_audio test downloading audio files from the shaarli import
test_archive_webpages                   test webpage archiving
test_export_html_table                  test exporting shaarli data to HTML table
scan_trivy          run trivy vulnerability scanner
```

## License

[GNU GPLv3](LICENSE)
