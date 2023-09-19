# Change Log

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](http://keepachangelog.com/).

#### [v1.1.2](https://github.com/nodiscc/hecat/releases/tag/1.1.2) - UNRELEASED

**Changed:**
- processors/awesome_lint: if `items_in_redirect_fatal: True` (the default), exit with error if any `software` item uses a tag for which `redirect:` is not empty
- processors/awesome_lint: always fail if any `tag` item has less than 3 `software` items referencing it
- processors/awesome_lint: run checks on `tag` items before checks on `software` items

**Fixed:**
- processors/awesome_lint: fix detection of `redirect` attribute when a tag has least than N items
- processors/awesome_lint: don't error if a tag with the redirect attribute has 0 matching `software` items
- exporters/markdown_multipage: render Demo link for `software` items where `demo_url` is set

---------------------


#### [v1.1.1](https://github.com/nodiscc/hecat/releases/tag/1.1.1) - 2023-08-19

**Fixed:**
- processors/awesome_lint: fix displayed number of days in `older than ... days` for error-level messages
- processors/github_metadata: don't split long lines in YAML output

---------------------

#### [v1.1.0](https://github.com/nodiscc/hecat/releases/tag/1.1.0) - 2023-07-29

**Added:**
- processors/awesome_lint: allow confguring the number of days without updates to a project before triggering an info/warning/error message (`last_updated_{error,warn,info}_days`, default to 3650, 365, 186 respectively)

---------------------

#### [v1.0.2](https://github.com/nodiscc/hecat/releases/tag/1.0.2) - 2023-07-27

**Changed:**
- dependencies: upgrade sphinx to v7.1.0, pin furo to v2023.7.26

**Fixed:**
- doc/tests: don't use deprecated `python3 setup.py install`, use `python3 -m pip install .`
- dependencies: install sphinx through `install_requires`, separate manual installation step is no longer required

---------------------

#### [v1.0.1](https://github.com/nodiscc/hecat/releases/tag/1.0.1) - 2023-07-24

**Changed:**
- utils: `to_kebab_case()`: replace `:` character with `-` (avoids filename issues on NTFS, consistent with automatic anchor generation)

---------------------

#### [v1.0.0](https://github.com/nodiscc/hecat/releases/tag/1.0.0) - 2023-07-24

Initial release, see [README.md](https://github.com/nodiscc/hecat/blob/1.0.0/README.md) and module-specific documentation in each module's docstring.
