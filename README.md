# hecat

A generic automation tool around data stored as plaintext YAML files.

**Status: experimental** [![CI](https://github.com/nodiscc/hecat/actions/workflows/ci.yml/badge.svg)](https://github.com/nodiscc/hecat/actions)

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

[![](https://gitlab.com/nodiscc/toolbox/-/raw/master/DOC/SCREENSHOTS/Heg3Esg.png)](hecat/processors/url_check.py)
[![](https://gitlab.com/nodiscc/toolbox/-/raw/master/DOC/SCREENSHOTS/RtiDE91.png)](hecat/processors/download_media.py)


#### Exporters

Export data to other formats:
- [exporters/markdown_singlepage](hecat/exporters/markdown_singlepage.py): export data from the [awesome-selfhosted-data](https://github.com/awesome-selfhosted/awesome-selfhosted-data) format to a single markdown document
- [exporters/html_table](hecat/exporters/html_table.py): render data as single-page HTML table

[![](https://gitlab.com/nodiscc/toolbox/-/raw/master/DOC/SCREENSHOTS/NvCOeiK.png)](hecat/exporters/markdown_singlepage.py)
[![](https://gitlab.com/nodiscc/toolbox/-/raw/master/DOC/SCREENSHOTS/FFMPdaw.png)](hecat/exporters/html_table.py)


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
cd hecat && python3 setup.py install
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

Import data from [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted), apply processing steps, export to single-page markdown again

```yaml
# .hecat.yml
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

  - name: update github projects metadata
    module: processors/github_metadata
    module_options:
      source_directory: awesome-selfhosted-data
      gh_metadata_only_missing: True # optional, default False
      sleep_time: 7.3

  - name: check data against awesome-selfhosted guidelines
    module: processors/awesome_lint
    module_options:
      source_directory: awesome-selfhosted-data

  - name: export YAML data to single-page markdown
    module: exporters/markdown_singlepage
    module_options:
      source_directory: awesome-selfhosted-data # source/YAML data directory
      output_directory: awesome-selfhosted # output directory
      output_file: README.md # output markdown file
      back_to_top_url: '#awesome-selfhosted' # (default #) the URL/anchor to use in 'back to top' links
      exclude_licenses: # (default none) do not write software items with any of these licenses to the output file
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

```

Schedule automatic metadata update every hour from Github Actions:

```yaml
# .github/workflows/update-metadata.yml
on:
  schedule:
    - cron: '22 * * * *'

env:
  GITHUB_TOKEN: ${{secrets.GITHUB_TOKEN}}

jobs:
  test_schedule:
    runs-on: ubuntu-latest
    steps:
      - name: checkout
        uses: actions/checkout@v3
      - name: install hecat
        run: |
          python3 -m venv .venv
          source .venv/bin/activate
          pip3 install wheel
          pip3 install --force git+https://github.com/nodiscc/hecat.git@master
      - name: update all metadata from Github API
        run: source .venv/bin/activate && hecat --config .hecat.update_metadata.yml
      - name: commit and push changes
        run: |
          git config user.name awesome-selfhosted-bot
          git config user.email github-actions@github.com
          git add software/ tags/ platforms/ licenses*.yml
          git diff-index --quiet HEAD || git commit -m "[bot] update projects metadata"
          git push
```

```yaml
# .hecat.update_metadata.yml
steps:
  - name: update all metadata from Github API
    module: processors/github_metadata
    module_options:
      source_directory: ./
      gh_metadata_only_missing: False
```


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

  - name: export shaarli data to HTML table
    module: exporters/html_table
    module_options:
      source_file: shaarli.yml # file from which data will be loaded
      output_file: index.html # (default index.html) output HTML table file
      html_title: "Shaarli export - shaarli.example.org" # (default "hecat HTML export") output HTML title
      description_format: paragraph # (details/paragraph, default details) wrap the description in a HTML details tag
```

[ffmpeg](https://ffmpeg.org/) must be installed for audio/video conversion support. [jdupes](https://github.com/jbruchon/jdupes), [soundalike](https://github.com/derat/soundalike) and [videoduplicatefinder](https://github.com/0x90d/videoduplicatefinder) may further help dealing with duplicate files and media.


## Support

Please submit any questions to <https://gitlab.com/nodiscc/hecat/-/issues> or <https://github.com/nodiscc/hecat/issues>


## Contributing

This program is in a very early stage of development. Code cleanup, documentation, unit tests, improvements, support for other input/output formats is very welcome at <https://gitlab.com/nodiscc/hecat/-/merge_requests> or <https://github.com/nodiscc/hecat/pulls>


## Testing

```bash
# install pyvenv, pip and make
sudo apt install python3-pip python3-venv make
# run automated tests
make clean test_run
```

## License

[GNU GPLv3](LICENSE)
