"""import data from a Shaarli instance using output from the API
- https://github.com/shaarli/Shaarli
- https://github.com/shaarli/python-shaarli-client/
- https://shaarli.github.io/api-documentation/

# $ python3 -m venv .venv && source .venv/bin/activate && pip3 install shaarli-client && shaarli get-links --limit=all >| shaarli.json
# $ cat hecat.yml
steps:
  - name: import_shaarli
    module: importers/shaarli_api
    module_options:
      source_file: shaarli.json
      output_file: shaarli.yml
      skip_existing: True # optional, default True, skip importing items whose 'url:' already exists in the output file

Source directory structure:
└── shaarli.json

Output directory structure:
└── shaarli.yml
"""

import os
import logging
import ruamel.yaml
import json
from ..utils import load_yaml_data

yaml = ruamel.yaml.YAML()
yaml.indent(sequence=2, offset=0)

def import_shaarli_json(step):
    """Import data from the JSON output of Shaarli API"""
    if 'skip_existing' not in step['module_options']:
        step['module_options']['skip_existing'] = True
    with open(step['module_options']['source_file'], 'r', encoding="utf-8") as json_file:
        data = json.load(json_file)
    if os.path.exists(step['module_options']['output_file']) and step['module_options']['skip_existing']:
        logging.info('loading existing data from %s', step['module_options']['output_file'])
        previous_data = load_yaml_data(step['module_options']['output_file'])
        final_data = sorted({x["url"]: x for x in (data + previous_data)}.values(), key=lambda x: x["url"])
        with open(step['module_options']['output_file'], 'w+', encoding="utf-8") as yaml_file:
            logging.debug('writing file %s', step['module_options']['output_file'])
            yaml.dump(final_data, yaml_file)
    else:
        with open(step['module_options']['output_file'], 'w+', encoding="utf-8") as yaml_file:
            logging.debug('writing file %s', step['module_options']['output_file'])
            yaml.dump(data, yaml_file)
