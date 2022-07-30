"""downloads videos in `url` keys, using yt-dlp
writes downloaded file names back to the original data file in 'filename' key
Supported sites: https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md

# $ python3 -m venv .venv && source .venv/bin/activate && pip3 install shaarli-client && shaarli get-links --limit=all >| shaarli.json
# $ hecat --config tests/.hecat.import_shaarli.yml
# $ cat tests/.hecat.download_videos.yml
steps:
  - name: download_video
    module: processors/download_video
    module_options:
      data_file: shaarli.yml
      only_tags: ['video'] # only download items tagged with all these tags
      exclude_tags: ['nodl'] # don't download items tagged with any of these tags # TODO
      output_directory: 'tests/video'
      download_playlists: False # optional, default False
      skip_when_filename_present: False # optional, default False
      retry_items_with_error: True # optional, default True

# $ hecat --config tests/.hecat.download_videos.yml

Data file format (output of import_shaarli module):
# shaarli.yml
- id: 1667 # required, unique id
  url: https://www.youtube.com/watch?v=BaW_jenozKc # required, URL supported by yt-dlp
  ...
  video_filename: 'Philipp_Hagemeister - youtube-dl_test_video_a - youtube-BaW_jenozKc.webm' # added automatically

Source directory structure:
└── shaarli.yml

Output directory structure:
└── tests/video/Philipp_Hagemeister - youtube-dl_test_video_a - youtube-BaW_jenozKc.webm
└── tests/video/Philipp_Hagemeister - youtube-dl_test_video_a - youtube-BaW_jenozKc.info.json
└── tests/video/Philipp_Hagemeister - youtube-dl_test_video_a - youtube-BaW_jenozKc.en.vtt
"""

import os
import logging
import json
import ruamel.yaml
import yt_dlp
from ..utils import load_yaml_data

yaml = ruamel.yaml.YAML()
yaml.indent(sequence=2, offset=0)
yaml.width = 4096 # don't wrap long lines in the output file

# print(help(yt_dlp.YoutubeDL))
# exit(1)
YDL_DEFAULT_OPTS = {
    'outtmpl': '%(uploader)s - %(title)s - %(extractor)s-%(id)s.%(ext)s', # without directory
    'trim_file_name': 180,
    'writeinfojson': True,
    'writesubtitles': True,
    'restrictfilenames': True,
    'compat_opts': ['no-live-chat'],
    'postprocessors': [{
        'key': 'FFmpegExtractAudio'
    }],
    'keepvideo': False,
    'restrictfilenames': True,
    'download_archive': 'yt-dlp.audio.archive',
    'format': 'bestaudio',
    'noplaylist': True
}

def write_data_file(step, items):
    """write updated data back to the data file"""
    with open(step['module_options']['data_file'] + '.tmp', 'w') as temp_yaml_file:
        logging.info('writing temporary data file %s', step['module_options']['data_file'] + '.tmp')
        yaml.dump(items, temp_yaml_file)
    logging.info('writing data file %s', step['module_options']['data_file'])
    os.rename(step['module_options']['data_file'] + '.tmp', step['module_options']['data_file'])

def download_videos(step, ydl_opts=YDL_DEFAULT_OPTS):
    """download videos from the step['url'], if it matches specified step['only_tags'],
    write downloaded filenames to new 'video_filenames' key in the original data file for each downloaded item
    """
    # prepend output directory to the output filename template/archive filename
    full_outtmpl = step['module_options']['output_directory'] + '/' + ydl_opts['outtmpl']
    full_download_archive = step['module_options']['output_directory'] + '/' + ydl_opts['download_archive']
    ydl_opts['outtmpl'] = full_outtmpl
    ydl_opts['download_archive'] = full_download_archive
    # set noplaylist option depending on step['download_playlists']
    if 'download_playlists' in step.keys() and step['download_playlists']:
        ydl_opts['noplaylist'] == False
    items = load_yaml_data(step['module_options']['data_file'])
    logging.info('starting download of video files')
    for item in items:
        if ('skip_when_filename_present' in step['module_options'].keys() and
                step['module_options']['skip_when_filename_present'] and
                'video_filename' in item.keys()):
            logging.info('%s (id %s): video_filename already recorded in the data file, skipping', item['url'], item['id'])
        if ('retry_items_with_error' in step['module_options'] and
                not step['module_options']['retry_items_with_error'] and
                'video_download_error' in item.keys()):
            logging.info('%s (id %s): not retrying download on items with video_download_error set, skipping')
        elif list(set(step['module_options']['only_tags']) & set(item['tags'])):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logging.info('downloading %s', item['url'])
                    try:
                        info = ydl.extract_info(item['url'], download=True)
                        if info is not None:
                            # TODO does not get the real, final filename after audio extraction https://github.com/ytdl-org/youtube-dl/issues/5710
                            outpath = ydl.prepare_filename(info)
                            for item2 in items:
                                if item2['id'] == item['id']:
                                    item2['video_filename'] = outpath
                                    item.pop('video_download_error', False)
                                    break
                            write_data_file(step, items)
                    except (yt_dlp.utils.DownloadError, AttributeError) as e:
                        logging.error('%s (id %s): %s', item['url'], item['id'], str(e))
                        item['video_download_error'] = str(e)
                        write_data_file(step, items)
        else:
            logging.info('id %s: no tags matching only_tags, skipping', item['id'])
    exit(1)
