# hecat

A catalog generator and management tool.

**Status: experimental** ![CI](https://github.com/nodiscc/hecat/actions/workflows/ci.yml/badge.svg)

This program uses YAML files to store data about various kind of items (software projects...). It can import data from various sources, run processing tasks on stored data, and export data to multiple human-readable formats:

Importers:
- [markdown_awesome](hecat/importers/README.md#markdown_awesome)

Processors:
- [github_metadata](hecat/processors/README.md#github_metadata)

Exporters:
- [markdown_singlepage](hecat/exporters/README.md#markdown_singlepage)


## Screenshots

[![](https://i.imgur.com/NvCOeiK.png)](hecat/exporters/README.md#markdown_singlepage)
[![](https://i.imgur.com/tMAxhLw.png)](hecat/importers/README.md#markdown_awesome)

## Installation

```bash
# install pyvenv and pip
sudo apt install python3-venv python3-pip
# create a python virtualenv
python3 -m venv ~/.venv
# activate the virtualenv
source ~/.venv/bin/activate
# install the program
pip3 install git+https://gitlab.com/nodiscc/hecat.git
```

If you want to install from a local copy instead:

```bash
# grab a copy
git clone https://gitlab.com/nodiscc/hecat.git
# install the python package
cd hecat && python3 setup.py install
```

## Requirements



## Configuration

The program takes its configuration from command-line parameters. See [Usage](#usage)

## Usage

```bash
$ hecat --help
usage: hecat [-h] {export,import} ...

positional arguments:
  {export,import}
    export        build markdown from YAML source files
    import        import initial data from other formats

optional arguments:
  -h, --help      show this help message and exit
```

```
$  hecat export --help
usage: hecat export [-h] [--exporter {markdown_singlepage}] --source-directory
                   SOURCE_DIRECTORY --output-directory OUTPUT_DIRECTORY
                   --output-file OUTPUT_FILE [--tags-directory TAGS_DIRECTORY]
                   [--software-directory SOFTWARE_DIRECTORY]

optional arguments:
  -h, --help            show this help message and exit
  --exporter {markdown_singlepage}
                        exporter to use
  --source-directory SOURCE_DIRECTORY
                        base directory for YAML data
  --output-directory OUTPUT_DIRECTORY
                        base directory for markdown output
  --output-file OUTPUT_FILE
                        output filename
  --tags-directory TAGS_DIRECTORY
                        source subdirectory for tags definitions
  --software-directory SOFTWARE_DIRECTORY
                        source subdirectory for software definitions

```

```
$ hecat import --help
usage: hecat import [-h] [--importer {markdown_awesome}] --source-file
                    SOURCE_FILE --output-directory OUTPUT_DIRECTORY
                    [--tags-directory TAGS_DIRECTORY]
                    [--software-directory SOFTWARE_DIRECTORY]
                    [--platforms-directory PLATFORMS_DIRECTORY]

optional arguments:
  -h, --help            show this help message and exit
  --importer {markdown_awesome}
                        importer to use
  --source-file SOURCE_FILE
                        input markdown file
  --output-directory OUTPUT_DIRECTORY
                        base directory for YAML output
  --tags-directory TAGS_DIRECTORY
                        destination subdirectory for tags definitions
  --software-directory SOFTWARE_DIRECTORY
                        destination subdirectory for software definitions
  --platforms-directory PLATFORMS_DIRECTORY
                        destination subdirectory for platforms definitions
```

```
$ hecat process --help
usage: hecat process [-h] [--processors PROCESSORS] --source-directory SOURCE_DIRECTORY [--software-directory SOFTWARE_DIRECTORY] [--options OPTIONS]

optional arguments:
  -h, --help            show this help message and exit
  --processors PROCESSORS
                        list of processors to run, comma-separated
  --source-directory SOURCE_DIRECTORY
                        base directory for YAML data
  --software-directory SOFTWARE_DIRECTORY
                        source subdirectory for software definitions
  --options OPTIONS     list of processors options, comma-separated
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
