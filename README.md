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



## Configuration

Currently the program takes its configuration from command-line parameters. See [Usage](#usage)

## Usage

```bash
$ hecat --help
usage: hecat [-h] {build,import} ...

positional arguments:
  {build,import}
    build         build markdown from YAML source files
    import        import initial data from other formats

optional arguments:
  -h, --help      show this help message and exit
```

```
$  hecat build --help
usage: hecat build [-h] [--exporter {markdown_singlepage}] --source-directory
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

### Build a single page markdown list

```bash
hecat build --exporter markdown_singlepage --source-directory /path/to/source/directory --output-directory /path/to/output/directory --output-file README.md
```

Will generate a single markdown document from YAML data.

```
/path/to/output/directory/
└── singlepage.md
└── AUTHORS.md
```

Your source/YAML directory must follow this structure:

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
delegate: # optional
  - https://another.awesome.li.st
  - https://gitlab.com/user/awesome-list
```

AUTHORS.md will be generated from the `git shortlog` of your source directory.


### Import data from an awesome list

```bash
hecat import --importer markdown_awesome --source-file /path/to/awesome/README.md --output-directory /path/to/output/yaml/data/directory
```

Will generate YAML data from a single-page, _awesome_ markdown list. The importer assumes a few things about the original markdown file:
- all level 3 (`###`) titles/sections contain the actual list data/items, other sections must use level 2 headings
- the list of licenses is available in a `## List of Licenses` section


Destination directories for tags/software/platforms must exist. 

If the source/destination directories are `git` repositories, and you want to import the original authors/committers list (`git log`) to the destination directory, you must do so manually. This will let `hecat` generate an `AUTHORS.md` retaining all contributors from the original repo:

```bash
SOURCE_REPO=../awesome-selfhosted
DEST_REPO=../awesome-selfhosted-data
# copy the orignal .mailmap to the new repository
cp $SOURCE_REPO/.github/.mailmap $DEST_REPO/.mailmap
# place the .mailmap at the standard location in the source repository
cp $SOURCE_REPO/.github/.mailmap $SOURCE_REPO/.mailmap
# generate a git log to use as a template for the new' "dummy" commit log
git -C $SOURCE_REPO log --reverse --format="%ai;%aN;%aE;%s" | tee -a history.log
# create an orphan branch in the target repository, to hold all dummy commits
git -C $DEST_REPO checkout --orphan import-git-history
# create a dummy/empty commit for each commit in the original log (preserving author and date)
cat history.log | while read -r line; do date=$(echo "$line" | awk -F';' '{print $1}'); author=$(echo "$line" | awk -F';' '{print $2}'); email=$(echo "$line" | awk -F';' '{print $3}'); message=$(echo "$line" | awk -F';' '{print $4}'); git -C $DEST_REPO commit --allow-empty --author="$author <$email>" --date="$date" --message="$message"; done
# merge the orphan branch/dummy commit history to your main branch
git -c $DEST_REPO checkout master
git -c $DEST_REPO merge --allow-unrelated-histories import-git-history
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
make test
```

## License

[GNU GPLv3](LICENSE)
