"""import data from a Shaarli instance using output from the API
- https://github.com/shaarli/Shaarli
- https://github.com/shaarli/python-shaarli-client/
- https://shaarli.github.io/api-documentation/

$ shaarli get-links --limit=all > shaarli.json
# hecat.yml
steps:
  - name: import
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

# TODO sort keys in each dict of data
# - created: '2022-07-27T22:56:06+02:00'
#   description: ''
#   id: 6624
#   private: false
#   shorturl: zKVXxA
#   tags:
#   - video
#   - vj
#   - math
#   - nodl
#   title: The Burning Ship - A Fractal Zoom (5e598) (4k 60fps) - YouTube
#   updated: '2022-07-29T14:15:39+02:00'
#   url: https://www.youtube.com/watch?v=2S3lc2G3rWs
