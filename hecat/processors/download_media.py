"""downloads videos/audio in `url` keys, using yt-dlp
writes downloaded file names back to the original data file in 'filename' key
Supported sites: https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md
ffmpeg (https://ffmpeg.org/) must be installed for audio/video conversion support

# $ python3 -m venv .venv && source .venv/bin/activate && pip3 install shaarli-client && shaarli get-links --limit=all >| shaarli.json
# $ hecat --config tests/.hecat.import_shaarli.yml
# $ cat tests/.hecat.download_video.yml
steps:
  - name: download video files
    module: processors/download_media
    module_options:
      data_file: tests/shaarli.yml # path to the YAML data file
      only_tags: ['video'] # only download items tagged with all these tags
      exclude_tags: ['nodl'] # (default []), don't download items tagged with any of these tags
      output_directory: 'tests/video' # path to the output directory for media files
      download_playlists: False # (default False) download playlists
      skip_when_filename_present: True # (default True) skip processing when item already has a 'video_filename/audio_filename': key
      retry_items_with_error: True # (default True) retry downloading items for which an error was previously recorded
      only_audio: False # (default False) download the 'bestaudio' format instead of the default 'best'
      use_download_archive: True # (default True) use a yt-dlp archive file to record downloaded items, skip them if already downloaded

# $ cat tests/.hecat.download_audio.yml
steps:
  - name: download audio files
    module: processors/download_media
    module_options:
      data_file: tests/shaarli.yml
      only_tags: ['music']
      exclude_tags: ['nodl']
      output_directory: 'tests/audio'
      only_audio: True

# $ hecat --config tests/.hecat.download_video.yml
# $ hecat --config tests/.hecat.download_audio.yml

Data file format (output of import_shaarli module):
# shaarli.yml
- id: 1667 # required, unique id
  url: https://www.youtube.com/watch?v=BaW_jenozKc # required, URL supported by yt-dlp
  tags:
    - tag1
    - tag2
    - video
    - music
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
import ruamel.yaml
import yt_dlp
from ..utils import load_yaml_data

yaml = ruamel.yaml.YAML()
yaml.indent(sequence=2, offset=0)
yaml.width = 4096 # don't wrap long lines in the output file

def write_data_file(step, items):
    """write updated data back to the data file"""
    with open(step['module_options']['data_file'] + '.tmp', 'w', encoding="utf-8") as temp_yaml_file:
        logging.info('writing temporary data file %s', step['module_options']['data_file'] + '.tmp')
        yaml.dump(items, temp_yaml_file)
    logging.info('writing data file %s', step['module_options']['data_file'])
    os.rename(step['module_options']['data_file'] + '.tmp', step['module_options']['data_file'])

def download_media(step):
    """download videos from the each item's 'url', if it matches one of step['only_tags'],
    write downloaded filenames to a new key audio_filename/video_filename in the original data file for each downloaded item
    """
    # print(help(yt_dlp.YoutubeDL))
    # exit(1)
    ydl_opts = {
        'outtmpl': '%(uploader)s - %(title)s - %(extractor)s-%(id)s.%(ext)s', # without directory
        'trim_file_name': 180,
        'writeinfojson': True,
        'writesubtitles': True,
        'restrictfilenames': True,
        'compat_opts': ['no-live-chat'],
        'download_archive': 'yt-dlp.video.archive',
        'noplaylist': True
    }
    filename_key = 'video_filename'
    error_key = 'video_download_error'
    skipped_count = 0
    downloaded_count = 0
    error_count = 0
    # add specific options when only_audio = True
    if 'only_audio' in step['module_options'] and step['module_options']['only_audio']:
        ydl_opts['postprocessors'] =  [ {'key': 'FFmpegExtractAudio'} ]
        ydl_opts['keepvideo'] = False
        ydl_opts['format'] = 'bestaudio'
        ydl_opts['download_archive'] = 'yt-dlp.audio.archive'
        filename_key = 'audio_filename'
        error_key = 'audio_download_error'
    ydl_opts['outtmpl'] = step['module_options']['output_directory'] + '/' + ydl_opts['outtmpl']
    ydl_opts['download_archive'] = step['module_options']['output_directory'] + '/' + ydl_opts['download_archive']
    if 'use_download_archive' in step['module_options'] and not step['module_options']['use_download_archive']:
        del ydl_opts['download_archive']
    if 'download_playlists' in step.keys() and step['download_playlists']:
        ydl_opts['noplaylist'] == False

    items = load_yaml_data(step['module_options']['data_file'])
    for item in items:
        # skip download when skip_when_filename_present = True, and video/audio_filename key already exists
        if (('skip_when_filename_present' not in step['module_options'].keys() or
                step['module_options']['skip_when_filename_present']) and
                filename_key in item.keys()):
            logging.info('skipping %s (id %s): %s already recorded in the data file', item['url'], item['id'], filename_key)
            skipped_count = skipped_count +1
        # skip download when retry_items_with_error = False, and video/audio_download_error key alraedy exists
        elif ('retry_items_with_error' in step['module_options'] and
                not step['module_options']['retry_items_with_error'] and
                error_key in item.keys()):
            logging.info('skipping %s (id %s): not retrying download on items with %s set', item['url'], item['id'], error_key)
            skipped_count = skipped_count +1
        # skip download when one of the item's tags matches a tag in exclude_tags
        elif ('exclude_tags' in step['module_options'] and
                any(tag in item['tags'] for tag in step['module_options']['exclude_tags'])):
            logging.info('skipping %s (id %s): one or more tags are present in exclude_tags', item['url'], item['id'])
            skipped_count = skipped_count +1
        # download if all tags in only_tags are present in the item's tags
        elif list(set(step['module_options']['only_tags']) & set(item['tags'])):
            logging.info('downloading %s (id %s)', item['url'], item ['id'])
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(item['url'], download=True)
                    if info is not None:
                        # TODO does not get the real, final filename after audio extraction https://github.com/ytdl-org/youtube-dl/issues/5710, https://github.com/ytdl-org/youtube-dl/issues/7137
                        outpath = ydl.prepare_filename(info)
                        for item2 in items:
                            if item2['id'] == item['id']:
                                item2[filename_key] = outpath
                                item.pop(error_key, False)
                                break
                        write_data_file(step, items)
                    downloaded_count = downloaded_count +1
                except (yt_dlp.utils.DownloadError, AttributeError) as e:
                    logging.error('%s (id %s): %s', item['url'], item['id'], str(e))
                    item[error_key] = str(e)
                    write_data_file(step, items)
                    error_count = error_count + 1
        else:
            logging.info('skipping %s (id %s): no tags matching only_tags', item['url'], item['id'])
            skipped_count = skipped_count + 1
    logging.info('processing complete. Downloaded: %s - Skipped: %s - Errors %s', downloaded_count, skipped_count, error_count)
