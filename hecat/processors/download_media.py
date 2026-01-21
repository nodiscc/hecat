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
from ..utils import load_yaml_data, write_data_file

yaml = ruamel.yaml.YAML()
yaml.indent(sequence=2, offset=0)
yaml.width = 99999


def should_skip_item(item, module_options, filename_key, error_key):
    """Determine if an item should be skipped and return (should_skip, reason).

    Returns:
        tuple: (bool, str) - (True, reason) if item should be skipped, (False, None) otherwise
    """
    # Check if filename already present and skip_when_filename_present is True
    skip_when_present = module_options.get('skip_when_filename_present', True)
    if skip_when_present and filename_key in item:
        return True, f'{filename_key} already recorded in the data file'

    # Check if we should skip items with errors
    retry_errors = module_options.get('retry_items_with_error', True)
    if not retry_errors and error_key in item:
        return True, f'not retrying download on items with {error_key} set'

    # Check if item has any excluded tags
    exclude_tags = module_options.get('exclude_tags', [])
    if exclude_tags and any(tag in item.get('tags', []) for tag in exclude_tags):
        return True, 'one or more tags are present in exclude_tags'

    # Check if item has any required tags
    only_tags = module_options.get('only_tags', [])
    if not list(set(only_tags) & set(item.get('tags', []))):
        return True, 'no tags matching only_tags'

    return False, None


def download_media(step):
    """download videos from the each item's 'url', if it matches one of step['only_tags'],
    write downloaded filenames to a new key audio_filename/video_filename in the original data file for each downloaded item
    """
    # print(help(yt_dlp.YoutubeDL))
    ydl_opts = {
        'outtmpl': '%(uploader)s - %(title)s - %(extractor)s-%(id)s.%(ext)s',
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
    if step['module_options'].get('only_audio', False):
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio'}]
        ydl_opts['keepvideo'] = False
        ydl_opts['format'] = 'bestaudio'
        ydl_opts['download_archive'] = 'yt-dlp.audio.archive'
        filename_key = 'audio_filename'
        error_key = 'audio_download_error'

    ydl_opts['outtmpl'] = step['module_options']['output_directory'] + '/' + ydl_opts['outtmpl']
    ydl_opts['download_archive'] = step['module_options']['output_directory'] + '/' + ydl_opts['download_archive']

    if not step['module_options'].get('use_download_archive', True):
        del ydl_opts['download_archive']

    if step.get('download_playlists', False):
        ydl_opts['noplaylist'] = False

    items = load_yaml_data(step['module_options']['data_file'])

    for item in items:
        should_skip, skip_reason = should_skip_item(
            item,
            step['module_options'],
            filename_key,
            error_key
        )

        if should_skip:
            logging.debug('skipping %s (id %s): %s', item['url'], item['id'], skip_reason)
            skipped_count += 1
            continue

        # Download the item
        logging.info('downloading %s (id %s)', item['url'], item['id'])
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(item['url'], download=True)
                if info is not None:
                    # TODO does not get the real, final filename after audio extraction
                    # https://github.com/ytdl-org/youtube-dl/issues/5710
                    # https://github.com/ytdl-org/youtube-dl/issues/7137
                    outpath = ydl.prepare_filename(info)
                    for item2 in items:
                        if item2['id'] == item['id']:
                            item2[filename_key] = outpath
                            item2.pop(error_key, None)
                            break
                    write_data_file(step, items)
                downloaded_count += 1
            except (yt_dlp.utils.DownloadError, AttributeError) as e:
                logging.error('%s (id %s): %s', item['url'], item['id'], str(e))
                item[error_key] = str(e)
                write_data_file(step, items)
                error_count += 1

    logging.info('processing complete. Downloaded: %s - Skipped: %s - Errors %s',
                 downloaded_count, skipped_count, error_count)