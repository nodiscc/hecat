# hecat

A catalog generator and management tool.

This program uses YAML files to store data about various kind of items (software projects, bookmarks, movies, ...).
It can then export the data to multiple human-readable formats.

**Status: experimental** ![CI](https://github.com/nodiscc/hecat/actions/workflows/ci.yml/badge.svg)

Input formats:
- [markdown_awesome](hecat/importers/README.md#markdown_awesome) - markdown format from [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted

Processing:
- [github_metdata](hecat/processors/README.md#github_metadata) - add software project metadata from Github.com

Output formats:
- [markdown_singlepage](hecat/exporters/README.md#markdown_singlepage) - single page markdown format for _awesome_ lists

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
    export         export markdown from YAML source files
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

### export a single page markdown list

See [hecat/exporters/README.md](hecat/exporters/README.md#markdown-singlepage)

### Run additional processing

TODO github_metadata

You can then rebuild the site using the `export` command.


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

## Import data from Shaarli

```bash
# install the python API client
python3 -m vev ~/.venv
source ~/.venv/bin/activate
shaarli --insecure get-links --searchtags "video -nodl" --limit 999999|jq '.[].url' | xargs youtube-dl --download-archive youtube-dl.archive.txt --ignore-errors --no-playlist
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
