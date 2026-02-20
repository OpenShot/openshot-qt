"""
 @file
 @brief AWS Rekognition provider for face detection and recognition
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


class AWSRekognitionProvider(BaseAIProvider):
    """AWS Rekognition provider for face detection and recognition"""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize AWS Rekognition provider
        
        Args:
            api_key: Not used (uses access_key_id and secret_access_key)
            **kwargs: Additional configuration (access_key_id, secret_access_key, region)
        """
        self.access_key_id = kwargs.get('access_key_id', '')
        self.secret_access_key = kwargs.get('secret_access_key', '')
        self.region = kwargs.get('region', 'us-east-1')
        super().__init__(api_key, **kwargs)
    
    def _validate_configuration(self) -> bool:
        """Validate AWS configuration"""
        if not self.access_key_id or not self.secret_access_key:
            log.warning("AWS credentials not configured")
            self.is_configured = False
            return False
        
        self.is_configured = True
        return True
    
    def _get_client(self):
        """Get AWS Rekognition client"""
        try:
            import boto3
            
            return boto3.client(
                'rekognition',
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region
            )
        except ImportError:
            log.error("Boto3 package not installed. Install with: pip install boto3")
            raise
        except Exception as e:
            log.error(f"Failed to create AWS Rekognition client: {e}")
            raise
    
    async def analyze_image(self, image_path: str, **kwargs) -> AnalysisResult:
        """
        Analyze a single image using AWS Rekognition
        
        Args:
            image_path: Path to the image file
            **kwargs: Additional analysis parameters
        
        Returns:
            AnalysisResult object with analysis data
        """
        log.debug(f"Analyzing image with AWS Rekognition: {image_path}")
        
        try:
            client = self._get_client()
            
            # Load image
            with open(image_path, 'rb') as image_file:
                image_bytes = image_file.read()
            
            # Detect labels
            labels_response = await asyncio.to_thread(
                client.detect_labels,
                Image={'Bytes': image_bytes},
                MaxLabels=20,
                MinConfidence=70
            )
            
            # Detect faces
            faces_response = await asyncio.to_thread(
                client.detect_faces,
                Image={'Bytes': image_bytes},
                Attributes=['ALL']
            )
            
            # Parse responses
            result = self._parse_rekognition_response(labels_response, faces_response)
            result.provider = "aws-rekognition"
            
            log.debug(f"AWS Rekognition analysis complete for {image_path}")
            return result
            
        except Exception as e:
            log.error(f"Failed to analyze image with AWS Rekognition: {e}")
            result = AnalysisResult()
            result.provider = "aws-rekognition"
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
        log.debug(f"Analyzing {len(frame_paths)} frames with AWS Rekognition")
        
        try:
            # Analyze each frame
            frame_results = []
            for frame_path in frame_paths:
                result = await self.analyze_image(frame_path, **kwargs)
                frame_results.append(result)
            
            # Aggregate results
            aggregated = self._aggregate_results(frame_results)
            aggregated.provider = "aws-rekognition"
            
            log.debug("AWS Rekognition video analysis complete")
            return aggregated
            
        except Exception as e:
            log.error(f"Failed to analyze video frames with AWS Rekognition: {e}")
            result = AnalysisResult()
            result.provider = "aws-rekognition"
            return result
    
    def _parse_rekognition_response(self, labels_response, faces_response) -> AnalysisResult:
        """
        Parse AWS Rekognition API responses into AnalysisResult
        
        Args:
            labels_response: Labels detection response
            faces_response: Faces detection response
        
        Returns:
            AnalysisResult object
        """
        result = AnalysisResult()
        
        try:
            # Extract labels
            if 'Labels' in labels_response:
                for label in labels_response['Labels']:
                    if label['Confidence'] > 70:
                        result.objects.append(label['Name'].lower())
                        
                        # Check for parent categories
                        if 'Parents' in label:
                            for parent in label['Parents']:
                                parent_name = parent['Name'].lower()
                                if parent_name not in result.objects:
                                    result.objects.append(parent_name)
            
            # Extract faces
            if 'FaceDetails' in faces_response:
                for face in faces_response['FaceDetails']:
                    face_data = {
                        'confidence': face['Confidence'],
                        'bounding_box': face['BoundingBox'],
                        'age_range': {
                            'low': face.get('AgeRange', {}).get('Low', 0),
                            'high': face.get('AgeRange', {}).get('High', 0)
                        },
                        'gender': face.get('Gender', {}).get('Value', 'Unknown'),
                        'emotions': []
                    }
                    
                    # Extract emotions
                    if 'Emotions' in face:
                        for emotion in face['Emotions']:
                            if emotion['Confidence'] > 50:
                                face_data['emotions'].append({
                                    'type': emotion['Type'].lower(),
                                    'confidence': emotion['Confidence']
                                })
                    
                    result.faces.append(face_data)
                    
                    # Add dominant emotion to mood tags
                    if face_data['emotions']:
                        dominant_emotion = max(face_data['emotions'], key=lambda x: x['confidence'])
                        if dominant_emotion['type'] not in result.mood:
                            result.mood.append(dominant_emotion['type'])
            
            # Classify scenes based on labels
            scene_keywords = {
                'indoor': ['room', 'interior', 'furniture', 'building'],
                'outdoor': ['sky', 'tree', 'nature', 'landscape', 'outdoors'],
                'city': ['building', 'street', 'urban', 'city'],
                'nature': ['tree', 'mountain', 'water', 'plant', 'forest', 'nature']
            }
            
            for scene_type, keywords in scene_keywords.items():
                if any(kw in result.objects for kw in keywords):
                    if scene_type not in result.scenes:
                        result.scenes.append(scene_type)
            
            # Generate description
            if result.objects:
                result.description = f"Image contains: {', '.join(result.objects[:5])}"
                if result.faces:
                    result.description += f" with {len(result.faces)} face(s)"
            
            result.confidence = 0.85  # AWS Rekognition generally high confidence
            result.raw_response = {
                'labels': labels_response,
                'faces': faces_response
            }
            
        except Exception as e:
            log.error(f"Failed to parse AWS Rekognition response: {e}")
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
        
        from collections import Counter
        
        all_objects = []
        all_scenes = []
        all_moods = []
        all_faces = []
        
        for result in results:
            all_objects.extend(result.objects)
            all_scenes.extend(result.scenes)
            all_moods.extend(result.mood)
            all_faces.extend(result.faces)
        
        # Get most common tags
        object_counts = Counter(all_objects)
        scene_counts = Counter(all_scenes)
        mood_counts = Counter(all_moods)
        
        # Keep tags that appear in at least 40% of frames
        threshold = len(results) * 0.4
        aggregated.objects = [obj for obj, count in object_counts.items() if count >= threshold]
        aggregated.scenes = [scene for scene, count in scene_counts.items() if count >= threshold]
        aggregated.mood = [mood for mood, count in mood_counts.most_common(3)]  # Top 3 moods
        
        # Aggregate faces
        aggregated.faces = all_faces[:10]  # Keep first 10 unique faces
        
        # Average confidence
        if results:
            aggregated.confidence = sum(r.confidence for r in results) / len(results)
        
        # Generate description
        if aggregated.objects:
            aggregated.description = f"Video contains: {', '.join(aggregated.objects[:5])}"
            if aggregated.faces:
                aggregated.description += f" with {len(aggregated.faces)} face(s)"
        
        return aggregated
    
    async def detect_faces(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Detect faces in an image
        
        Args:
            image_path: Path to the image file
        
        Returns:
            List of face detection results
        """
        log.debug(f"Detecting faces with AWS Rekognition: {image_path}")
        
        try:
            client = self._get_client()
            
            with open(image_path, 'rb') as image_file:
                image_bytes = image_file.read()
            
            response = await asyncio.to_thread(
                client.detect_faces,
                Image={'Bytes': image_bytes},
                Attributes=['ALL']
            )
            
            faces = []
            if 'FaceDetails' in response:
                for face in response['FaceDetails']:
                    face_data = {
                        'confidence': face['Confidence'],
                        'bounding_box': face['BoundingBox'],
                        'age_range': face.get('AgeRange', {}),
                        'gender': face.get('Gender', {}),
                        'emotions': face.get('Emotions', []),
                        'landmarks': face.get('Landmarks', []),
                        'quality': face.get('Quality', {})
                    }
                    faces.append(face_data)
            
            return faces
            
        except Exception as e:
            log.error(f"Failed to detect faces with AWS Rekognition: {e}")
            return []
    
    async def compare_faces(self, source_image: str, target_image: str) -> Dict[str, Any]:
        """
        Compare faces between two images
        
        Args:
            source_image: Path to source image
            target_image: Path to target image
        
        Returns:
            Comparison result with similarity score
        """
        log.debug(f"Comparing faces: {source_image} vs {target_image}")
        
        try:
            client = self._get_client()
            
            with open(source_image, 'rb') as source_file:
                source_bytes = source_file.read()
            
            with open(target_image, 'rb') as target_file:
                target_bytes = target_file.read()
            
            response = await asyncio.to_thread(
                client.compare_faces,
                SourceImage={'Bytes': source_bytes},
                TargetImage={'Bytes': target_bytes},
                SimilarityThreshold=70
            )
            
            return {
                'face_matches': response.get('FaceMatches', []),
                'unmatched_faces': response.get('UnmatchedFaces', []),
                'source_face': response.get('SourceImageFace', {})
            }
            
        except Exception as e:
            log.error(f"Failed to compare faces: {e}")
            return {}
    
    async def parse_search_query(self, query: str) -> Dict[str, Any]:
        """
        Parse natural language search query
        Note: AWS Rekognition doesn't have NLP, so this is a simple keyword-based parser
        
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
        if any(word in query_lower for word in ['people', 'person', 'face', 'man', 'woman']):
            filters['people'] = True
            filters['objects'].append('person')
        
        # Mood keywords
        mood_keywords = ['happy', 'sad', 'angry', 'surprised', 'calm', 'excited']
        for mood in mood_keywords:
            if mood in query_lower:
                filters['mood'].append(mood)
        
        return filters


# Register the provider
ProviderFactory.register_provider(ProviderType.AWS, AWSRekognitionProvider)
