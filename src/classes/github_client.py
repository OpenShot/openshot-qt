"""
GitHub API client for repository data extraction.

This module is logic-only (no Qt). Call it from worker threads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from classes.logger import log

DEFAULT_GITHUB_API = "https://api.github.com"


@dataclass(frozen=True)
class GitHubError(Exception):
    """Structured error for GitHub API failures."""

    message: str
    status_code: Optional[int] = None
    detail: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        bits = [self.message]
        if self.status_code is not None:
            bits.append(f"(status={self.status_code})")
        if self.detail:
            bits.append(self.detail)
        return " ".join(bits)


def _auth_headers(token: str = "") -> Dict[str, str]:
    """Build authentication headers for GitHub API."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    tok = (token or "").strip()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return headers


def _parse_json_response(resp) -> Any:
    try:
        return resp.json()
    except Exception:
        # Fallback: show small slice of raw text for debugging
        text = getattr(resp, "text", "") or ""
        raise GitHubError(
            "Failed to parse JSON response.",
            status_code=getattr(resp, "status_code", None),
            detail=text[:500]
        )


def _raise_for_status(resp) -> None:
    if 200 <= int(resp.status_code) < 300:
        return

    status = int(resp.status_code)
    data = None
    detail = None
    try:
        data = _parse_json_response(resp)
        if isinstance(data, dict) and "message" in data:
            detail = str(data.get("message") or "")
    except Exception:
        # ignore parse failures; will fall back to resp.text
        pass
    if not detail:
        detail = (getattr(resp, "text", "") or "")[:500]

    # Provide helpful error messages for common status codes
    if status == 401:
        raise GitHubError(
            "Authentication failed. Your GitHub token may be invalid.",
            status_code=status,
            detail=detail
        )
    elif status == 403:
        raise GitHubError(
            "Access denied or rate limit exceeded. You may need a GitHub token.",
            status_code=status,
            detail=detail
        )
    elif status == 404:
        raise GitHubError(
            "Repository not found. Check the owner and repo name.",
            status_code=status,
            detail=detail
        )
    elif status == 400:
        raise GitHubError(
            "Bad request. Check your parameters.",
            status_code=status,
            detail=detail
        )
    else:
        raise GitHubError(
            "GitHub API request failed.",
            status_code=status,
            detail=detail
        )


def parse_github_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse a GitHub URL to extract owner and repo name.

    Args:
        url: GitHub URL (e.g., "https://github.com/facebook/react")

    Returns:
        Tuple of (owner, repo) or (None, None) if parsing fails

    Examples:
        >>> parse_github_url("https://github.com/facebook/react")
        ('facebook', 'react')
        >>> parse_github_url("github.com/openai/gpt-4")
        ('openai', 'gpt-4')
        >>> parse_github_url("facebook/react")
        ('facebook', 'react')
    """
    url = (url or "").strip()
    if not url:
        return None, None

    # Remove protocol if present
    url = re.sub(r'^https?://', '', url)
    # Remove github.com/ if present
    url = re.sub(r'^github\.com/', '', url)
    # Remove .git suffix if present
    url = re.sub(r'\.git$', '', url)
    # Remove trailing slashes
    url = url.rstrip('/')

    # Split by '/' and take first two parts
    parts = url.split('/')
    if len(parts) >= 2:
        owner = parts[0].strip()
        repo = parts[1].strip()
        if owner and repo:
            return owner, repo

    return None, None


def get_repo_info(
    owner: str,
    repo: str,
    token: str = "",
    base_url: str = DEFAULT_GITHUB_API,
    timeout_seconds: float = 30.0,
) -> Dict[str, Any]:
    """
    Fetch repository metadata from GitHub API.

    Args:
        owner: Repository owner (username or organization)
        repo: Repository name
        token: GitHub personal access token (optional, but recommended for rate limits)
        base_url: GitHub API base URL (defaults to public API)
        timeout_seconds: Request timeout in seconds

    Returns:
        Dictionary with repository metadata including:
        - name: repo name
        - full_name: owner/repo
        - description: repo description
        - html_url: GitHub page URL
        - stargazers_count: number of stars
        - forks_count: number of forks
        - watchers_count: number of watchers
        - language: primary language
        - topics: list of topic tags
        - created_at: creation date
        - updated_at: last update date
        - homepage: project homepage URL
        - license: license info (if present)

    Raises:
        GitHubError: If the request fails
    """
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    if not owner or not repo:
        raise GitHubError("Owner and repo are required.")

    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise GitHubError("requests library is required.") from exc

    url = f"{base_url}/repos/{owner}/{repo}"
    headers = _auth_headers(token)

    try:
        resp = requests.get(url, headers=headers, timeout=float(timeout_seconds))
    except requests.RequestException as exc:
        raise GitHubError(f"GitHub API request failed: {exc}") from exc

    _raise_for_status(resp)
    data = _parse_json_response(resp)

    if not isinstance(data, dict):
        raise GitHubError(
            "Unexpected repo info response format.",
            status_code=int(resp.status_code),
            detail=str(data)[:500]
        )

    return data


def get_readme(
    owner: str,
    repo: str,
    token: str = "",
    base_url: str = DEFAULT_GITHUB_API,
    timeout_seconds: float = 30.0,
) -> str:
    """
    Fetch README content from GitHub API.

    Args:
        owner: Repository owner
        repo: Repository name
        token: GitHub personal access token (optional)
        base_url: GitHub API base URL
        timeout_seconds: Request timeout in seconds

    Returns:
        README content as plain text (markdown)

    Raises:
        GitHubError: If the request fails or README not found
    """
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    if not owner or not repo:
        raise GitHubError("Owner and repo are required.")

    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise GitHubError("requests library is required.") from exc

    url = f"{base_url}/repos/{owner}/{repo}/readme"
    headers = _auth_headers(token)
    # Request raw markdown content instead of JSON
    headers["Accept"] = "application/vnd.github.raw+json"

    try:
        resp = requests.get(url, headers=headers, timeout=float(timeout_seconds))
    except requests.RequestException as exc:
        raise GitHubError(f"GitHub API request failed: {exc}") from exc

    _raise_for_status(resp)

    # Response is raw text (markdown)
    return resp.text


def get_repo_data_from_url(
    repo_url: str,
    token: str = "",
    base_url: str = DEFAULT_GITHUB_API,
    timeout_seconds: float = 30.0,
) -> Dict[str, Any]:
    """
    Convenience function: parse GitHub URL and fetch all repo data.

    Args:
        repo_url: GitHub repository URL (any format)
        token: GitHub personal access token (optional)
        base_url: GitHub API base URL
        timeout_seconds: Request timeout in seconds

    Returns:
        Dictionary with:
        - repo_info: Repository metadata
        - readme: README content (or empty string if not found)
        - owner: Repository owner
        - repo: Repository name

    Raises:
        GitHubError: If URL parsing fails or API request fails
    """
    owner, repo = parse_github_url(repo_url)
    if not owner or not repo:
        raise GitHubError(
            f"Could not parse GitHub URL: {repo_url}",
            detail="Expected format: github.com/owner/repo or owner/repo"
        )

    repo_info = get_repo_info(owner, repo, token, base_url, timeout_seconds)

    # Try to get README, but don't fail if it doesn't exist
    readme = ""
    try:
        readme = get_readme(owner, repo, token, base_url, timeout_seconds)
    except GitHubError as e:
        if e.status_code == 404:
            log.warning("README not found for %s/%s", owner, repo)
            readme = ""
        else:
            raise

    return {
        "repo_info": repo_info,
        "readme": readme,
        "owner": owner,
        "repo": repo,
    }
