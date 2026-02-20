"""
QThread worker for Remotion video rendering.
Offloads network and rendering work from the main Qt thread.
"""

from __future__ import annotations

from classes.logger import log

try:
    from PyQt5.QtCore import QThread, pyqtSignal
except ImportError:
    QThread = None
    pyqtSignal = None


class RemotionRenderThread(QThread if QThread else object):
    """Worker thread: calls Remotion API for video rendering"""

    if pyqtSignal is not None:
        finished_with_result = pyqtSignal(dict, str)  # result_dict, error_or_empty
        progress_update = pyqtSignal(int, str)  # progress (0-100), status message

    def __init__(
        self,
        api_key: str,
        mode: str,  # "sonar" or "repo"
        base_url: str,
        timeout_seconds: int = 300,
        **kwargs
    ):
        """
        Initialize worker thread

        Args:
            api_key: Remotion API key
            mode: "sonar" or "repo"
            base_url: Remotion API base URL
            timeout_seconds: Maximum render timeout
            **kwargs: Mode-specific parameters

        For "sonar" mode, kwargs should include:
            - query: str
            - sonar_data: dict
            - visualization_style: str (optional)
            - duration: int (optional)
            - theme: dict (optional)

        For "repo" mode, kwargs should include:
            - repo_url: str
            - template: str
            - user_input: str (optional)
            - codec: str (optional)
        """
        if QThread is not None:
            super().__init__()

        self._api_key = api_key
        self._mode = mode
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._kwargs = kwargs

    def run(self):
        """Execute the render operation"""
        from classes.video_generation.remotion_client import (
            RemotionError,
            render_from_sonar,
            render_from_repo,
        )

        try:
            log.info(f"Starting Remotion render (mode: {self._mode})")

            # Progress callback
            def on_progress(progress: int, status: str):
                if pyqtSignal is not None:
                    self.progress_update.emit(progress, status)
                log.info(f"Render progress: {progress}% - {status}")

            result = None

            if self._mode == "sonar":
                # Sonar visualization render
                result = render_from_sonar(
                    api_key=self._api_key,
                    query=self._kwargs.get('query', ''),
                    sonar_data=self._kwargs.get('sonar_data', {}),
                    visualization_style=self._kwargs.get('visualization_style', 'research-summary'),
                    duration=self._kwargs.get('duration'),
                    theme=self._kwargs.get('theme'),
                    base_url=self._base_url,
                    timeout_seconds=self._timeout_seconds,
                    poll_callback=on_progress,
                )

            elif self._mode == "repo":
                # Repository video render
                result = render_from_repo(
                    api_key=self._api_key,
                    repo_url=self._kwargs.get('repo_url', ''),
                    template=self._kwargs.get('template', 'default'),
                    user_input=self._kwargs.get('user_input'),
                    codec=self._kwargs.get('codec', 'h264'),
                    base_url=self._base_url,
                    timeout_seconds=self._timeout_seconds,
                    poll_callback=on_progress,
                )

            else:
                raise ValueError(f"Invalid mode: {self._mode}")

            # Success
            log.info(f"Remotion render completed: {result.get('jobId')}")
            if pyqtSignal is not None:
                self.finished_with_result.emit(result, "")

        except RemotionError as e:
            log.error(f"Remotion render failed: {e}")
            if pyqtSignal is not None:
                self.finished_with_result.emit({}, str(e))

        except Exception as e:
            log.error(f"Unexpected error in Remotion render: {e}")
            if pyqtSignal is not None:
                self.finished_with_result.emit({}, f"Unexpected error: {str(e)}")
