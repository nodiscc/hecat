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

# Constants
VIDEO_FILENAME_KEY = 'video_filename'
AUDIO_FILENAME_KEY = 'audio_filename'
VIDEO_ERROR_KEY = 'video_download_error'
AUDIO_ERROR_KEY = 'audio_download_error'
VIDEO_ARCHIVE_FILENAME = 'yt-dlp.video.archive'
AUDIO_ARCHIVE_FILENAME = 'yt-dlp.audio.archive'
OUTPUT_TEMPLATE = '%(uploader)s - %(title)s - %(extractor)s-%(id)s.%(ext)s'

# Base yt-dlp configuration
BASE_YDL_OPTIONS = {
    'outtmpl': OUTPUT_TEMPLATE,
    'trim_file_name': 180,
    'writeinfojson': True,
    'writesubtitles': True,
    'restrictfilenames': True,
    'compat_opts': ['no-live-chat'],
    'noplaylist': True
}

# Video-specific configuration
VIDEO_YDL_OPTIONS = {
    'download_archive': VIDEO_ARCHIVE_FILENAME,
}

# Audio-specific configuration
AUDIO_YDL_OPTIONS = {
    'postprocessors': [{'key': 'FFmpegExtractAudio'}],
    'keepvideo': False,
    'format': 'bestaudio',
    'download_archive': AUDIO_ARCHIVE_FILENAME,
}


def build_ydl_options(module_options, is_audio=False):
    """Build yt-dlp options based on module configuration.

    Args:
        module_options: Module options from the step configuration
        is_audio: Whether to configure for audio-only downloads

    Returns:
        dict: Complete yt-dlp options dictionary
    """
    # Start with base options
    ydl_opts = BASE_YDL_OPTIONS.copy()

    # Add media-type specific options
    if is_audio:
        ydl_opts.update(AUDIO_YDL_OPTIONS)
    else:
        ydl_opts.update(VIDEO_YDL_OPTIONS)

    # Add output directory to paths
    output_dir = module_options['output_directory']
    ydl_opts['outtmpl'] = f"{output_dir}/{ydl_opts['outtmpl']}"

    if 'download_archive' in ydl_opts:
        ydl_opts['download_archive'] = f"{output_dir}/{ydl_opts['download_archive']}"

    # Remove download archive if disabled
    if not module_options.get('use_download_archive', True):
        ydl_opts.pop('download_archive', None)

    # Enable playlists if requested
    if module_options.get('download_playlists', False):
        ydl_opts['noplaylist'] = False

    return ydl_opts


def download_single_item(item, items, ydl_opts, filename_key, error_key, step):
    """Download a single media item and update the data file.

    Args:
        item: The item to download (will be updated in-place)
        items: Full list of items (for write_data_file)
        ydl_opts: yt-dlp options dictionary
        filename_key: Key to store filename in ('video_filename' or 'audio_filename')
        error_key: Key to store errors in ('video_download_error' or 'audio_download_error')
        step: Step configuration (needed for write_data_file)

    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    logging.info('downloading %s (id %s)', item['url'], item['id'])

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(item['url'], download=True)
            if info is not None:
                # TODO does not get the real, final filename after audio extraction
                # https://github.com/ytdl-org/youtube-dl/issues/5710
                # https://github.com/ytdl-org/youtube-dl/issues/7137
                outpath = ydl.prepare_filename(info)

                # Update item directly (it's a reference to the dict in items list)
                item[filename_key] = outpath
                item.pop(error_key, None)

                write_data_file(step, items)
                return True, None
        except (yt_dlp.utils.DownloadError, AttributeError) as e:
            error_message = str(e)
            logging.error('%s (id %s): %s', item['url'], item['id'], error_message)
            item[error_key] = error_message
            write_data_file(step, items)
            return False, error_message

    return False, "No info returned from yt-dlp"


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
    module_options = step['module_options']
    is_audio = module_options.get('only_audio', False)

    # Build yt-dlp options and determine keys
    ydl_opts = build_ydl_options(module_options, is_audio)
    filename_key = AUDIO_FILENAME_KEY if is_audio else VIDEO_FILENAME_KEY
    error_key = AUDIO_ERROR_KEY if is_audio else VIDEO_ERROR_KEY

    skipped_count = 0
    downloaded_count = 0
    error_count = 0

    items = load_yaml_data(module_options['data_file'])

    for item in items:
        should_skip, skip_reason = should_skip_item(
            item,
            module_options,
            filename_key,
            error_key
        )

        if should_skip:
            logging.debug('skipping %s (id %s): %s', item['url'], item['id'], skip_reason)
            skipped_count += 1
            continue

        # Download the item
        success, error = download_single_item(item, items, ydl_opts, filename_key, error_key, step)

        if success:
            downloaded_count += 1
        else:
            error_count += 1

    logging.info('processing complete. Downloaded: %s - Skipped: %s - Errors %s',
                 downloaded_count, skipped_count, error_count)