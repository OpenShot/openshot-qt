"""
 @file
 @brief Media analyzer for extracting frames and coordinating AI analysis
 @author Flowcut Development Team

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
 This file is part of OpenShot Video Editor (http://www.openshot.org)
"""

import os
import asyncio
import tempfile
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

import openshot

from classes.logger import log
from classes import info
from classes.app import get_app
from classes.ai_providers import ProviderFactory, ProviderType, AnalysisResult


class MediaAnalyzer:
    """Analyzes media files using AI providers"""
    
    def __init__(self):
        """Initialize media analyzer"""
        self.temp_dir = os.path.join(info.USER_PATH, 'ai_analysis_temp')
        os.makedirs(self.temp_dir, exist_ok=True)
        self.provider = None
        self._init_provider()
    
    def _init_provider(self):
        """Initialize AI provider based on settings"""
        try:
            s = get_app().get_settings()
            
            # Check if AI features are enabled
            if not s.get('ai-enabled'):
                log.info("AI features disabled in settings")
                return
            
            # Get provider type
            provider_type_str = s.get('ai-provider') or 'openai'
            provider_type = ProviderType(provider_type_str)
            
            # Get API credentials
            api_key = None
            provider_config = {}
            
            if provider_type == ProviderType.NVIDIA_EDGE:
                # Import to trigger provider registration
                import classes.ai_providers.nvidia_edge_vision_provider  # noqa: F401
                edge_url = (s.get('nvidia-edge-api-url') or 'http://10.19.183.5:8000/v1').strip()
                api_key = 'not-needed'
                provider_config = {
                    'base_url': edge_url,
                    'model': 'llava',
                    'max_tokens': 1000
                }
            elif provider_type == ProviderType.OPENAI:
                api_key = s.get('openai-api-key')
                provider_config = {
                    'model': 'gpt-4-vision-preview',
                    'max_tokens': 1000
                }
            elif provider_type == ProviderType.GOOGLE:
                provider_config['credentials_path'] = s.get('google-credentials-path')
            elif provider_type == ProviderType.AWS:
                provider_config['access_key_id'] = s.get('aws-access-key-id')
                provider_config['secret_access_key'] = s.get('aws-secret-access-key')
            
            # Create provider
            self.provider = ProviderFactory.create_provider(
                provider_type,
                api_key=api_key,
                **provider_config
            )
            
            if self.provider and self.provider.is_available():
                log.info(f"Media analyzer initialized with {provider_type.value} provider")
            else:
                log.warning("AI provider not properly configured")
                
        except Exception as e:
            log.error(f"Failed to initialize AI provider: {e}")
            self.provider = None
    
    def is_available(self) -> bool:
        """Check if analyzer is available and configured"""
        return self.provider is not None and self.provider.is_available()
    
    def extract_video_frames(self, video_path: str, num_frames: int = 5) -> List[str]:
        """
        Extract frames from video file
        
        Args:
            video_path: Path to video file
            num_frames: Number of frames to extract
        
        Returns:
            List of paths to extracted frame images
        """
        frame_paths = []
        
        try:
            log.debug(f"Extracting {num_frames} frames from {video_path}")
            
            # Open video with libopenshot
            clip = openshot.Clip(video_path)
            reader = clip.Reader()
            
            # Get video duration and calculate frame positions
            duration = reader.info.duration
            fps = reader.info.fps.ToFloat()
            total_frames = int(duration * fps)
            
            if total_frames < num_frames:
                num_frames = total_frames
            
            # Calculate frame positions evenly distributed
            frame_positions = []
            if num_frames > 1:
                step = total_frames / (num_frames - 1)
                frame_positions = [int(i * step) for i in range(num_frames)]
            else:
                frame_positions = [total_frames // 2]
            
            # Extract frames
            for i, frame_num in enumerate(frame_positions):
                try:
                    # Get frame
                    frame = reader.GetFrame(frame_num)
                    
                    # Generate temp filename
                    frame_filename = f"{uuid.uuid4()}_frame_{i}.jpg"
                    frame_path = os.path.join(self.temp_dir, frame_filename)
                    
                    # Save frame as image
                    frame.Save(frame_path, 1.0, "JPG")
                    frame_paths.append(frame_path)
                    
                    log.debug(f"Extracted frame {i} at position {frame_num}")
                    
                except Exception as e:
                    log.warning(f"Failed to extract frame {i}: {e}")
            
            reader.Close()
            
        except Exception as e:
            log.error(f"Failed to extract frames from {video_path}: {e}")
        
        return frame_paths
    
    async def analyze_file(self, file_id: str, file_path: str, media_type: str) -> Dict[str, Any]:
        """
        Analyze a media file and return AI metadata
        
        Args:
            file_id: Unique file ID
            file_path: Path to the media file
            media_type: Type of media (video, image, audio)
        
        Returns:
            Dictionary with AI analysis metadata
        """
        if not self.is_available():
            log.warning("Media analyzer not available, skipping analysis")
            return self._empty_metadata()
        
        log.info(f"Analyzing file: {file_path}")
        
        try:
            result = None
            
            if media_type == 'image':
                # Analyze single image
                result = await self.provider.analyze_image(file_path)
                
            elif media_type == 'video':
                # Extract frames and analyze
                frame_paths = self.extract_video_frames(file_path, num_frames=5)
                
                if frame_paths:
                    result = await self.provider.analyze_video_frames(frame_paths)
                    
                    # Clean up temporary frames
                    for frame_path in frame_paths:
                        try:
                            os.remove(frame_path)
                        except:
                            pass
                else:
                    log.warning("No frames extracted from video")
                    
            elif media_type == 'audio':
                # Audio analysis not yet implemented
                log.info("Audio analysis not yet implemented")
                return self._empty_metadata()
            
            if result:
                # Convert result to metadata format
                metadata = self._result_to_metadata(result)
                log.info(f"Analysis complete for {file_path}")
                return metadata
            else:
                return self._empty_metadata()
                
        except Exception as e:
            log.error(f"Failed to analyze file {file_path}: {e}")
            return self._empty_metadata()
    
    def _result_to_metadata(self, result: AnalysisResult) -> Dict[str, Any]:
        """
        Convert AnalysisResult to metadata dictionary
        
        Args:
            result: AnalysisResult object
        
        Returns:
            Metadata dictionary
        """
        return {
            "analyzed": True,
            "analysis_version": "1.0",
            "analysis_date": datetime.now().isoformat(),
            "provider": result.provider,
            "tags": {
                "objects": result.objects,
                "scenes": result.scenes,
                "activities": result.activities,
                "mood": result.mood,
                "quality": result.quality_scores
            },
            "faces": result.faces,
            "colors": result.colors,
            "audio_analysis": {},
            "description": result.description,
            "confidence": result.confidence
        }
    
    def _empty_metadata(self) -> Dict[str, Any]:
        """Return empty metadata structure"""
        return {
            "analyzed": False,
            "analysis_version": "1.0",
            "analysis_date": datetime.now().isoformat(),
            "provider": "none",
            "tags": {
                "objects": [],
                "scenes": [],
                "activities": [],
                "mood": [],
                "quality": {}
            },
            "faces": [],
            "colors": {},
            "audio_analysis": {},
            "description": "",
            "confidence": 0.0
        }
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                os.makedirs(self.temp_dir, exist_ok=True)
        except Exception as e:
            log.error(f"Failed to cleanup temp files: {e}")


class AnalysisQueue:
    """Queue manager for batch analysis of media files"""
    
    def __init__(self):
        """Initialize analysis queue"""
        self.queue: List[Dict[str, Any]] = []
        self.is_processing = False
        self.analyzer = MediaAnalyzer()
        self.current_file = None
        self.progress_callback = None
    
    def add_to_queue(self, file_id: str, file_path: str, media_type: str):
        """
        Add file to analysis queue
        
        Args:
            file_id: Unique file ID
            file_path: Path to the media file
            media_type: Type of media
        """
        item = {
            'file_id': file_id,
            'file_path': file_path,
            'media_type': media_type,
            'status': 'pending'
        }
        self.queue.append(item)
        log.debug(f"Added file to analysis queue: {file_path}")
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            'total': len(self.queue),
            'pending': len([item for item in self.queue if item['status'] == 'pending']),
            'processing': 1 if self.is_processing else 0,
            'current_file': self.current_file
        }
    
    async def process_queue(self):
        """Process all files in the queue"""
        if self.is_processing:
            log.warning("Queue is already being processed")
            return
        
        if not self.analyzer.is_available():
            log.warning("Analyzer not available, cannot process queue")
            return
        
        self.is_processing = True
        log.info(f"Processing analysis queue with {len(self.queue)} items")
        
        try:
            from classes.query import File
            
            for item in self.queue:
                if item['status'] != 'pending':
                    continue
                
                item['status'] = 'processing'
                self.current_file = item['file_path']
                
                log.info(f"Analyzing: {item['file_path']}")
                
                try:
                    # Analyze file
                    metadata = await self.analyzer.analyze_file(
                        item['file_id'],
                        item['file_path'],
                        item['media_type']
                    )
                    
                    # Update file object with metadata
                    file_obj = File.get(id=item['file_id'])
                    if file_obj:
                        if 'ai_metadata' not in file_obj.data:
                            file_obj.data['ai_metadata'] = {}
                        file_obj.data['ai_metadata'] = metadata
                        file_obj.save()
                        log.info(f"Saved AI metadata for file: {item['file_id']}")
                    
                    item['status'] = 'completed'
                    
                    # Call progress callback if set
                    if self.progress_callback:
                        self.progress_callback(item)
                    
                except Exception as e:
                    log.error(f"Failed to analyze {item['file_path']}: {e}")
                    item['status'] = 'failed'
                    item['error'] = str(e)
        
        finally:
            self.is_processing = False
            self.current_file = None
            log.info("Queue processing complete")
    
    def clear_queue(self):
        """Clear the analysis queue"""
        self.queue = []
        log.info("Analysis queue cleared")


# Global analysis queue instance
_analysis_queue = None

def get_analysis_queue() -> AnalysisQueue:
    """Get global analysis queue instance"""
    global _analysis_queue
    if _analysis_queue is None:
        _analysis_queue = AnalysisQueue()
    return _analysis_queue
