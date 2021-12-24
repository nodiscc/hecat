## markdown_singlepage

Generates a single markdown document from YAML data, suitable for [awesome](https://github.com/sindresorhus/awesome) lists.

```bash
hecat export --exporter markdown_singlepage --source-directory /path/to/source/directory --output-directory /path/to/output/directory --output-file README.md --options=authors
```

Output directory structure:

```
/path/to/output/directory/
└── README.md
└── AUTHORS.md
```

Source YAML directory structure:

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
github_last_update: "20200202T20:20:20Z" # optional, auto-generated, last update/commit date for github projects
stargazers_count: "999"  # optional, auto-generated, number of stars for github projects
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
