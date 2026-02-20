"""
Perplexity research tools for Flowcut agents.

These tools are designed to be run on the Qt main thread (like ai_openshot_tools),
but they offload network + download work to a QThread.
"""

from __future__ import annotations

import os
import uuid as uuid_module

from classes.logger import log

try:
    from PyQt5.QtCore import QObject, QThread, pyqtSignal, QEventLoop
except ImportError:
    QObject = object
    QThread = None
    pyqtSignal = None
    QEventLoop = None


def _get_app():
    """Get app; must be called from main thread."""
    from classes.app import get_app

    return get_app()


def _output_dir_for_research() -> str:
    """Return an absolute directory path for saving research images. Call from main thread."""
    app = _get_app()
    project_path = getattr(app.project, "current_filepath", None) or ""
    if project_path and os.path.isabs(project_path):
        base_dir = os.path.dirname(project_path)
        out_dir = os.path.join(base_dir, "Generated", f"research_{uuid_module.uuid4().hex[:8]}")
        try:
            os.makedirs(out_dir, exist_ok=True)
            return out_dir
        except OSError:
            pass
    import tempfile

    temp_dir = os.path.join(tempfile.gettempdir(), f"flowcut_research_{uuid_module.uuid4().hex[:8]}")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def _try_get_file_id_for_path(path: str):
    """Try to resolve a File id after adding a path to the files model."""
    from classes.query import File

    f = File.get(path=path)
    if not f:
        f = File.get(path=os.path.normpath(path))
    if not f:
        for candidate in File.filter():
            if getattr(candidate, "absolute_path", None) and candidate.absolute_path() == path:
                f = candidate
                break
    return getattr(f, "id", None)


class _ResearchThread(QThread if QThread else object):
    """Worker thread: calls Perplexity API, downloads images."""

    if pyqtSignal is not None:
        finished_with_result = pyqtSignal(dict, str)  # result_dict, error_or_empty
        progress_update = pyqtSignal(str)  # status messages

    def __init__(
        self,
        api_key: str,
        query: str,
        model: str,
        max_images: int,
        dest_dir: str,
        search_domain_filter: list,
        search_recency_filter: str,
        timeout_seconds: float,
        operation_type: str = "search",  # "search" or "plan"
        content_type: str = "video",
        aspects: str = "",
    ):
        if QThread is not None:
            super().__init__()
        self._api_key = api_key
        self._query = query
        self._model = model
        self._max_images = max_images
        self._dest_dir = dest_dir
        self._search_domain_filter = search_domain_filter
        self._search_recency_filter = search_recency_filter
        self._timeout_seconds = timeout_seconds
        self._operation_type = operation_type
        self._content_type = content_type
        self._aspects = aspects

    def run(self):
        from classes.research_generation.perplexity_client import (
            PerplexityError,
            research_and_download_images,
            perplexity_search,
        )

        try:
            if self._operation_type == "search":
                # Full search with image downloads
                result = research_and_download_images(
                    api_key=self._api_key,
                    query=self._query,
                    max_images=self._max_images,
                    dest_dir=self._dest_dir,
                    model=self._model,
                    search_domain_filter=self._search_domain_filter,
                    search_recency_filter=self._search_recency_filter,
                    timeout_seconds=self._timeout_seconds,
                )
            else:
                # Content planning: search without images or with fewer images
                # Build structured query based on content_type and aspects
                query = self._query
                if self._aspects:
                    aspects_list = [a.strip() for a in self._aspects.split(",") if a.strip()]
                    query_parts = [self._query]

                    if "visuals" in aspects_list:
                        query_parts.append("visual style cinematography")
                    if "colors" in aspects_list:
                        query_parts.append("color palette grading")
                    if "sounds" in aspects_list:
                        query_parts.append("sound design music score")
                    if "transitions" in aspects_list:
                        query_parts.append("editing transitions effects")
                    if "mood" in aspects_list:
                        query_parts.append("mood atmosphere pacing")

                    query = " ".join(query_parts)

                # Simple search without extensive image downloads
                search_result = perplexity_search(
                    api_key=self._api_key,
                    query=query,
                    model=self._model,
                    return_images=True,
                    return_related_questions=True,
                    search_domain_filter=self._search_domain_filter,
                    search_recency_filter=self._search_recency_filter,
                    timeout_seconds=self._timeout_seconds,
                )

                result = {
                    "summary": search_result.get("content", ""),
                    "citations": search_result.get("citations", []),
                    "image_paths": [],
                    "downloaded_images": [],
                    "failed_images": [],
                    "related_questions": search_result.get("related_questions", []),
                }

            if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit(result, "")
        except PerplexityError as exc:
            if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit({}, str(exc))
        except Exception as exc:
            log.error("Research operation failed: %s", exc, exc_info=True)
            if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit({}, str(exc))


def research_web_and_display(
    *,
    query: str = "",
    max_images: int = "3",
    add_images_to_timeline: str = "false",
    position_seconds: str = "",
    search_domain_filter: str = "",
    search_recency_filter: str = "",
    timeout_seconds: str = "120",
) -> str:
    """
    Search the web using Perplexity, get images, and display results in chat.

    Args:
        query: Search query (required)
        max_images: Number of images to download (0-10, default 3)
        add_images_to_timeline: "true" to add images as clips to timeline (default "false")
        position_seconds: Timeline position (empty = playhead)
        search_domain_filter: Comma-separated domains (e.g., "wikipedia.org,imdb.com")
        search_recency_filter: Filter by recency ("month", "week", "day", or empty)
        timeout_seconds: Operation timeout (default 120)

    Returns:
        Formatted research summary with citations and image information.
    """
    if QThread is None or QEventLoop is None:
        return "Error: Research requires PyQt5."

    query_str = (query or "").strip()
    if not query_str:
        return "Error: Query is required for research."

    app = _get_app()
    settings = app.get_settings()

    api_key = (settings.get("perplexity-api-key") or "").strip()
    if not api_key:
        return "Perplexity is not configured. Add your Perplexity API key in Preferences > AI (Perplexity API Key)."

    model = (settings.get("perplexity-model") or "").strip() or "sonar-pro"

    # Parse max_images
    try:
        max_imgs = int(max_images) if str(max_images).strip() else 3
        max_imgs = max(0, min(10, max_imgs))  # Clamp to 0-10
    except Exception:
        max_imgs = 3

    # Parse domain filter
    domain_filter = []
    if (search_domain_filter or "").strip():
        domain_filter = [d.strip() for d in search_domain_filter.split(",") if d.strip()]

    # Parse timeout
    try:
        timeout_f = float(timeout_seconds) if str(timeout_seconds).strip() else 120.0
    except Exception:
        timeout_f = 120.0

    # Create output directory for images
    dest_dir = _output_dir_for_research()

    log.info("Perplexity research: query='%s', max_images=%d, model=%s", query_str, max_imgs, model)

    result_holder = [None, None]  # [result_dict, error]
    loop_holder = [None]

    class _DoneReceiver(QObject if QObject is not object else object):
        def on_done(self, result, error):
            result_holder[0] = result
            result_holder[1] = error
            if loop_holder[0]:
                loop_holder[0].quit()

    receiver = _DoneReceiver()
    thread = _ResearchThread(
        api_key=api_key,
        query=query_str,
        model=model,
        max_images=max_imgs,
        dest_dir=dest_dir,
        search_domain_filter=domain_filter,
        search_recency_filter=(search_recency_filter or "").strip(),
        timeout_seconds=timeout_f,
        operation_type="search",
    )
    thread.finished_with_result.connect(receiver.on_done)

    loop_holder[0] = QEventLoop(app)
    status_bar = getattr(app.window, "statusBar", None)
    try:
        if status_bar is not None:
            status_bar.showMessage("Researching...", 0)
        thread.start()
        loop_holder[0].exec_()
    finally:
        if status_bar is not None:
            status_bar.clearMessage()

    thread.quit()
    thread.wait(10000)
    try:
        thread.finished_with_result.disconnect(receiver.on_done)
    except Exception:
        pass

    result, error = result_holder[0], result_holder[1]
    if error:
        log.error("Research error: %s", error)
        return f"Research failed: {error}"

    # Format response
    summary = result.get("summary", "")
    citations = result.get("citations", [])
    downloaded_images = result.get("downloaded_images", [])
    failed_images = result.get("failed_images", [])
    related_questions = result.get("related_questions", [])

    output_parts = []

    # Summary
    if summary:
        output_parts.append(summary)

    # Images
    if downloaded_images:
        output_parts.append(f"\n**IMAGES FOUND:** {len(downloaded_images)} image(s) downloaded")
        for i, img in enumerate(downloaded_images, 1):
            desc = img.get("description", "Image")
            output_parts.append(f"{i}. {desc}")

        # Optionally add images to timeline
        add_to_timeline = (add_images_to_timeline or "").strip().lower() in ("true", "1", "yes", "y")
        if add_to_timeline:
            output_parts.append("\n**ADDING IMAGES TO TIMELINE:**")
            from classes.ai_openshot_tools import add_clip_to_timeline

            for img in downloaded_images:
                img_path = img.get("path", "")
                if not img_path or not os.path.isfile(img_path):
                    continue

                # Import image into project
                try:
                    app.window.files_model.add_files([img_path])
                except Exception as exc:
                    log.error("Failed to import image: %s", exc, exc_info=True)
                    output_parts.append(f"- Error importing {os.path.basename(img_path)}")
                    continue

                file_id = _try_get_file_id_for_path(img_path)
                if not file_id:
                    output_parts.append(f"- Error: Could not resolve {os.path.basename(img_path)}")
                    continue

                # Add to timeline
                msg = add_clip_to_timeline(
                    file_id=str(file_id),
                    position_seconds=position_seconds or "",
                    track=""
                )
                if isinstance(msg, str) and not msg.startswith("Error:"):
                    output_parts.append(f"- Added {os.path.basename(img_path)} to timeline")
                else:
                    output_parts.append(f"- Error adding {os.path.basename(img_path)}: {msg}")

    if failed_images:
        output_parts.append(f"\n**Note:** {len(failed_images)} image(s) could not be downloaded")

    # Citations
    if citations:
        output_parts.append("\n**SOURCES:**")
        for i, url in enumerate(citations, 1):
            output_parts.append(f"{i}. {url}")

    # Related questions
    if related_questions:
        output_parts.append("\n**RELATED QUESTIONS:**")
        for q in related_questions:
            output_parts.append(f"- {q}")

    if not output_parts:
        return "Research completed but no results were found."

    return "\n".join(output_parts)


def research_for_content_planning(
    *,
    topic: str = "",
    content_type: str = "video",
    aspects: str = "",  # comma-separated: "visuals,colors,sounds,transitions,mood"
    timeout_seconds: str = "90",
) -> str:
    """
    Research a topic and return actionable content suggestions.

    Use this for intelligent content planning (e.g., "Stranger Things theme").

    Args:
        topic: Topic to research (required)
        content_type: Type of content ("video", "music", "aesthetic")
        aspects: Comma-separated aspects to focus on (e.g., "visuals,colors,sounds,transitions,mood")
        timeout_seconds: Operation timeout (default 90)

    Returns:
        Structured suggestions:
        - Visual style recommendations
        - Color palette suggestions
        - Sound/music suggestions
        - Transition effects recommendations
        - Mood and pacing guidance
    """
    if QThread is None or QEventLoop is None:
        return "Error: Research requires PyQt5."

    topic_str = (topic or "").strip()
    if not topic_str:
        return "Error: Topic is required for content planning."

    app = _get_app()
    settings = app.get_settings()

    api_key = (settings.get("perplexity-api-key") or "").strip()
    if not api_key:
        return "Perplexity is not configured. Add your Perplexity API key in Preferences > AI (Perplexity API Key)."

    model = (settings.get("perplexity-model") or "").strip() or "sonar-pro"

    # Parse timeout
    try:
        timeout_f = float(timeout_seconds) if str(timeout_seconds).strip() else 90.0
    except Exception:
        timeout_f = 90.0

    # Create output directory (though we won't download many images)
    dest_dir = _output_dir_for_research()

    log.info("Content planning research: topic='%s', content_type=%s, aspects=%s", topic_str, content_type, aspects)

    result_holder = [None, None]  # [result_dict, error]
    loop_holder = [None]

    class _DoneReceiver(QObject if QObject is not object else object):
        def on_done(self, result, error):
            result_holder[0] = result
            result_holder[1] = error
            if loop_holder[0]:
                loop_holder[0].quit()

    receiver = _DoneReceiver()
    thread = _ResearchThread(
        api_key=api_key,
        query=topic_str,
        model=model,
        max_images=0,  # Don't download images for content planning
        dest_dir=dest_dir,
        search_domain_filter=[],
        search_recency_filter="",
        timeout_seconds=timeout_f,
        operation_type="plan",
        content_type=content_type,
        aspects=aspects or "",
    )
    thread.finished_with_result.connect(receiver.on_done)

    loop_holder[0] = QEventLoop(app)
    status_bar = getattr(app.window, "statusBar", None)
    try:
        if status_bar is not None:
            status_bar.showMessage(f"Researching {topic_str}...", 0)
        thread.start()
        loop_holder[0].exec_()
    finally:
        if status_bar is not None:
            status_bar.clearMessage()

    thread.quit()
    thread.wait(10000)
    try:
        thread.finished_with_result.disconnect(receiver.on_done)
    except Exception:
        pass

    result, error = result_holder[0], result_holder[1]
    if error:
        log.error("Content planning research error: %s", error)
        return f"Content planning failed: {error}"

    # Format response for content planning
    summary = result.get("summary", "")
    citations = result.get("citations", [])
    related_questions = result.get("related_questions", [])

    output_parts = []

    if summary:
        output_parts.append(f"**{topic_str.upper()} - CONTENT PLANNING**\n")
        output_parts.append(summary)

    if citations:
        output_parts.append("\n**SOURCES:**")
        for i, url in enumerate(citations, 1):
            output_parts.append(f"{i}. {url}")

    # Add actionable suggestions
    output_parts.append("\n**NEXT STEPS:**")
    if "music" in aspects or "sounds" in aspects:
        output_parts.append("- Use the Music Agent to generate background music matching this style")
    if "transitions" in aspects:
        output_parts.append("- Use the Transitions Agent to apply recommended transition effects")
    if "colors" in aspects or "visuals" in aspects:
        output_parts.append("- Apply color grading adjustments using the Video Agent")

    if related_questions:
        output_parts.append("\n**EXPLORE FURTHER:**")
        for q in related_questions[:3]:  # Limit to top 3
            output_parts.append(f"- {q}")

    if not output_parts:
        return "Content planning completed but no recommendations were generated."

    return "\n".join(output_parts)


def test_perplexity_api_key() -> str:
    """Test if the Perplexity API key is configured."""
    app = _get_app()
    settings = app.get_settings()

    api_key = (settings.get("perplexity-api-key") or "").strip()
    model = (settings.get("perplexity-model") or "").strip() or "sonar-pro"

    if not api_key:
        return "Perplexity API key is NOT configured. Please add your API key in Preferences > AI (Perplexity API Key)."

    # Quick validation: API key should be reasonably long
    if len(api_key) < 20:
        return f"Perplexity API key looks invalid (too short: {len(api_key)} chars). Please check your key in Preferences > AI."

    return f"Perplexity is configured (model: {model}). Ready to research!"


def get_research_tools_for_langchain():
    """Return a list of LangChain Tool objects for Perplexity research."""
    from langchain_core.tools import tool

    @tool
    def test_perplexity_api_key_tool() -> str:
        """Check if Perplexity is configured and the API key is set. Use this first if research fails."""
        return test_perplexity_api_key()

    @tool
    def research_web_and_display_tool(
        query: str = "",
        max_images: int = "3",
        add_images_to_timeline: str = "false",
        position_seconds: str = "",
        search_domain_filter: str = "",
        search_recency_filter: str = "",
        timeout_seconds: str = "120",
    ) -> str:
        """
        Search the web using Perplexity, get images, and display results. Use for general research queries.

        - query: Search query (required)
        - max_images: Number of images to download (0-10, default 3)
        - add_images_to_timeline: "true" to add images to timeline (default "false")
        - position_seconds: Timeline position (empty = playhead)
        - search_domain_filter: Comma-separated domains filter (e.g., "wikipedia.org,imdb.com")
        - search_recency_filter: "month", "week", "day", or empty
        - timeout_seconds: Operation timeout (default 120)
        """
        return research_web_and_display(
            query=query,
            max_images=max_images,
            add_images_to_timeline=add_images_to_timeline,
            position_seconds=position_seconds,
            search_domain_filter=search_domain_filter,
            search_recency_filter=search_recency_filter,
            timeout_seconds=timeout_seconds,
        )

    @tool
    def research_for_content_planning_tool(
        topic: str = "",
        content_type: str = "video",
        aspects: str = "",
        timeout_seconds: str = "90",
    ) -> str:
        """
        Research a topic and get actionable content suggestions for video editing. Use when user wants to apply a theme or style.

        - topic: Topic to research (required, e.g., "Stranger Things", "cyberpunk aesthetic")
        - content_type: Type of content ("video", "music", "aesthetic")
        - aspects: Comma-separated aspects (e.g., "visuals,colors,sounds,transitions,mood")
        - timeout_seconds: Operation timeout (default 90)
        """
        return research_for_content_planning(
            topic=topic,
            content_type=content_type,
            aspects=aspects,
            timeout_seconds=timeout_seconds,
        )

    return [
        test_perplexity_api_key_tool,
        research_web_and_display_tool,
        research_for_content_planning_tool,
    ]
