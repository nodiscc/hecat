"""render data as HTML table
# $ cat hecat.yml
steps:
  - name: export shaarli data to HTML table
    module: importers/shaarli_api
    module_options:
      source_file: shaarli.yml # file from which data will be loaded
      output_file: index.html # (default index.html) output HTML table file
      html_title: "hecat HTML export" # (default "hecat HTML export") output HTML title
      favicon_base64: "iVBORw0KGgoAAAAN..." # (defaults to the default favicon) base64-encoded png favicon
      description_format: paragraph # (details/paragraph, default details) wrap the description in a HTML details tag

Source directory structure:
└── shaarli.yml

Output directory structure:
└── index.html
"""

import sys
import os
import logging
from jinja2 import Template
from ..utils import load_yaml_data
from datetime import datetime
import markdown

HTML_JINJA = """
<html>
<head>
<title>{{ html_title }}</title>
<link rel="icon" href="data:image/png;base64,{{ favicon_base64 }}">
<style>
  body {
    margin: 10px 20px;
    padding: 0;
    font-family: 'Trebuchet MS', 'Lucida Sans Unicode', 'Lucida Grande', 'Lucida Sans', Arial, sans-serif;
    background-color: #F8F8F8;
  }

  table {
    width: 100%;
    min-width: 960px;
    border-collapse: collapse;
  }

  a {
    text-decoration: none;
  }

  table, th, td {
    padding: 1px;
    text-align: left;
    border-bottom: 1px solid #ddd;
    font-size: 90%;
  }

  tr:hover {
    background-color: #E6F3F9;
  }

  thead {
    font-weight: bold;
    background-color: #EAEAEA;
  }

  code {
    background-color: #EAEAEA;
    padding: 1px;
    font-family: Monospace;
    font-size: 110%;
    border-radius: 3px;
    color: #222;
  }

  ul, p {
    margin-top: auto;
  }

  ul {
    padding-left: 20px;
  }

  .searchbar {
    background-color: #EAEAEA;
    padding: 10px;
  }

  .date-column {
    min-width: 130px;
  }
</style>

<script>
function myFunctionTitle() {
  // Declare variables
  var input, filter, table, tr, td, i, txtValue;
  input = document.getElementById("myTitleInput");
  filter = input.value.toUpperCase();
  table = document.getElementById("myTable");
  tr = table.getElementsByTagName("tr");

  // Loop through all table rows, and hide those who don't match the search query
  for (i = 0; i < tr.length; i++) {
    td = tr[i].getElementsByTagName("td")[0];
    if (td) {
      txtValue = td.textContent || td.innerText;
      if (txtValue.toUpperCase().indexOf(filter) > -1) {
        tr[i].style.display = "";
      } else {
        tr[i].style.display = "none";
      }
    }
  }
}

function myFunctionTag() {
  // Declare variables
  var input, filter, table, tr, td, i, txtValue;
  input = document.getElementById("myTagInput");
  filter = input.value.toUpperCase();
  table = document.getElementById("myTable");
  tr = table.getElementsByTagName("tr");

  // Loop through all table rows, and hide those who don't match the search query
  for (i = 0; i < tr.length; i++) {
    td = tr[i].getElementsByTagName("td")[2];
    if (td) {
      txtValue = td.textContent || td.innerText;
      if (txtValue.toUpperCase().indexOf(filter) > -1) {
        tr[i].style.display = "";
      } else {
        tr[i].style.display = "none";
      }
    }
  }
}
</script>


</head>
<body>
<div class="searchbar">
<input type="text" id="myTitleInput" onkeyup="myFunctionTitle()" placeholder="Search for titles/descriptions...">
<input type="text" id="myTagInput" onkeyup="myFunctionTag()" placeholder="Search for @tags..">
<span>{{ link_count }} links</span>
<span style="font-size: 75%; color: #666; text-align: 'right';">Built with <a href="https://github.com/nodiscc/hecat">hecat</a></span>
</div>
<table id="myTable">
  <thead>
    <tr>
      <td>Title</td>
      <td class="date-column">Date</td>
      <td>Tags</td>
    </tr>
  </thead>
{% for item in items %}
<tr>
  <td><a href='{{ item['url'] }}'>{{ item['title'] }}</a>
  {% if item['description'] is defined and item['description'] %}<br/>{% if description_format == 'details' %}<details><summary></summary>{% elif description_format == 'paragraph' %}<p>{% endif %}{{ jinja_markdown(item['description']) }}{% if description_format == 'details' %}</details>{% elif description_format == 'paragraph' %}</p>{% endif %}{% endif %}
  </td>
  <td>{{ simple_datetime(item.created) }}</td>
  <td><code>@{{ '</code> <code>@'.join(item['tags']) }}</code></td>
<tr/>
{% endfor %}
</div>
</table>
</body>
</html>
"""

def jinja_markdown(text):
  """wrapper for using the markdown library from inside the jinja2 template"""
  return markdown.markdown(text)

def simple_datetime(date):
  return datetime.strftime(datetime.strptime(date, "%Y-%m-%dT%H:%M:%S%z"), "%Y-%m-%d %H:%M:%S")

def render_html_table(step):
    """render the list data as a HTML table"""
    if 'output_file' not in step['module_options']:
        step['module_options']['output_file'] = 'index.html'
    if 'html_title' not in step['module_options']:
        step['module_options']['html_title'] = 'hecat HTML export'
    if 'favicon_base64' not in step['module_options']:
        step['module_options']['favicon_base64'] = 'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQAgMAAABinRfyAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAB3RJTUUH5wIEFgEeyYiWTQAAAAlQTFRFAAAALi4u////gGfi/AAAAAF0Uk5TAEDm2GYAAAABYktHRAJmC3xkAAAAKUlEQVQI12NggAPR0NAQBqlVq5YwSIaGpjBILsVFhK1MgSgBKwZrgwMAswcRaNWVOXAAAAAldEVYdGRhdGU6Y3JlYXRlADIwMjMtMDItMDRUMjI6MDE6MzArMDA6MDB1Hpz/AAAAJXRFWHRkYXRlOm1vZGlmeQAyMDIzLTAyLTA0VDIyOjAxOjMwKzAwOjAwBEMkQwAAAABJRU5ErkJggg=='
    if 'description_format' not in step['module_options']:
        step['module_options']['description_format'] = 'details'
    if step['module_options']['description_format'] not in ['details', 'paragraph']:
        logging.error('unrecognized value %s for description_format option. Allowed values: details, paragraph', step['module_options']['description_format'])
        sys.exit(1)
    data = load_yaml_data(step['module_options']['source_file'])
    link_count = len(data)
    html_template = Template(HTML_JINJA)
    html_template.globals['jinja_markdown'] = jinja_markdown
    html_template.globals['simple_datetime'] = simple_datetime
    with open(step['module_options']['output_file'], 'w+', encoding="utf-8") as html_file:
        logging.info('writing file %s', step['module_options']['output_file'])
        html_file.write(html_template.render(items=data,
                                            link_count=link_count,
                                            html_title=step['module_options']['html_title'],
                                            favicon_base64=step['module_options']['favicon_base64'],
                                            description_format=step['module_options']['description_format']
                                            ))
