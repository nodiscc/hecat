# hecat

A catalog generator and management tool.

**Status: experimental** [![CI](https://github.com/nodiscc/hecat/actions/workflows/ci.yml/badge.svg)](https://github.com/nodiscc/hecat/actions)

This program uses YAML files to store data about various kind of items (bookmarks, software projects, ...), and performs various import/export/processing tasks around this storage format through these modules:

- [importers/markdown_awesome](hecat/importers/markdown_awesome.py): import data from the awesome-selfhosted markdown format
- [processors/github_metadata](hecat/processors/github_metadata.py): import/update software project metadata from GitHub API
- [processors/awesome_lint](hecat/processors/awesome_lint.py): check all software entries against awesome-selfhosted formatting guidelines
- [exporters/markdown_singlepage](hecat/exporters/markdown_singlepage.py): export data to single markdown document suitable for "awesome" lists
- [exporters/markdown_authors](hecat/exporters/markdown_authors.py)

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
- `module_options`: a dict of options specific to the module, see module list above

```yaml
steps:
  - name: import
    module: importers/markdown_awesome
    module_options:
      source_file: awesome-selfhosted/README.md
      output_directory: awesome-selfhosted-data

  - name: update_github_metadata
    module: processors/github_metadata
    module_options:
      source_directory: awesome-selfhosted-data
      gh_metadata_only_missing: True # optional, default False

  - name: lint
    module: processors/awesome_lint
    module_options:
      source_directory: awesome-selfhosted-data

  - name: export_markdown
      module: exporters/markdown_singlepage
      module_options:
        source_directory: awesome-selfhosted-data
        output_directory: awesome-selfhosted
        output_file: README.md
        authors_file: AUTHORS.md # optional, default no authors file
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
