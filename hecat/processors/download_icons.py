"""download_icons processor
Downloads icons from software `icon_url` entries and converts them to webp.

# hecat.yml
steps:
  - name: download icons
    module: processors/download_icons
    module_options:
      source_directory: tests/awesome-selfhosted-data
      output_directory: tests/awesome-selfhosted-data/icons     # (default <source_directory>/icons) output directory for .webp icons
      skip_when_icon_present: True                              # (default True) skip entries whose .webp already exists
      output_size: 128                                          # (default 128) target square size in pixels
      max_download_bytes: 2097152                               # (default 2 MiB) hard cap on bytes downloaded per icon
      max_image_pixels: 4194304                                 # (default 4 Mpx) reject sources whose width*height exceeds this; prevents decompression bombs
      request_timeout: 15                                       # (default 15) per-request timeout in seconds
      webp_quality: 85                                          # (default 85) lossy WEBP quality 0-100; only used for opaque non-icon-art sources
      webp_method: 6                                            # (default 6) WEBP encoder effort 0-6; 6=slowest/smallest
      retry_total: 2                                            # (default 2) max retries for transient failures (5xx, 429, connection errors)
      retry_backoff_factor: 1                                   # (default 1) urllib3 backoff factor between retries
      retry_status_forcelist: [429, 500, 502, 503, 504]         # (default same) HTTP statuses that should trigger a retry


source_directory: path to directory where data files reside. Directory structure:
├── software
│   ├── mysoftware.yml # .yml files containing software data
│   ├── someothersoftware.yml
│   └── ...
├── icons
│   ├── mysoftware.webp # .webp icons
└── ...
"""

import os
import sys
import tempfile
import logging
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image, ImageOps, UnidentifiedImageError
from ..utils import load_yaml_data

# Defaults
DEFAULT_MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024 # 2 MiB
DEFAULT_MAX_IMAGE_PIXELS = 2048 * 2048 # 4 Mpx, prevents decompression-bomb DoS
DEFAULT_REQUEST_TIMEOUT = 15
DEFAULT_SKIP_WHEN_ICON_PRESENT = True
DEFAULT_OUTPUT_SIZE = 128
DEFAULT_WEBP_QUALITY = 85
DEFAULT_WEBP_METHOD = 6
DEFAULT_RETRY_TOTAL = 2
DEFAULT_RETRY_BACKOFF_FACTOR = 1
DEFAULT_RETRY_STATUS_FORCELIST = (429, 500, 502, 503, 504)

# Allowed input types
ALLOWED_IMAGE_TYPES = {
    'PNG':  {'image/png'},
    'JPEG': {'image/jpeg'},
    'WEBP': {'image/webp'},
    'GIF':  {'image/gif'},
    'BMP':  {'image/bmp'},
    'TIFF': {'image/tiff'},
    'ICO':  {'image/x-icon', 'image/vnd.microsoft.icon'},
}

# Configuration helpers
def get_module_option(step, key, default):
    """return a module option value or its default"""
    return step['module_options'].get(key, default)

def build_retrying_session(retry_total, retry_backoff_factor, retry_status_forcelist):
    """build a requests.Session with retries on transient failures (5xx, 429, connection errors)"""
    retry = Retry(
        total=retry_total,
        backoff_factor=retry_backoff_factor,
        status_forcelist=tuple(retry_status_forcelist),
        allowed_methods=('HEAD', 'GET'),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def iter_software_entries_with_stem(source_directory):
    """return a list of (software, yaml stem, yaml path) tuples for every YAML in <source_directory>/software"""
    software_directory = Path(source_directory) / 'software'
    if not software_directory.is_dir():
        return []
    software_entries = []
    for yaml_path in sorted(software_directory.glob('*.yml')):
        software = load_yaml_data(str(yaml_path))
        software_entries.append((software, yaml_path.stem, yaml_path))
    return software_entries

# HTTP header parsing
def normalize_content_type(content_type):
    """normalize content-type to a lowercase mime type without parameters"""
    if content_type is None:
        return None
    return content_type.split(';', 1)[0].strip().lower()

def validate_content_type(content_type, allowed_mime_types, source_label):
    """validate content-type against a strict mime whitelist"""
    if content_type is None:
        return None
    normalized_type = normalize_content_type(content_type)
    if normalized_type not in allowed_mime_types:
        return f'{source_label}: MIME type not allowed: {normalized_type}'
    return None

def parse_content_length(content_length):
    """parse content-length header value and return integer bytes"""
    if content_length is None:
        return None, None
    try:
        parsed = int(content_length)
    except ValueError:
        return None, f'invalid Content-Length header: {content_length}'
    if parsed < 0:
        return None, f'invalid negative Content-Length header: {content_length}'
    return parsed, None

# HTTP request handling
def preflight_head(session, icon_url, timeout, max_download_bytes, allowed_mime_types):
    """run a head preflight check and validate response headers if available

    Status-code policy:
    - exception (DNS / connection / SSL): can't tell, fall through to GET so a transient network blip doesn't kill the entry.
    - 405 / 501: server doesn't support HEAD; fall through to GET.
    - 5xx: transient origin error; fall through to GET (the session adapter retries).
    - any other >= 400 (404, 403, 410, ...): definitive client-side error from the origin; block here so we don't waste a GET round trip on an entry that the origin already told us is unreachable.
    """
    try:
        logging.debug('running HEAD preflight for %s', icon_url)
        response = session.head(icon_url, allow_redirects=True, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        logging.warning('HEAD preflight failed for %s (%s); proceeding to GET without preflight', icon_url, exc)
        return None
    status = response.status_code
    logging.debug('HEAD %s -> status=%s, final_url=%s, Content-Type=%r, Content-Length=%r', icon_url, status, response.url, response.headers.get('Content-Type'), response.headers.get('Content-Length'))

    if status in (405, 501):
        logging.warning('HEAD not supported for %s (HTTP %s); proceeding to GET without preflight', icon_url, status)
        return None
    if 500 <= status < 600:
        logging.warning('HEAD preflight returned HTTP %s for %s; proceeding to GET (transient)', status, icon_url)
        return None
    if status >= 400:
        return f'HEAD preflight rejected by origin with HTTP status {status}'

    mime_error = validate_content_type(response.headers.get('Content-Type'), allowed_mime_types, 'HEAD response')
    if mime_error is not None:
        return mime_error
    content_length, content_length_error = parse_content_length(response.headers.get('Content-Length'))
    if content_length_error is not None:
        return content_length_error
    if content_length is not None and content_length > max_download_bytes:
        return f'HEAD response Content-Length {content_length} exceeds limit {max_download_bytes}'

    logging.debug('HEAD preflight successful for %s', icon_url)
    return None

def download_icon_to_temp(session, icon_url, output_directory, timeout, max_download_bytes, allowed_mime_types):
    """download icon data to a temporary file with strict byte cap enforcement. On any error return, the temp file is cleaned up before returning"""
    temp_file = tempfile.NamedTemporaryFile(dir=output_directory, suffix='.download', delete=False)
    temp_path = temp_file.name
    temp_file.close()
    logging.debug('allocated tempfile %s for %s', temp_path, icon_url)
    bytes_written = 0
    server_mime = None
    try:
        logging.debug('starting icon download for %s', icon_url)
        with session.get(icon_url, allow_redirects=True, stream=True, timeout=timeout) as response:
            logging.debug('GET %s -> status=%s, final_url=%s, Content-Type=%r, Content-Length=%r', icon_url, response.status_code, response.url, response.headers.get('Content-Type'), response.headers.get('Content-Length'))

            if response.status_code >= 400:
                remove_temp_file(temp_path)
                return None, None, f'download request failed with HTTP status {response.status_code}'

            raw_content_type = response.headers.get('Content-Type')
            mime_error = validate_content_type(raw_content_type, allowed_mime_types, 'GET response')
            if mime_error is not None:
                remove_temp_file(temp_path)
                return None, None, mime_error

            server_mime = normalize_content_type(raw_content_type)
            if server_mime is None:
                logging.info('%s: no Content-Type header on GET response, relying on file content sniff', icon_url)

            content_length, content_length_error = parse_content_length(response.headers.get('Content-Length'))
            if content_length_error is not None:
                remove_temp_file(temp_path)
                return None, None, content_length_error
            if content_length is not None and content_length > max_download_bytes:
                remove_temp_file(temp_path)
                return None, None, f'GET response Content-Length {content_length} exceeds limit {max_download_bytes}'

            with open(temp_path, 'wb') as temp_output:
                for chunk in response.iter_content(chunk_size=16384):
                    if not chunk:
                        continue
                    bytes_written += len(chunk)
                    if bytes_written > max_download_bytes:
                        remove_temp_file(temp_path)
                        return None, None, f'download exceeded max_download_bytes limit ({max_download_bytes})'
                    temp_output.write(chunk)

        logging.debug('download completed for %s (%s bytes)', icon_url, bytes_written)
    except requests.exceptions.RequestException as exc:
        remove_temp_file(temp_path)
        return None, None, f'download request failed: {exc}'
    return temp_path, server_mime, None

# Image processing
def convert_image_to_webp(temp_path, destination_path, output_size, allowed_image_formats, server_mime, allowed_image_types, max_image_pixels, webp_quality, webp_method):
    """verify image type, resize within output_size while keeping aspect ratio, pad to a square output_size x output_size canvas, and save as WEBP atomically.

    Encoder choice is per-source-format: lossless WEBP for sources with alpha or in {PNG, ICO, GIF, BMP}; lossy WEBP for photographic sources (JPEG, opaque WEBP).
    Truncated source images are rejected (Pillow default behavior)
    """
    tmp_destination = destination_path + '.tmp'
    try:
        logging.debug('converting icon file %s to %s', temp_path, destination_path)
        with Image.open(temp_path) as image:
            detected_format = (image.format or '').upper()
            logging.debug('Pillow opened %s: format=%s mode=%s size=%s bands=%s', temp_path, detected_format, image.mode, image.size, image.getbands())
            if detected_format not in allowed_image_formats:
                return f'detected image format not allowed: {detected_format or "unknown"}'

            # cross-check server-declared MIME against Pillow's sniffed format
            if server_mime is not None:
                expected_mimes = allowed_image_types.get(detected_format, set())
                if server_mime not in expected_mimes:
                    return f'MIME mismatch: server said {server_mime}, file decoded as {detected_format}'

            # decompression-bomb guard
            width, height = image.size
            if width * height > max_image_pixels:
                return f'image too large: {width}x{height} exceeds {max_image_pixels} pixels'

            # don't force an unused alpha channel onto opaque sources (e.g. JPEG photos)
            has_alpha = 'A' in image.getbands() or image.info.get('transparency') is not None
            target_mode = 'RGBA' if has_alpha else 'RGB'
            logging.debug('alpha=%s -> target_mode=%s', has_alpha, target_mode)

            resized = image.convert(target_mode)
            pre_thumb_size = resized.size
            resized.thumbnail((output_size, output_size), Image.Resampling.LANCZOS)
            logging.debug('thumbnailed %s -> %s (target box=%dx%d)', pre_thumb_size, resized.size, output_size, output_size)

            # normalize to a square output_size x output_size canvas without stretching
            pad_color = (0, 0, 0, 0) if target_mode == 'RGBA' else (255, 255, 255)
            resized = ImageOps.pad(
                resized,
                (output_size, output_size),
                color=pad_color,
                centering=(0.5, 0.5),
            )

            # per-source encoder split: Lossy on photos, lossless on icon-like art
            save_kwargs = {'format': 'WEBP', 'method': webp_method}
            if has_alpha or detected_format in {'PNG', 'ICO', 'GIF', 'BMP'}:
                save_kwargs['lossless'] = True
            else:
                save_kwargs['quality'] = webp_quality

            icc_profile = image.info.get('icc_profile')
            if icc_profile:
                save_kwargs['icc_profile'] = icc_profile
            logging.debug('saving WEBP with kwargs=%s (icc_profile=%s bytes)', {k: v for k, v in save_kwargs.items() if k != 'icc_profile'}, len(icc_profile) if icc_profile else 0)

            resized.save(tmp_destination, **save_kwargs)
            os.replace(tmp_destination, destination_path)
    except UnidentifiedImageError as exc:
        return f'downloaded file is not a valid image: {exc}'
    except ValueError as exc:
        return f'failed converting or saving icon: {exc}'
    finally:
        remove_temp_file(tmp_destination)
    return None

def remove_temp_file(temp_path):
    """delete a temporary file and log a warning on cleanup failure"""
    if temp_path and os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except (FileNotFoundError, PermissionError) as exc:
            logging.warning('failed to remove temporary file %s: %s', temp_path, exc)

# Per-entry processing
def process_single_icon(session, software, yaml_stem, icon_path, output_directory, options):
    """download and process a single software icon entry"""
    icon_url = software.get('icon_url')

    if not icon_url:
        return 'skipped_no_icon_url'
    if options['skip_when_icon_present'] and icon_path.exists():
        return 'skipped_existing_icon'
    logging.debug('processing entry stem=%s name=%r icon_url=%s -> %s', yaml_stem, software.get('name'), icon_url, icon_path)

    head_error = preflight_head(session, icon_url, options['request_timeout'], options['max_download_bytes'], options['allowed_mime_types'])
    if head_error is not None:
        return head_error

    temp_path = None
    try:
        temp_path, server_mime, download_error = download_icon_to_temp(session, icon_url, output_directory, options['request_timeout'], options['max_download_bytes'], options['allowed_mime_types'])
        if download_error is not None:
            return download_error

        conversion_error = convert_image_to_webp(
            temp_path, str(icon_path), options['output_size'],
            options['allowed_image_formats'], server_mime, options['allowed_image_types'],
            options['max_image_pixels'], options['webp_quality'], options['webp_method'])
        if conversion_error is not None:
            return conversion_error

    finally:
        remove_temp_file(temp_path)
    logging.info('saved icon for %s at %s', software.get('name', yaml_stem), icon_path)
    return 'downloaded'

# Main function
def download_icons(step):
    """download and normalize software icons from icon_url fields"""
    errors = []
    source_directory = get_module_option(step, 'source_directory', None)
    if not source_directory:
        logging.error('module option source_directory is required')
        sys.exit(1)
    output_directory = get_module_option(step, 'output_directory', f'{source_directory}/icons')
    allowed_mime_types = {mime.casefold() for mimes in ALLOWED_IMAGE_TYPES.values() for mime in mimes}
    allowed_image_formats = set(ALLOWED_IMAGE_TYPES)
    options = {
        'request_timeout': get_module_option(step, 'request_timeout', DEFAULT_REQUEST_TIMEOUT),
        'max_download_bytes': get_module_option(step, 'max_download_bytes', DEFAULT_MAX_DOWNLOAD_BYTES),
        'max_image_pixels': get_module_option(step, 'max_image_pixels', DEFAULT_MAX_IMAGE_PIXELS),
        'skip_when_icon_present': get_module_option(step, 'skip_when_icon_present', DEFAULT_SKIP_WHEN_ICON_PRESENT),
        'output_size': get_module_option(step, 'output_size', DEFAULT_OUTPUT_SIZE),
        'webp_quality': get_module_option(step, 'webp_quality', DEFAULT_WEBP_QUALITY),
        'webp_method': get_module_option(step, 'webp_method', DEFAULT_WEBP_METHOD),
        'allowed_mime_types': allowed_mime_types,
        'allowed_image_formats': allowed_image_formats,
        'allowed_image_types': ALLOWED_IMAGE_TYPES,
    }

    Path(output_directory).mkdir(parents=True, exist_ok=True)
    software_entries = iter_software_entries_with_stem(source_directory)
    if not software_entries:
        logging.error('software directory does not exist or is empty: %s/software', source_directory)
        sys.exit(1)
    logging.debug('processing %s software YAML entries for icon downloads', len(software_entries))
    session = build_retrying_session(
        get_module_option(step, 'retry_total', DEFAULT_RETRY_TOTAL),
        get_module_option(step, 'retry_backoff_factor', DEFAULT_RETRY_BACKOFF_FACTOR),
        get_module_option(step, 'retry_status_forcelist', DEFAULT_RETRY_STATUS_FORCELIST),
    )
    processed_count = 0
    skipped_count = 0
    error_count = 0

    for software, yaml_stem, yaml_path in software_entries:
        icon_path = Path(output_directory) / f'{yaml_stem}.webp'
        result = process_single_icon(session, software, yaml_stem, icon_path, output_directory, options)
        if result == 'downloaded':
            processed_count += 1
        elif result.startswith('skipped_'):
            skipped_count += 1
            logging.debug('%s: %s', yaml_path, result)
        else:
            error_count += 1
            error_msg = f'{yaml_path}: {result}'
            logging.error(error_msg)
            errors.append(error_msg)
    logging.info('icon processing complete. Downloaded: %s - Skipped: %s - Errors: %s', processed_count, skipped_count, error_count)

    if errors:
        logging.error("errors occurred during processing")
        print('\n'.join(errors))
        sys.exit(1)
