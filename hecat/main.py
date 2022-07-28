"""hecat CLI entrypoint"""
import argparse
import logging
from .utils import load_yaml_data

LOG_FORMAT = "%(levelname)s:%(filename)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

def main():
    """Main loop"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', dest='config_file', type=str, default='.hecat.yml', help='configuration file')
    args = parser.parse_args()
    config = load_yaml_data(args.config_file)
    for step in config['steps']:
        logging.info('running step %s', step['name'])
        if step['module'] == 'importers/markdown_awesome':
            from .importers import import_markdown_awesome
            import_markdown_awesome(step)
        elif step['module'] == 'processors/github_metadata':
            from .processors import add_github_metadata, check_github_last_updated
            add_github_metadata(step)
            check_github_last_updated(step)
        elif step['module'] == 'processors/awesome_lint':
            from .processors import awesome_lint
            awesome_lint(step)
        elif step['module'] == 'exporters/markdown_singlepage':
            from .exporters import render_markdown_singlepage
            render_markdown_singlepage(step)
        else:
            logging.error('step %s: unknown module %s', step['name'], step['module'])
            exit(1)
    logging.info('all steps completed')

if __name__ == "__main__":
    main()