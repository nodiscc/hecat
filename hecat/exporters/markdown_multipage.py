"""export YAML data to a multipage markdown site which can be used to generate a HTML site with Sphinx
- A main index.html page listing all items
- Pages for each tag
This will output an intermediary markdown site in output_directory/md
sphinx (https://www.sphinx-doc.org/) must be used to generate the final HTML site:
$ sphinx-build -b html -c CONFIG_DIR/ SOURCE_DIR/ OUTPUT_DIR/
CONFIG_DIR/ is the directory containing the conf.py sphinx configuration file, you can find an example at test/conf.py in this repository
SOURCE_DIR/ is the directory containing the markdown site generated by hecat/markdown_multipage.py
OUTPUT_DIR/ is the output directory for the HTML site
Currently, html_theme = 'furo', extensions = ['myst_parser', 'sphinx_design'] and myst_enable_extensions = ['fieldlist'] are expected in the sphinx configuration file

$ git clone https://github.com/awesome-selfhosted/awesome-selfhosted-data
$ $EDITOR .hecat.yml
$ hecat

# .hecat.yml
steps:
  - name: export YAML data to single-page HTML
    module: exporters/markdown_multipage
    module_options:
      source_directory: awesome-selfhosted-data # directory containing YAML data
      output_directory: awesome-selfhosted-html # directory to write markdown pages to
      output_file: index.html # optional, default index.html
      authors_file: AUTHORS.md # optional, default no authors file
      exclude_licenses: # optional, default []
        - 'CC-BY-NC-4.0'
        - '⊘ Proprietary'
        - 'SSPL-1.0'

Output directory structure:
└── index.html
└── TODO

The source YAML directory structure, and formatting for software/platforms data is documented in markdown_singlepage.py.
The authors_file, if set, will be generated from the `git shortlog` of your source directory.
"""

import os
import logging
from datetime import datetime, timedelta
import ruamel.yaml
from jinja2 import Template
from ..utils import load_yaml_data, to_kebab_case

yaml = ruamel.yaml.YAML(typ='safe')
yaml.indent(sequence=4, offset=2)

MARKDOWN_CSS="""
<style>
    .tag {
        background-color: #DBEAFE;
        border-radius: 5px;
        padding: 2px 8px 0px 8px;
        color: #1E40AF;
        font-weight: bold;
        display: inline-block;
    }
    .tag a {
        text-decoration: none
    }
    .platform {
        background-color: #B0E6A3;
        border-radius: 5px;
        padding: 2px 8px 0px 8px;
        color: #2B4026;
        font-weight: bold;
        display: inline-block;
    }
    .license {
        background-color: #A7C7F9;
        border-radius: 5px;
        padding: 2px 8px 0px 8px;
        color: #173B80;
        font-weight: bold;
        display: inline-block;
    }
    .stars {
        background-color: #FFFCAB;
        border-radius: 5px;
        padding: 2px 8px 0px 8px;
        color: #856000;
        font-weight: bold;
        display: inline-block;
    }
    .updated-at {
        background-color: #EFEFEF;
        border-radius: 5px;
        padding: 2px 8px 0px 8px;
        color: #444444;
        display: inline-block;
        font-weight: bold
    }
    .updated-at-orange {
        background-color: #FD9D49;
        border-radius: 5px;
        padding: 2px 8px 0px 8px;
        color: #FFFFFF;
        display: inline-block;
        font-weight: bold
    }
    .updated-at-red {
        background-color: #FD4949;
        border-radius: 5px;
        padding: 2px 8px 0px 8px;
        color: #FFFFFF;
        display: inline-block;
        font-weight: bold
    }
    .external-link-box {
        background-color: #1E40AF;
        border-radius: 5px;
        padding: 2px 8px 0px 8px;
        display: inline-block;
    }
    .external-link {
        color: #DBEAFE;
        font-weight: bold;
        text-decoration: none
    }
    .external-link a:hover {
        color: #FFF;
    }
    .sd-octicon {
        vertical-align: inherit
    }
</style>
"""

MARKDOWN_INDEX_CONTENT_HEADER="""
--------------------

## Software

This page lists all projects. Use links in the sidebar or click on tags to browse projects by category.
"""

SOFTWARE_JINJA_MARKDOWN="""
--------------------

### {{ software['name'] }}

{{ software['description'] }}

<span class="external-link-box"><a class="external-link" href="{{ software['website_url'] }}">{% raw %}{octicon}{% endraw %}`globe;0.8em;octicon` Website</a></span>
<span class="external-link-box"><a class="external-link" href="{% if software['source_code_url'] is defined %}{{ software['source_code_url'] }}{% else %}{{ software['website_url'] }}{% endif %}">{% raw %}{octicon}{% endraw %}`git-branch;0.8em;octicon` Source Code</a></span>

<span class="stars">★{% if software['stargazers_count'] is defined %}{{ software['stargazers_count'] }}{% else %}?{% endif %}</span>
<span class="{{ date_css_class }}">{% raw %}{octicon}{% endraw %}`clock;0.8em;octicon` {% if software['updated_at'] is defined %}{{ software['updated_at'] }}{% else %}?{% endif %}</span>
{% for platform in software['platforms'] %}<span class="platform">{{ platform }} </span> {% endfor %}
{% for license in software['licenses'] %}<span class="license">{% raw %}{octicon}{% endraw %}`law;0.8em;octicon` {{ license }} </span> {% endfor %}

{% for tag in tags %}<span class="tag"><a href="{{ tag['href'] }}">{% raw %}{octicon}{% endraw %}`tag;0.8em;octicon` {{ tag['name'] }}</a> </span>{% endfor %}

"""

TAG_HEADER_JINJA_MARKDOWN="""

# {{ tag['name'] }}

{{ tag['description']}}

{% if tag['related_tags'] is defined %}```{admonition} Related tags
{% for related_tag in tag['related_tags'] %}- [{{ related_tag }}]({{ to_kebab_case(related_tag) }}.md)
{% endfor %}
```
{% endif %}
{% if tag['external_links'] is defined %}```{seealso}
{% for link in tag['external_links'] %}- [{{ link['title'] }}]({{ link['url'] }})
{% endfor %}
```{% endif %}
{% if tag['redirect'] is defined %}```{important}
**Please visit {% for redirect in tag['redirect'] %}[{{ redirect['title'] }}]({{ redirect['url'] }}){% if not loop.last %}{{', '}}{% endif %} instead**{% endfor %}
```{% endif %}

"""

MARKDOWN_TAGPAGE_CONTENT_HEADER="""
--------------------

## Software
"""

def render_markdown_software(software, tags_relative_url='tags/'):
    """render a software project info as a markdown list item"""
    tags_dicts_list = []
    for tag in software['tags']:
        tags_dicts_list.append({"name": tag, "href": tags_relative_url + to_kebab_case(tag) + '.html'})
    date_css_class = 'updated-at'
    if 'updated_at' in software:
        last_update_time = datetime.strptime(software['updated_at'], "%Y-%m-%d")
        if last_update_time < datetime.now() - timedelta(days=365):
            date_css_class = 'updated-at-red'
        elif last_update_time < datetime.now() - timedelta(days=186):
            date_css_class = 'updated-at-orange'
    software_template = Template(SOFTWARE_JINJA_MARKDOWN)
    markdown_software = software_template.render(software=software, tags=tags_dicts_list, date_css_class=date_css_class)
    return markdown_software

def render_tag_page(step, tag, software_list):
    """render a page containing all items matching a specific tag"""
    logging.debug('rendering tag %s', tag['name'])
    tag_header_template = Template(TAG_HEADER_JINJA_MARKDOWN)
    tag_header_template.globals['to_kebab_case'] = to_kebab_case
    markdown_tag_page_header = tag_header_template.render(tag=tag)
    markdown_software_list = ''

    for software in software_list:
        if any(license in software['licenses'] for license in step['module_options']['exclude_licenses']):
            logging.debug("%s has a license listed in exclude_licenses, skipping", software['name'])
        elif any(item == tag['name'] for item in software['tags']):
            markdown_software_list = markdown_software_list + render_markdown_software(software, tags_relative_url='./')
    if markdown_software_list:
        markdown_tag_page = '{}{}{}{}'.format(MARKDOWN_CSS, markdown_tag_page_header, MARKDOWN_TAGPAGE_CONTENT_HEADER, markdown_software_list)
    else:
        markdown_tag_page = '{}{}'.format(MARKDOWN_CSS, markdown_tag_page_header)
    output_file_name = step['module_options']['output_directory'] + '/md/tags/' + to_kebab_case(tag['name'] + '.md')
    with open(output_file_name, 'w+', encoding="utf-8") as outfile:
        logging.debug('writing output file %s', output_file_name)
        outfile.write(markdown_tag_page)

def render_markdown_toctree(tags):
    """render the toctree block"""
    logging.debug('rendering toctree')
    tags_files_list = ''
    for tag in tags:
        tag_file_name = 'tags/' + to_kebab_case(tag['name'] + '.md')
        tags_files_list = '{}\n{}'.format(tags_files_list, tag_file_name)
    markdown_toctree = '\n```{{toctree}}\n:maxdepth: 1\n:hidden:\n{}\n```\n\n'.format(tags_files_list)
    return markdown_toctree

def render_markdown_multipage(step):
    """
    Render a single-page markdown list of all software, in alphabetical order
    Prepend/appends the header/footer
    """
    if 'exclude_licenses' not in step['module_options']:
        step['module_options']['exclude_licenses'] = []
    if 'output_file' not in step['module_options']:
        step['module_options']['output_file'] = 'index.md'

    tags = load_yaml_data(step['module_options']['source_directory'] + '/tags', sort_key='name')
    software_list = load_yaml_data(step['module_options']['source_directory'] + '/software')
    licenses = load_yaml_data(step['module_options']['source_directory'] + '/licenses.yml')
    markdown_fieldlist = ':tocdepth: 2\n'
    markdown_content_header = MARKDOWN_INDEX_CONTENT_HEADER

    with open(step['module_options']['source_directory'] + '/markdown/header.md', 'r', encoding="utf-8") as header_file:
        markdown_header = header_file.read()
    with open(step['module_options']['source_directory'] + '/markdown/footer.md', 'r', encoding="utf-8") as footer_file:
        markdown_footer = footer_file.read()
    markdown_toctree = render_markdown_toctree(tags)

    markdown_software_list = ''
    for software in software_list:
        if any(license in software['licenses'] for license in step['module_options']['exclude_licenses']):
            logging.debug("%s has a license listed in exclude_licenses, skipping", software['name'])
        else:
            markdown_software_list = markdown_software_list + render_markdown_software(software, tags_relative_url='tags/')
    markdown = '{}{}{}{}{}{}{}'.format(markdown_fieldlist, MARKDOWN_CSS, markdown_header, markdown_content_header, markdown_toctree, markdown_software_list, markdown_footer)

    output_file_name = step['module_options']['output_directory'] + '/md/' + step['module_options']['output_file']
    try:
        os.mkdir(step['module_options']['output_directory'] + '/md/')
        os.mkdir(step['module_options']['output_directory'] + '/md/tags/')
    except FileExistsError:
        pass
    with open(output_file_name, 'w+', encoding="utf-8") as outfile:
        logging.info('writing output file %s', output_file_name)
        outfile.write(markdown)

    logging.info('rendering tags pages')
    for tag in tags:
        render_tag_page(step, tag, software_list)
