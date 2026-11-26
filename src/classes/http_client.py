"""
 @file
 @brief Shared helpers for best-effort HTTP requests in packaged OpenShot builds
 @author OpenShot Studios, LLC

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 """

import os
import ssl
import urllib.request
from urllib.parse import urlparse, urlunparse

import requests

from classes import info
from classes.logger import log


DEFAULT_CONNECT_TIMEOUT = 2
DEFAULT_READ_TIMEOUT = 5
DOWNLOAD_READ_SIZE = 1024 * 1024
URLLIB_ALLOWED_SCHEMES = ("http", "https")


def ca_bundle_path():
    """Return the packaged CA bundle path when available."""
    try:
        import certifi

        cafile = certifi.where()
        if cafile and os.path.exists(cafile):
            return cafile
    except Exception as ex:
        log.debug("Unable to locate certifi CA bundle: %s", ex)
    return None


def configure_ssl_environment():
    """Point common Python HTTP clients at certifi when packaged."""
    cafile = ca_bundle_path()
    if not cafile:
        log.info("No packaged CA bundle detected; using Python/OpenSSL default CA paths")
        return None

    os.environ.setdefault("SSL_CERT_FILE", cafile)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", cafile)
    log.info("Configured packaged CA bundle: %s", cafile)
    return cafile


def ssl_context():
    """Return an SSL context using the packaged CA bundle when available."""
    cafile = ca_bundle_path()
    if cafile:
        return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()


def verify_path():
    """Return a requests-compatible verify value."""
    return ca_bundle_path() or True


def http_fallback_url(url):
    """Return an HTTP fallback URL for an HTTPS URL."""
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        return None
    return urlunparse(parsed._replace(scheme="http"))


def validate_url_scheme(url, allowed_schemes=URLLIB_ALLOWED_SCHEMES):
    """Validate URLs before passing them to urllib helpers."""
    scheme = urlparse(str(url)).scheme.lower()
    if scheme not in allowed_schemes:
        raise ValueError("Unsupported URL scheme: {}".format(scheme or "<empty>"))
    return scheme


def urls_with_http_fallback(url):
    """Return URL attempts in preferred order."""
    urls = [url]
    fallback = http_fallback_url(url)
    if fallback and fallback not in urls:
        urls.append(fallback)
    return urls


def get_json(urls, description, headers=None, timeout=None):
    """Fetch JSON from one or more URLs, logging each fallback attempt."""
    if isinstance(urls, str):
        urls = [urls]
    timeout = timeout or (DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT)
    headers = headers or {}
    last_error = None

    for index, url in enumerate(urls, start=1):
        try:
            log.info("HTTP GET %s attempt %s/%s: %s", description, index, len(urls), url)
            response = requests.get(
                url,
                headers=headers,
                timeout=timeout,
                verify=verify_path(),
            )
            response.raise_for_status()
            log.info("HTTP GET %s succeeded via %s", description, urlparse(url).scheme.upper())
            return response.json()
        except Exception as ex:
            last_error = ex
            log.warning("HTTP GET %s failed via %s: %s", description, url, ex)

    raise RuntimeError("Failed to fetch %s from %s URL(s): %s" % (description, len(urls), last_error))


def post_json(url, payload, description, headers=None, timeout=None):
    """POST JSON with packaged CA handling and logging."""
    timeout = timeout or (DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT)
    headers = headers or {}
    log.info("HTTP POST %s: %s", description, url)
    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=timeout,
        verify=verify_path(),
    )
    response.raise_for_status()
    log.info("HTTP POST %s succeeded with status=%s", description, response.status_code)
    return response


def download_file(urls, output_path, description, progress_callback=None, timeout=None, cancel_exceptions=None):
    """Download one of several URL attempts to disk."""
    if isinstance(urls, str):
        urls = [urls]
    timeout = timeout or (DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT)
    cancel_exceptions = tuple(cancel_exceptions or ())
    last_error = None

    for index, url in enumerate(urls, start=1):
        try:
            log.info("HTTP download %s attempt %s/%s: %s", description, index, len(urls), url)
            _download_file_once(url, output_path, progress_callback, timeout)
            log.info("HTTP download %s succeeded via %s", description, urlparse(url).scheme.upper())
            return url
        except Exception as ex:
            if cancel_exceptions and isinstance(ex, cancel_exceptions):
                log.info("HTTP download %s cancelled", description)
                raise
            last_error = ex
            log.warning("HTTP download %s failed via %s: %s", description, url, ex)
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
            except OSError:
                log.warning("Failed to remove partial download: %s", output_path, exc_info=True)

    raise RuntimeError("Failed to download %s from %s URL(s): %s" % (description, len(urls), last_error))


def _download_file_once(url, output_path, progress_callback, timeout):
    scheme = validate_url_scheme(url)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "OpenShot/{}".format(info.VERSION)},
    )
    kwargs = {"timeout": sum(timeout) if isinstance(timeout, tuple) else timeout}
    if scheme == "https":
        kwargs["context"] = ssl_context()

    with urllib.request.urlopen(request, **kwargs) as response:  # nosec B310 - URL scheme is restricted above.
        total_size = response.headers.get("Content-Length")
        total_size = int(total_size) if total_size else 0
        downloaded_size = 0

        with open(output_path, "wb") as output_file:
            while True:
                chunk = response.read(DOWNLOAD_READ_SIZE)
                if not chunk:
                    break

                output_file.write(chunk)
                downloaded_size += len(chunk)
                if progress_callback:
                    progress_callback(downloaded_size, total_size)
                del chunk  # Release this buffer before the next read allocates another.
