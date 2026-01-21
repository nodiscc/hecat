"""import data from github-stars-backup output
- https://gitlab.com/nodiscc/github-stars-backup

# python3 -m venv .venv && source .venv/bin/activate && pip3 install PyGithub
# git clone https://gitlab.com/nodiscc/github-stars-backup && cd github-stars-backup
# export GITHUB_ACCESS_TOKEN=aaaabbbbccccddddeeefffggghhhiijjj
# ./github-stars-backup.py USERNAME ~/github-stars-backup.json && cd ..
# $ cat hecat.yml
steps:
  - name: import data from github-stars-backup
    module: importers/github_stars_backup
    module_options:
      source_file: github-stars-backup/github-stars-backup.json
      output_file: github-stars-backup.yml

Source directory structure:
└── github-stars-backup.json

Output directory structure:
└── github-stars-backup.yml
"""

import os
import logging
import json
import ruamel.yaml
from ..utils import load_yaml_data

yaml = ruamel.yaml.YAML()
yaml.indent(sequence=2, offset=0)
yaml.width = 99999

def import_github_stars_backup_json(step):
    """Import data from the JSON output of Shaarli API"""
    with open(step['module_options']['source_file'], 'r', encoding="utf-8") as json_file:
        new_data = json.load(json_file)
    data_as_list = list(new_data.values())
    with open(step['module_options']['output_file'], 'w+', encoding="utf-8") as yaml_file:
        logging.debug('writing file %s', step['module_options']['output_file'])
        yaml.dump(data_as_list, yaml_file)
