# hecat

Software catalog generator. Built for [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted).

This program takes YAML data as input, and renders a single-page, _awesome_ markdown list. It will be extended to handle other output formats and input types.

**Status: experimental**


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

To convert a YAML-based list to markdown, your source project/YAML directory must follow this directory structure:

```bash
/path/to/source/directory
├── markdown
│   ├── header.md # markdown footer to render in the final single-page document
│   └── footer.md # markdown header to render in the final single-page document
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
└── tools
```

Files containing software data must be formatted as follows:

```yaml
# software/my-awesome-software.yml
name: "My awesome software" # required
website_url: "https://my.awesome.softwar.e" # required
source_code_url: "https://gitlab.com/awesome/software" # optional
description: "A description of my awesome software." # required
licenses: # required, all licenses must be listed in licenses.yml
  - Apache-2.0
  - AGPL-3.0
platforms: # required, all platforms must be listed in platforms/*.yml
  - Java
  - Python
  - PHP
  - Nodejs
  - Deb
  - Docker
tags: # required, all tags must be listed in tags/*.yml
  - Automation
  - Calendar
  - File synchronization
demo_url: "https://my.awesome.softwar.e/demo" # optional
related_software_url: "https://my.awesome.softwar.e/apps" # optional
depends_3rdparty: yes # optional, default no
```

Files containing platforms/languages must be formatted as follows:

```yaml
name: Document management # required
description: "[Document management systems (DMS)](https://en.wikipedia.org/wiki/Document_management_system) are used to receive, track, manage and store documents and reduce paper" # required, markdown
related_tags: # optional
  - E-books and Integrated Library Systems (ILS)
  - Archiving and Digital Preservation
```

## Configuration

Currently the program takes its configuration from command-line parameters. See [Usage](#usage)

## Usage

```bash
$ hecat --help
usage: hecat [-h] {build} ...

positional arguments:
  {build}
    build     build markdown from YAML source files

optional arguments:
  -h, --help  show this help message and exit
```

```
$ hecat build --help
usage: hecat build [-h] [--exporter {markdown_singlepage}]
                   [--source-directory SOURCE_DIRECTORY]
                   [--output-directory OUTPUT_DIRECTORY]
                   [--output-file OUTPUT_FILE]

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
```

### Build a single page markdown list

```bash
hecat build --exporter markdown_singlepage --source-directory /path/to/source/directory --output-directory /path/to/output/directory --output-file singlepage.md
```

This will generate the following directory structure:

```
/path/to/output/directory/
└── singlepage.md
```


## Support

Please submit any questions to <https://gitlab.com/nodiscc/hecat/-/issues> or <https://github.com/nodiscc/hecat/issues>


## Contributing

This program is at a very ealry stage of development. Code cleanup, documentation, unit tests, improvements, support for other input/output formats is very welcome at <https://gitlab.com/nodiscc/hecat/-/merge_requests> or <https://github.com/nodiscc/hecat/pulls>


## Testing

```bash
# install pyvenv, pip and make
sudo apt install python3-pip python3-venv make
# run automated tests
make test
```

## License

[GNU GPLv3](LICENSE)
