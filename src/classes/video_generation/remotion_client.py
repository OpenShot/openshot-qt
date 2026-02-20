"""
Remotion API client for video generation from Sonar research data and GitHub repositories.
Thread-safe: no Qt, for use from worker thread only.
"""

import time
import requests
from typing import Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass

# Constants
DEFAULT_BASE_URL = "http://localhost:4500/api/v1"
POLL_INTERVAL_SECONDS = 2.0
DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes


@dataclass(frozen=True)
class RemotionError(Exception):
    """Custom error for Remotion API failures"""
    message: str
    status_code: Optional[int] = None
    detail: Optional[str] = None

    def __str__(self):
        if self.status_code:
            return f"RemotionError {self.status_code}: {self.message}"
        return f"RemotionError: {self.message}"


def _norm_base_url(base_url: str) -> str:
    """Normalize base URL by removing trailing slash"""
    return base_url.rstrip('/')


def _auth_headers(api_key: str) -> Dict[str, str]:
    """Generate authentication headers"""
    return {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }


def _parse_json_response(resp: requests.Response) -> Any:
    """Parse JSON response or raise error"""
    try:
        return resp.json()
    except ValueError:
        raise RemotionError(
            f"Invalid JSON response from server",
            status_code=resp.status_code
        )


def _raise_for_status(resp: requests.Response) -> None:
    """Raise appropriate error based on status code"""
    if resp.status_code < 400:
        return

    try:
        error_data = resp.json()
        message = error_data.get('message', resp.text)
        detail = error_data.get('details')
    except ValueError:
        message = resp.text
        detail = None

    if resp.status_code == 401:
        raise RemotionError(
            "Authentication failed. Check your API key.",
            status_code=401,
            detail=detail
        )
    elif resp.status_code == 403:
        raise RemotionError(
            "Access forbidden.",
            status_code=403,
            detail=detail
        )
    elif resp.status_code == 404:
        raise RemotionError(
            "Resource not found.",
            status_code=404,
            detail=detail
        )
    elif resp.status_code == 429:
        raise RemotionError(
            "Rate limit exceeded. Please try again later.",
            status_code=429,
            detail=detail
        )
    elif resp.status_code == 400:
        raise RemotionError(
            f"Bad request: {message}",
            status_code=400,
            detail=detail
        )
    else:
        raise RemotionError(
            f"Server error: {message}",
            status_code=resp.status_code,
            detail=detail
        )


def render_from_sonar(
    *,
    api_key: str,
    query: str,
    sonar_data: Dict[str, Any],
    visualization_style: str = "research-summary",
    duration: Optional[int] = None,
    theme: Optional[Dict[str, str]] = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    poll_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Generate a video from Sonar research data via Remotion API.

    Args:
        api_key: Remotion API key for authentication
        query: Research query/question
        sonar_data: Sonar API response data (content, citations, images, relatedQuestions)
        visualization_style: "research-summary", "data-cards", or "timeline"
        duration: Optional video duration in seconds
        theme: Optional theme dict with backgroundColor and accentColor
        base_url: API base URL
        timeout_seconds: Maximum time to wait for render completion
        poll_callback: Optional callback(progress, status) called during polling

    Returns:
        Dict with 'videoUrl', 'downloadUrl', and 'metadata'

    Raises:
        RemotionError: On API failure or timeout
    """
    if not api_key or not api_key.strip():
        raise RemotionError("API key is required")

    if not query or not query.strip():
        raise RemotionError("Query is required")

    base_url = _norm_base_url(base_url)
    headers = _auth_headers(api_key)

    # Build request payload
    payload = {
        "query": query,
        "sonarData": sonar_data,
        "visualizationStyle": visualization_style,
    }

    if duration or theme:
        payload["options"] = {}
        if duration:
            payload["options"]["duration"] = duration
        if theme:
            payload["options"]["theme"] = theme

    # Submit render job
    try:
        resp = requests.post(
            f"{base_url}/render/sonar",
            json=payload,
            headers=headers,
            timeout=30,
        )
        _raise_for_status(resp)
        data = _parse_json_response(resp)
    except requests.RequestException as e:
        raise RemotionError(f"Network error: {str(e)}")

    job_id = data.get('jobId')
    if not job_id:
        raise RemotionError("Server did not return a job ID")

    # Poll for completion
    return _poll_for_completion(
        api_key=api_key,
        job_id=job_id,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        poll_callback=poll_callback,
    )


def render_from_repo(
    *,
    api_key: str,
    repo_url: str,
    template: str,
    user_input: Optional[str] = None,
    codec: str = "h264",
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    poll_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Generate a video from a GitHub repository via Remotion API.

    Args:
        api_key: Remotion API key for authentication
        repo_url: GitHub repository URL
        template: Template name to use
        user_input: Optional custom user input
        codec: Video codec (h264, h265, vp8, vp9)
        base_url: API base URL
        timeout_seconds: Maximum time to wait for render completion
        poll_callback: Optional callback(progress, status) called during polling

    Returns:
        Dict with 'videoUrl', 'downloadUrl', and 'metadata'

    Raises:
        RemotionError: On API failure or timeout
    """
    if not api_key or not api_key.strip():
        raise RemotionError("API key is required")

    if not repo_url or not repo_url.strip():
        raise RemotionError("Repository URL is required")

    base_url = _norm_base_url(base_url)
    headers = _auth_headers(api_key)

    # Build request payload
    payload = {
        "repoUrl": repo_url,
        "template": template,
    }

    if user_input:
        payload["userInput"] = user_input

    if codec:
        payload["options"] = {"codec": codec}

    # Submit render job
    try:
        resp = requests.post(
            f"{base_url}/render/repo",
            json=payload,
            headers=headers,
            timeout=30,
        )
        _raise_for_status(resp)
        data = _parse_json_response(resp)
    except requests.RequestException as e:
        raise RemotionError(f"Network error: {str(e)}")

    job_id = data.get('jobId')
    if not job_id:
        raise RemotionError("Server did not return a job ID")

    # Poll for completion
    return _poll_for_completion(
        api_key=api_key,
        job_id=job_id,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        poll_callback=poll_callback,
    )


def _poll_for_completion(
    api_key: str,
    job_id: str,
    base_url: str,
    timeout_seconds: int,
    poll_callback: Optional[Callable[[int, str], None]],
) -> Dict[str, Any]:
    """
    Poll job status until completion or timeout

    Returns:
        Dict with video URLs and metadata

    Raises:
        RemotionError: On timeout or job failure
    """
    base_url = _norm_base_url(base_url)
    headers = _auth_headers(api_key)
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            raise RemotionError(
                f"Render timeout after {timeout_seconds}s",
                detail=f"Job ID: {job_id}"
            )

        # Check status
        try:
            resp = requests.get(
                f"{base_url}/jobs/{job_id}/result",
                headers=headers,
                timeout=30,
            )
            _raise_for_status(resp)
            data = _parse_json_response(resp)
        except requests.RequestException as e:
            raise RemotionError(f"Network error while polling: {str(e)}")

        status = data.get('status')

        if status == 'completed':
            # Success!
            return {
                'jobId': job_id,
                'videoUrl': data.get('videoUrl'),
                'downloadUrl': data.get('downloadUrl'),
                'metadata': data.get('metadata'),
                'sceneGraph': data.get('sceneGraph'),
            }

        elif status == 'failed':
            error_msg = data.get('error', 'Render failed')
            raise RemotionError(f"Render failed: {error_msg}")

        elif status == 'processing':
            # Still working
            progress = data.get('progress', 0)
            if poll_callback:
                poll_callback(progress, 'processing')

        else:
            # Unknown status, keep waiting
            pass

        # Wait before next poll
        time.sleep(POLL_INTERVAL_SECONDS)


def download_video(
    *,
    api_key: str,
    job_id: str,
    dest_path: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Tuple[bool, Optional[str]]:
    """
    Download rendered video to local file

    Args:
        api_key: Remotion API key
        job_id: Job ID from render call
        dest_path: Destination file path
        base_url: API base URL
        timeout_seconds: Download timeout

    Returns:
        (success: bool, error_message: Optional[str])
    """
    try:
        base_url = _norm_base_url(base_url)
        headers = _auth_headers(api_key)

        resp = requests.get(
            f"{base_url}/jobs/{job_id}/download",
            headers=headers,
            timeout=timeout_seconds,
            stream=True,
        )
        _raise_for_status(resp)

        with open(dest_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return True, None

    except RemotionError as e:
        return False, str(e)
    except requests.RequestException as e:
        return False, f"Network error: {str(e)}"
    except IOError as e:
        return False, f"File error: {str(e)}"
