"""
 @file
 @brief Base AI provider interfaces and factory for media analysis
 @author Zenvi Development Team

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from enum import Enum

from classes.logger import log


class ProviderType(Enum):
    """Enum for AI provider types"""
    OPENAI = "openai"
    GOOGLE = "google"
    AWS = "aws"
    HYBRID = "hybrid"


class AnalysisResult:
    """Standardized result from AI analysis"""
    
    def __init__(self):
        self.objects: List[str] = []
        self.scenes: List[str] = []
        self.activities: List[str] = []
        self.mood: List[str] = []
        self.colors: Dict[str, Any] = {}
        self.faces: List[Dict[str, Any]] = []
        self.quality_scores: Dict[str, float] = {}
        self.description: str = ""
        self.raw_response: Dict[str, Any] = {}
        self.provider: str = ""
        self.confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis result to dictionary"""
        return {
            "objects": self.objects,
            "scenes": self.scenes,
            "activities": self.activities,
            "mood": self.mood,
            "colors": self.colors,
            "faces": self.faces,
            "quality_scores": self.quality_scores,
            "description": self.description,
            "provider": self.provider,
            "confidence": self.confidence
        }


class BaseAIProvider(ABC):
    """Abstract base class for AI providers"""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize the AI provider
        
        Args:
            api_key: API key for the service
            **kwargs: Additional provider-specific configuration
        """
        self.api_key = api_key
        self.config = kwargs
        self.is_configured = False
        self._validate_configuration()
    
    @abstractmethod
    def _validate_configuration(self) -> bool:
        """
        Validate provider configuration
        
        Returns:
            True if configuration is valid
        """
        pass
    
    @abstractmethod
    async def analyze_image(self, image_path: str, **kwargs) -> AnalysisResult:
        """
        Analyze a single image
        
        Args:
            image_path: Path to the image file
            **kwargs: Additional analysis parameters
        
        Returns:
            AnalysisResult object with analysis data
        """
        pass
    
    @abstractmethod
    async def analyze_video_frames(self, frame_paths: List[str], **kwargs) -> AnalysisResult:
        """
        Analyze multiple video frames
        
        Args:
            frame_paths: List of paths to frame images
            **kwargs: Additional analysis parameters
        
        Returns:
            AnalysisResult object with aggregated analysis
        """
        pass
    
    @abstractmethod
    async def detect_faces(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Detect faces in an image
        
        Args:
            image_path: Path to the image file
        
        Returns:
            List of face detection results
        """
        pass
    
    @abstractmethod
    async def parse_search_query(self, query: str) -> Dict[str, Any]:
        """
        Parse natural language search query
        
        Args:
            query: Natural language query string
        
        Returns:
            Structured search parameters
        """
        pass
    
    def get_provider_name(self) -> str:
        """Get the name of this provider"""
        return self.__class__.__name__
    
    def is_available(self) -> bool:
        """Check if provider is properly configured and available"""
        return self.is_configured


class ProviderFactory:
    """Factory for creating AI provider instances"""
    
    _providers = {}
    
    @classmethod
    def register_provider(cls, provider_type: ProviderType, provider_class):
        """
        Register a provider class
        
        Args:
            provider_type: Type of provider
            provider_class: Provider class to register
        """
        cls._providers[provider_type] = provider_class
        log.debug(f"Registered AI provider: {provider_type.value}")
    
    @classmethod
    def create_provider(cls, provider_type: ProviderType, **kwargs) -> Optional[BaseAIProvider]:
        """
        Create a provider instance
        
        Args:
            provider_type: Type of provider to create
            **kwargs: Provider configuration parameters
        
        Returns:
            Provider instance or None if not registered
        """
        provider_class = cls._providers.get(provider_type)
        if provider_class:
            try:
                provider = provider_class(**kwargs)
                log.info(f"Created AI provider: {provider_type.value}")
                return provider
            except Exception as e:
                log.error(f"Failed to create provider {provider_type.value}: {e}")
                return None
        else:
            log.error(f"Provider type {provider_type.value} not registered")
            return None
    
    @classmethod
    def get_available_providers(cls) -> List[ProviderType]:
        """Get list of registered provider types"""
        return list(cls._providers.keys())
