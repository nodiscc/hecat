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

Source directory structure:
└── shaarli.json

Output directory structure:
└── shaarli.yml
"""

import logging
import ruamel.yaml
import json

yaml = ruamel.yaml.YAML()
yaml.indent(sequence=2, offset=0)

def import_shaarli_json(step):
    """Import data from the JSON output of Shaarli API"""
    with open(step['module_options']['source_file']) as json_file:
      data = json.load(json_file)
    with open(step['module_options']['output_file'], 'w+') as yaml_file:
        logging.debug('writing file %s', step['module_options']['output_file'])
        yaml.dump(data, yaml_file)
