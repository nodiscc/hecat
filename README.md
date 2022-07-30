# hecat

A catalog generator and management tool.

**Status: experimental** [![CI](https://github.com/nodiscc/hecat/actions/workflows/ci.yml/badge.svg)](https://github.com/nodiscc/hecat/actions)

This program uses YAML files to store data about various kind of items (bookmarks, software projects, ...), and performs various import/export/processing tasks around this storage format through these modules:

- [importers/markdown_awesome](hecat/importers/markdown_awesome.py): import data from the [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) markdown format
- [importers/shaarli_api](hecat/importers//shaarli_api.py): import data from a [Shaarli](https://github.com/shaarli/Shaarli) instance
- [processors/github_metadata](hecat/processors/github_metadata.py): import/update software project metadata from GitHub API
- [processors/awesome_lint](hecat/processors/awesome_lint.py): check data against [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) guidelines
- [processors/download_media](hecat/processors/download_media.py): download video/audio files using [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [exporters/markdown_singlepage](hecat/exporters/markdown_singlepage.py): export data from the [awesome-selfhosted-data](format) to a single markdown document

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
- `name`: arbitrary for this step
- `module`: the module to use, see list of modules above
- `module_options`: a dict of options specific to the module, see list of modules above

```yaml
# .hecat.yml
# $ git clone https://github.com/awesome-selfhosted/awesome-selfhosted
# $ git clone https://github.com/awesome-selfhosted/awesome-selfhosted-data
steps:
  - name: import data from awesome-selfhosted markdown
    module: importers/markdown_awesome
    module_options:
      source_file: awesome-selfhosted/README.md
      output_directory: awesome-selfhosted-data

  - name: update github metadata in awesome-selfhosted data
    module: processors/github_metadata
    module_options:
      source_directory: awesome-selfhosted-data
      gh_metadata_only_missing: True # optional, default False

  - name: check awesome-selfhosted data
    module: processors/awesome_lint
    module_options:
      source_directory: awesome-selfhosted-data

  - name: export awesome-selfhosted markdown
      module: exporters/markdown_singlepage
      module_options:
        source_directory: awesome-selfhosted-data
        output_directory: awesome-selfhosted
        output_file: README.md
        authors_file: AUTHORS.md # optional, default no authors file
```
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
