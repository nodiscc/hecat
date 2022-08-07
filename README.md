# hecat

A generic automation tool around data stored as plaintext YAML files.

**Status: experimental** [![CI](https://github.com/nodiscc/hecat/actions/workflows/ci.yml/badge.svg)](https://github.com/nodiscc/hecat/actions)

This program uses YAML files to store data about various kind of items (bookmarks, software projects, ...). It is able to import data from various input formats, perform processing tasks (enrich data, run consistency checks...), and export data to other formats.

## Modules

- [importers/markdown_awesome](hecat/importers/markdown_awesome.py): import data from the [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) markdown format
- [importers/shaarli_api](hecat/importers//shaarli_api.py): import data from a [Shaarli](https://github.com/shaarli/Shaarli) instance using the [API](https://shaarli.github.io/api-documentation/)
- [processors/github_metadata](hecat/processors/github_metadata.py): enrich software project metadata from GitHub API (stars, last commit date...)
- [processors/awesome_lint](hecat/processors/awesome_lint.py): check data against [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) consistency/completeness guidelines
- [processors/download_media](hecat/processors/download_media.py): download video/audio files using [yt-dlp](https://github.com/yt-dlp/yt-dlp) for bookmarks imported from Shaarli
- [exporters/markdown_singlepage](hecat/exporters/markdown_singlepage.py): export data from the [awesome-selfhosted-data](https://github.com/awesome-selfhosted/awesome-selfhosted-data) format to a single markdown document

[![](https://i.imgur.com/NvCOeiK.png)](hecat/exporters/markdown_singlepage.py)
[![](https://i.imgur.com/tMAxhLw.png)](hecat/importers/markdown_awesome.py)

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
usage: hecat [-h] [--config CONFIG_FILE]

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG_FILE  configuration file
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

  - name: update github metadata in awesome-selfhosted data
    module: processors/github_metadata
    module_options:
      source_directory: awesome-selfhosted-data
      gh_metadata_only_missing: True # optional, default False

  - name: check awesome-selfhosted data
    module: processors/awesome_lint
    module_options:
      source_directory: awesome-selfhosted-data

  - step: export YAML data to single-page markdown
    module: exporters/markdown_singlepage
    module_options:
      source_directory: awesome-selfhosted-data
      output_directory: awesome-selfhosted
      output_file: README.md
      authors_file: AUTHORS.md # optional, default no authors file
      exclude_licenses: # optional, default []
        - 'CC-BY-NC-4.0'
        - '⊘ Proprietary'
        - 'SSPL-1.0'
```

Import data from a Shaarli instance, download video/audio files identified by specific tags:

```yaml
# .hecat.yml
# $ python3 -m venv .venv && source .venv/bin/activate && pip3 install shaarli-client
# $ mkdir -p ~/.config/shaarli/ && nano ~/.config/shaarli/client.ini
# $ shaarli get-links --limit=all >| tests/shaarli.json
  - name: import data shaarli from shaarli API JSON
    module: importers/shaarli_api
    module_options:
      source_file: tests/shaarli.json
      output_file: tests/shaarli.yml

  - name: download video files
    module: processors/download_media
    module_options:
      data_file: tests/shaarli.yml
      only_tags: ['video']
      exclude_tags: ['nodl'] # optional, don't download items tagged with any of these tags
      output_directory: 'tests/video'
      download_playlists: False # optional, default False
      skip_when_filename_present: False # optional, default False
      retry_items_with_error: True # optional, default True

  - name: download audio files
    module: processors/download_media
    module_options:
      data_file: tests/shaarli.yml
      only_tags: ['music']
      exclude_tags: ['nodl']
      output_directory: 'tests/audio'
      only_audio: True

```

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
