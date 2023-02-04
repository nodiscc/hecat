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
      skip_existing: True # (default True) skip importing items whose 'url:' already exists in the output file
      clean_removed: False # (default False) remove items from the output file, whose 'url:' was not found in the input file

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
yaml.width = 99999

def import_shaarli_json(step):
    """Import data from the JSON output of Shaarli API"""
    if 'skip_existing' not in step['module_options']:
        step['module_options']['skip_existing'] = True
    if 'clean_removed' not in step['module_options']:
        step['module_options']['clean_removed'] = False
    with open(step['module_options']['source_file'], 'r', encoding="utf-8") as json_file:
        new_data = json.load(json_file)
    if os.path.exists(step['module_options']['output_file']) and step['module_options']['skip_existing']:
        logging.info('loading existing data from %s', step['module_options']['output_file'])
        previous_data = load_yaml_data(step['module_options']['output_file'])
        final_data = sorted({x["url"]: x for x in (new_data + previous_data)}.values(), key=lambda x: x["url"])
        with open(step['module_options']['output_file'], 'w+', encoding="utf-8") as yaml_file:
            logging.info('writing file %s', step['module_options']['output_file'])
            yaml.dump(final_data, yaml_file)
        logging.info('checking for URLs that are present in the output file, but not in the source file')
        items_were_removed = False
        for final_item in final_data:
            if not any(new_item['url'] == final_item['url'] for new_item in new_data):
                if step['module_options']['clean_removed']:
                    logging.info('item with URL %s not found in %s. Deleting from output file: %s.', final_item['url'], step['module_options']['source_file'], final_item)
                    final_data.remove(final_item)
                    items_were_removed = True
                else:
                    logging.warning('item with URL %s not found in %s. Consider deleting it manually or using clean_removed: True.', final_item['url'], step['module_options']['source_file'])
        if step['module_options']['clean_removed'] and items_were_removed:
            with open(step['module_options']['output_file'], 'w+', encoding="utf-8") as yaml_file:
                logging.info('writing file %s', step['module_options']['output_file'])
                yaml.dump(final_data, yaml_file)
    else:
        with open(step['module_options']['output_file'], 'w+', encoding="utf-8") as yaml_file:
            logging.debug('writing file %s', step['module_options']['output_file'])
            yaml.dump(new_data, yaml_file)
