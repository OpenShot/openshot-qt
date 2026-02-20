"""
 @file
 @brief Google Cloud Vision provider for media analysis
 @author Flowcut Development Team

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
 This file is part of OpenShot Video Editor (http://www.openshot.org)
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from pathlib import Path

from classes.logger import log
from classes.ai_providers import BaseAIProvider, AnalysisResult, ProviderType, ProviderFactory


class GoogleVisionProvider(BaseAIProvider):
    """Google Cloud Vision provider for detailed object and label detection"""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize Google Vision provider
        
        Args:
            api_key: Not used for Google (uses credentials file)
            **kwargs: Additional configuration (credentials_path)
        """
        self.credentials_path = kwargs.get('credentials_path', '')
        super().__init__(api_key, **kwargs)
    
    def _validate_configuration(self) -> bool:
        """Validate Google Cloud configuration"""
        import os
        
        if not self.credentials_path or not os.path.exists(self.credentials_path):
            log.warning("Google Cloud credentials file not configured or not found")
            self.is_configured = False
            return False
        
        self.is_configured = True
        return True
    
    def _get_client(self):
        """Get Google Vision API client"""
        try:
            from google.cloud import vision
            import os
            
            # Set credentials environment variable
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.credentials_path
            
            return vision.ImageAnnotatorClient()
        except ImportError:
            log.error("Google Cloud Vision package not installed. Install with: pip install google-cloud-vision")
            raise
        except Exception as e:
            log.error(f"Failed to create Google Vision client: {e}")
            raise
    
    async def analyze_image(self, image_path: str, **kwargs) -> AnalysisResult:
        """
        Analyze a single image using Google Cloud Vision
        
        Args:
            image_path: Path to the image file
            **kwargs: Additional analysis parameters
        
        Returns:
            AnalysisResult object with analysis data
        """
        log.debug(f"Analyzing image with Google Vision: {image_path}")
        
        try:
            from google.cloud import vision
            
            # Get client
            client = self._get_client()
            
            # Load image
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            
            # Perform multiple types of detection
            response = await asyncio.to_thread(
                client.annotate_image,
                {
                    'image': image,
                    'features': [
                        {'type_': vision.Feature.Type.LABEL_DETECTION, 'max_results': 20},
                        {'type_': vision.Feature.Type.OBJECT_LOCALIZATION, 'max_results': 20},
                        {'type_': vision.Feature.Type.FACE_DETECTION, 'max_results': 10},
                        {'type_': vision.Feature.Type.IMAGE_PROPERTIES},
                        {'type_': vision.Feature.Type.SAFE_SEARCH_DETECTION},
                    ]
                }
            )
            
            # Parse response
            result = self._parse_vision_response(response)
            result.provider = "google-cloud-vision"
            
            log.debug(f"Google Vision analysis complete for {image_path}")
            return result
            
        except Exception as e:
            log.error(f"Failed to analyze image with Google Vision: {e}")
            result = AnalysisResult()
            result.provider = "google-cloud-vision"
            return result
    
    async def analyze_video_frames(self, frame_paths: List[str], **kwargs) -> AnalysisResult:
        """
        Analyze multiple video frames
        
        Args:
            frame_paths: List of paths to frame images
            **kwargs: Additional analysis parameters
        
        Returns:
            AnalysisResult object with aggregated analysis
        """
        log.debug(f"Analyzing {len(frame_paths)} frames with Google Vision")
        
        try:
            # Analyze each frame
            frame_results = []
            for frame_path in frame_paths:
                result = await self.analyze_image(frame_path, **kwargs)
                frame_results.append(result)
            
            # Aggregate results
            aggregated = self._aggregate_results(frame_results)
            aggregated.provider = "google-cloud-vision"
            
            log.debug("Google Vision video analysis complete")
            return aggregated
            
        except Exception as e:
            log.error(f"Failed to analyze video frames with Google Vision: {e}")
            result = AnalysisResult()
            result.provider = "google-cloud-vision"
            return result
    
    def _parse_vision_response(self, response) -> AnalysisResult:
        """
        Parse Google Vision API response into AnalysisResult
        
        Args:
            response: Raw API response
        
        Returns:
            AnalysisResult object
        """
        result = AnalysisResult()
        
        try:
            # Extract labels (objects/scenes)
            if response.label_annotations:
                for label in response.label_annotations:
                    if label.score > 0.7:  # High confidence
                        result.objects.append(label.description.lower())
            
            # Extract localized objects
            if response.localized_object_annotations:
                for obj in response.localized_object_annotations:
                    if obj.score > 0.6:
                        obj_name = obj.name.lower()
                        if obj_name not in result.objects:
                            result.objects.append(obj_name)
            
            # Extract faces
            if response.face_annotations:
                for face in response.face_annotations:
                    face_data = {
                        'confidence': face.detection_confidence,
                        'bounding_box': {
                            'vertices': [
                                {'x': v.x, 'y': v.y}
                                for v in face.bounding_poly.vertices
                            ]
                        },
                        'emotions': {
                            'joy': face.joy_likelihood.name,
                            'sorrow': face.sorrow_likelihood.name,
                            'anger': face.anger_likelihood.name,
                            'surprise': face.surprise_likelihood.name
                        }
                    }
                    result.faces.append(face_data)
            
            # Extract color properties
            if response.image_properties_annotation:
                dominant_colors = response.image_properties_annotation.dominant_colors.colors
                if dominant_colors:
                    result.colors['dominant'] = [
                        f"#{int(c.color.red):02x}{int(c.color.green):02x}{int(c.color.blue):02x}"
                        for c in dominant_colors[:5]
                    ]
            
            # Classify scenes based on labels
            scene_keywords = {
                'indoor': ['room', 'interior', 'building', 'furniture'],
                'outdoor': ['sky', 'tree', 'nature', 'landscape', 'outdoor'],
                'city': ['building', 'street', 'urban', 'city'],
                'nature': ['tree', 'mountain', 'water', 'plant', 'forest']
            }
            
            for scene_type, keywords in scene_keywords.items():
                if any(kw in ' '.join(result.objects) for kw in keywords):
                    if scene_type not in result.scenes:
                        result.scenes.append(scene_type)
            
            # Generate description from top labels
            if result.objects:
                result.description = f"Image contains: {', '.join(result.objects[:5])}"
            
            result.confidence = 0.85  # Google Vision generally high confidence
            result.raw_response = {'response': str(response)}
            
        except Exception as e:
            log.error(f"Failed to parse Google Vision response: {e}")
            result.confidence = 0.0
        
        return result
    
    def _aggregate_results(self, results: List[AnalysisResult]) -> AnalysisResult:
        """
        Aggregate multiple frame results into one
        
        Args:
            results: List of AnalysisResult objects
        
        Returns:
            Aggregated AnalysisResult
        """
        aggregated = AnalysisResult()
        
        # Count occurrences of each tag
        from collections import Counter
        
        all_objects = []
        all_scenes = []
        all_faces = []
        
        for result in results:
            all_objects.extend(result.objects)
            all_scenes.extend(result.scenes)
            all_faces.extend(result.faces)
        
        # Get most common objects/scenes
        object_counts = Counter(all_objects)
        scene_counts = Counter(all_scenes)
        
        # Keep tags that appear in at least 40% of frames
        threshold = len(results) * 0.4
        aggregated.objects = [obj for obj, count in object_counts.items() if count >= threshold]
        aggregated.scenes = [scene for scene, count in scene_counts.items() if count >= threshold]
        
        # Aggregate faces (simplified)
        aggregated.faces = all_faces[:10]  # Keep first 10 unique faces
        
        # Average confidence
        if results:
            aggregated.confidence = sum(r.confidence for r in results) / len(results)
        
        # Generate description
        if aggregated.objects:
            aggregated.description = f"Video contains: {', '.join(aggregated.objects[:5])}"
        
        return aggregated
    
    async def detect_faces(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Detect faces in an image
        
        Args:
            image_path: Path to the image file
        
        Returns:
            List of face detection results
        """
        log.debug(f"Detecting faces with Google Vision: {image_path}")
        
        try:
            from google.cloud import vision
            
            client = self._get_client()
            
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            
            response = await asyncio.to_thread(client.face_detection, image=image)
            
            faces = []
            for face in response.face_annotations:
                face_data = {
                    'confidence': face.detection_confidence,
                    'bounding_box': {
                        'vertices': [
                            {'x': v.x, 'y': v.y}
                            for v in face.bounding_poly.vertices
                        ]
                    },
                    'landmarks': [
                        {'type': lm.type_.name, 'x': lm.position.x, 'y': lm.position.y}
                        for lm in face.landmarks
                    ],
                    'emotions': {
                        'joy': face.joy_likelihood.name,
                        'sorrow': face.sorrow_likelihood.name,
                        'anger': face.anger_likelihood.name,
                        'surprise': face.surprise_likelihood.name
                    }
                }
                faces.append(face_data)
            
            return faces
            
        except Exception as e:
            log.error(f"Failed to detect faces with Google Vision: {e}")
            return []
    
    async def parse_search_query(self, query: str) -> Dict[str, Any]:
        """
        Parse natural language search query
        Note: Google Vision doesn't have NLP, so this is a simple keyword-based parser
        
        Args:
            query: Natural language query string
        
        Returns:
            Structured search parameters
        """
        log.debug(f"Parsing search query (simple): {query}")
        
        query_lower = query.lower()
        
        filters = {
            'objects': [],
            'scenes': [],
            'activities': [],
            'mood': [],
            'people': False,
            'quality': 'any',
            'time': 'any'
        }
        
        # Simple keyword matching
        scene_keywords = {
            'outdoor': ['outdoor', 'outside', 'nature'],
            'indoor': ['indoor', 'inside', 'room'],
            'city': ['city', 'urban', 'street'],
            'nature': ['nature', 'forest', 'mountain', 'beach']
        }
        
        for scene, keywords in scene_keywords.items():
            if any(kw in query_lower for kw in keywords):
                filters['scenes'].append(scene)
        
        # Check for people
        if any(word in query_lower for word in ['people', 'person', 'man', 'woman', 'face']):
            filters['people'] = True
            filters['objects'].append('person')
        
        return filters


# Register the provider
ProviderFactory.register_provider(ProviderType.GOOGLE, GoogleVisionProvider)
