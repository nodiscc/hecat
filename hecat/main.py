"""hecat CLI entrypoint"""
import sys
import argparse
import logging
from .utils import load_yaml_data
from .importers import import_markdown_awesome, import_shaarli_json
from .processors import software_metadata, awesome_lint, check_urls, download_media, archive_webpages
from .exporters import render_markdown_singlepage, render_html_table
from .exporters import render_markdown_multipage

LOG_FORMAT = "%(levelname)s:%(filename)s: %(message)s"
LOG_LEVEL_MAPPING = {
                    'DEBUG': logging.DEBUG,
                    'INFO': logging.INFO,
                    'WARNING': logging.WARNING,
                    'ERROR': logging.ERROR,
                    }

def main():
    """Main loop"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', dest='config_file', type=str, default='.hecat.yml', help='configuration file (default .hecat.yml)')
    parser.add_argument('--log-level', dest='log_level', type=str, default='INFO', help='log level (default INFO)', choices=['ERROR', 'WARNING', 'INFO', 'DEBUG'])
    parser.add_argument('--log-file', dest='log_file', type=str, default=None, help='log file (default none)')
    args = parser.parse_args()
    if args.log_file is not None:
        logging_handlers = [ logging.FileHandler(args.log_file), logging.StreamHandler() ]
    else:
        logging_handlers = [ logging.StreamHandler() ]
    logging.basicConfig(level=LOG_LEVEL_MAPPING.get(args.log_level), format=LOG_FORMAT, handlers = logging_handlers)
    config = load_yaml_data(args.config_file)
    for step in config['steps']:
        logging.info('running step %s', step['name'])
        if step['module'] == 'importers/markdown_awesome':
            import_markdown_awesome(step)
        elif step['module'] == 'importers/shaarli_api':
            import_shaarli_json(step)
        elif step['module'] == 'processors/software_metadata':
            software_metadata(step)
        elif step['module'] == 'processors/awesome_lint':
            awesome_lint(step)
        elif step['module'] == 'processors/url_check':
            check_urls(step)
        elif step['module'] == 'processors/archive_webpages':
            archive_webpages(step)
        elif step['module'] == 'processors/download_media':
            download_media(step)
        elif step['module'] == 'exporters/markdown_singlepage':
            render_markdown_singlepage(step)
        elif step['module'] == 'exporters/html_table':
            render_html_table(step)
        elif step['module'] == 'exporters/markdown_multipage':
            render_markdown_multipage(step)
        else:
            logging.error('step %s: unknown module %s', step['name'], step['module'])
            sys.exit(1)
    logging.info('all steps completed')

if __name__ == "__main__":
    main()
