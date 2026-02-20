"""
Vision Analysis Service

Coordinates vision analysis for timeline clips using AI vision models.
Provides caching and on-demand analysis to avoid expensive re-analysis.
"""

import os
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from classes.logger import log
from classes.media_analyzer import MediaAnalyzer
from classes.query import Clip, File
from classes.app import get_app


class VisionAnalysisService:
    """Coordinates vision analysis for timeline clips"""

    def __init__(self):
        """Initialize vision analysis service"""
        self.media_analyzer = MediaAnalyzer()

    def is_available(self) -> bool:
        """
        Check if vision analysis is available

        Returns:
            True if vision analysis is enabled and configured
        """
        try:
            s = get_app().get_settings()

            # Check if vision analysis is enabled
            if not s.get('ai-vision-enabled'):
                return False

            # Check if media analyzer is available
            if not self.media_analyzer.is_available():
                return False

            return True

        except Exception as e:
            log.error(f"Failed to check vision availability: {e}")
            return False

    async def analyze_clip_visual_content(self, clip_id: str) -> Optional[Dict[str, Any]]:
        """
        Analyze visual content of a clip using vision models

        Args:
            clip_id: ID of the clip to analyze

        Returns:
            Dictionary with vision analysis results, or None if unavailable
        """
        try:
            # Get clip
            clip = Clip.get(id=clip_id)
            if not clip:
                log.warning(f"Clip not found: {clip_id}")
                return None

            # Get file reference
            file_id = clip.data.get("file_id")
            if not file_id:
                # Try to get from reader
                reader = clip.data.get("reader", {})
                file_path = reader.get("path")
                if file_path:
                    # Find file by path
                    files = File.filter()
                    for f in files:
                        if f.data.get("path") == file_path:
                            file_id = f.id
                            break

            if not file_id:
                log.warning(f"No file reference found for clip: {clip_id}")
                return None

            # Analyze file
            return await self.analyze_file_visual_content(file_id)

        except Exception as e:
            log.error(f"Failed to analyze clip {clip_id}: {e}", exc_info=True)
            return None

    async def analyze_file_visual_content(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Analyze visual content of a file using vision models

        Args:
            file_id: ID of the file to analyze

        Returns:
            Dictionary with vision analysis results, or None if unavailable
        """
        try:
            # Get file
            file_obj = File.get(id=file_id)
            if not file_obj:
                log.warning(f"File not found: {file_id}")
                return None

            # Check if already analyzed with vision
            cached = self.get_cached_analysis(file_id)
            if cached:
                log.debug(f"Using cached vision analysis for file: {file_id}")
                return cached

            # Get file path
            file_path = file_obj.data.get("path")
            if not file_path:
                log.warning(f"No path found for file: {file_id}")
                return None

            # Make path absolute
            file_path = file_obj.absolute_path()

            # Check if file exists
            if not os.path.exists(file_path):
                log.warning(f"File does not exist: {file_path}")
                return None

            # Get frame count from settings
            s = get_app().get_settings()
            num_frames = s.get('ai-vision-frame-count', 5)

            log.info(f"Extracting {num_frames} frames from {file_path}")

            # Extract frames
            frame_paths = self.media_analyzer.extract_video_frames(file_path, num_frames)

            if not frame_paths:
                log.warning(f"No frames extracted from {file_path}")
                return None

            try:
                log.info(f"Analyzing {len(frame_paths)} frames with vision model")

                # Analyze frames with vision model
                provider = self.media_analyzer.provider
                if not provider:
                    log.warning("No AI provider available")
                    return None

                result = await provider.analyze_video_frames(frame_paths)

                if not result:
                    log.warning("No result from vision analysis")
                    return None

                # Convert to metadata format with vision extensions
                metadata = self._result_to_vision_metadata(result)

                # Store in File.ai_metadata
                if 'ai_metadata' not in file_obj.data:
                    file_obj.data['ai_metadata'] = {}

                # Merge with existing metadata
                file_obj.data['ai_metadata'].update(metadata)
                file_obj.save()

                log.info(f"Vision analysis complete and saved for file: {file_id}")

                return metadata

            finally:
                # Clean up temporary frames
                for frame_path in frame_paths:
                    try:
                        if os.path.exists(frame_path):
                            os.remove(frame_path)
                            log.debug(f"Cleaned up temp frame: {frame_path}")
                    except Exception as e:
                        log.warning(f"Failed to cleanup frame {frame_path}: {e}")

        except Exception as e:
            log.error(f"Failed to analyze file {file_id}: {e}", exc_info=True)
            return None

    def get_cached_analysis(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached vision analysis from File.ai_metadata

        Args:
            file_id: ID of the file

        Returns:
            Cached analysis dictionary, or None if not available
        """
        try:
            s = get_app().get_settings()

            # Check if caching is enabled
            if not s.get('ai-vision-cache-enabled', True):
                return None

            file_obj = File.get(id=file_id)
            if not file_obj:
                return None

            ai_metadata = file_obj.data.get('ai_metadata', {})

            # Check if has vision analysis
            if not ai_metadata.get('has_vision_analysis'):
                return None

            # Return cached analysis
            return ai_metadata

        except Exception as e:
            log.error(f"Failed to get cached analysis for {file_id}: {e}")
            return None

    def _result_to_vision_metadata(self, result) -> Dict[str, Any]:
        """
        Convert AnalysisResult to metadata dictionary with vision extensions

        Args:
            result: AnalysisResult object from provider

        Returns:
            Metadata dictionary with vision_analysis field
        """
        # Extract quality scores for vision analysis
        quality_scores = result.quality_scores if hasattr(result, 'quality_scores') else {}

        # Build vision_analysis structure
        vision_analysis = {
            "composition": {
                "framing_score": quality_scores.get('composition_score', 0.0),
                "lighting_score": quality_scores.get('lighting_score', 0.0),
                "color_harmony_score": quality_scores.get('color_harmony', 0.0)
            },
            "visual_quality": {
                "blur_detected": quality_scores.get('blur_detected', False),
                "exposure_issues": quality_scores.get('exposure_issues', False),
                "resolution_appearance": quality_scores.get('resolution', 'medium')
            },
            "aesthetic": {
                "overall_appeal": quality_scores.get('aesthetic_score', 0.0),
                "style": result.mood if hasattr(result, 'mood') else []
            }
        }

        return {
            "analyzed": True,
            "analysis_version": "2.0",
            "analysis_date": datetime.now().isoformat(),
            "provider": result.provider if hasattr(result, 'provider') else "unknown",
            "has_vision_analysis": True,
            "vision_analysis": vision_analysis,
            "tags": {
                "objects": result.objects if hasattr(result, 'objects') else [],
                "scenes": result.scenes if hasattr(result, 'scenes') else [],
                "activities": result.activities if hasattr(result, 'activities') else [],
                "mood": result.mood if hasattr(result, 'mood') else [],
                "quality": quality_scores
            },
            "faces": result.faces if hasattr(result, 'faces') else [],
            "colors": result.colors if hasattr(result, 'colors') else {},
            "description": result.description if hasattr(result, 'description') else "",
            "confidence": result.confidence if hasattr(result, 'confidence') else 0.0
        }


# Global service instance
_vision_service = None

def get_vision_service() -> VisionAnalysisService:
    """Get global vision analysis service instance"""
    global _vision_service
    if _vision_service is None:
        _vision_service = VisionAnalysisService()
    return _vision_service
