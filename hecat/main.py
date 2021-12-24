"""hecat CLI entrypoint"""
import argparse
import logging
from .exporters import render_markdown_singlepage
from .exporters import render_markdown_authors
from .importers import import_markdown_awesome

LOG_FORMAT = "%(levelname)s:%(filename)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

##########################

def hecat_build(args):
    """build markdown from YAML source files"""
    if args.exporter == 'markdown_singlepage':
        markdown_singlepage = render_markdown_singlepage(args)
        with open(args.output_directory + '/' + args.output_file, 'w+') as outfile:
            outfile.write(markdown_singlepage)
    if args.authors:
        markdown_authors = render_markdown_authors(args)
        with open(args.output_directory + '/AUTHORS.md', 'w+') as outfile:
            outfile.write(markdown_authors)

def hecat_import(args):
    """import initial data from other formats"""
    if args.importer == 'markdown_awesome':
        import_markdown_awesome(args)

def hecat_process(args):
    """apply processing rules"""
    processors = args.processors.split(',')
    options = args.options.split(',')
    if 'github_metadata' in args.processors:
        from .processors import add_github_metadata, check_github_last_updated
        add_github_metadata(args, options)
        check_github_last_updated(args)


#######################

def main():
    # pylint: disable=line-too-long
    """Main loop"""
    # command-line parsing
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    build_parser = subparsers.add_parser('build', help='build markdown from YAML source files')
    build_parser.add_argument('--exporter', type=str, default='markdown_singlepage', choices=['markdown_singlepage'], help='exporter to use')
    build_parser.add_argument('--source-directory', required=True, type=str, help='base directory for YAML data')
    build_parser.add_argument('--output-directory', required=True, type=str, help='base directory for markdown output')
    build_parser.add_argument('--output-file', required=True, type=str, help='output filename')
    build_parser.add_argument('--tags-directory', type=str, default='/tags/', help='source subdirectory for tags definitions')
    build_parser.add_argument('--software-directory', type=str, default='/software/', help='source subdirectory for software definitions')
    build_parser.add_argument('--authors', type=bool, default=False, help='generate an AUTHORS.md file from the source git repository log')
    build_parser.set_defaults(action=hecat_build)

    import_parser = subparsers.add_parser('import', help='import initial data from other formats')
    import_parser.add_argument('--importer', type=str, default='markdown_awesome', choices=['markdown_awesome'], help='importer to use')
    import_parser.add_argument('--source-file', required=True, type=str, help='input markdown file')
    import_parser.add_argument('--output-directory', required=True, type=str, help='base directory for YAML output')
    import_parser.add_argument('--tags-directory', type=str, default='/tags/', help='destination subdirectory for tags definitions')
    import_parser.add_argument('--software-directory', type=str, default='/software/', help='destination subdirectory for software definitions')
    import_parser.add_argument('--platforms-directory', type=str, default='/platforms/', help='destination subdirectory for platforms definitions')
    import_parser.set_defaults(action=hecat_import)

    process_parser = subparsers.add_parser('process', help='apply processing rules')
    process_parser.add_argument('--processors', required=True, type=str, help='processors to run, comma-separated (github_metadata)')
    process_parser.add_argument('--source-directory', required=True, type=str, help='base directory for YAML data')
    process_parser.add_argument('--software-directory', type=str, default='/software/', help='source subdirectory for software definitions')
    process_parser.add_argument('--options', type=str, default='', help='[OPTION1=VALUE,OPTION2=VALUE,...] processors options, comma-separated') #  --options=only-missing,option2
    process_parser.set_defaults(action=hecat_process)

    args = parser.parse_args()
    args.action(args)
