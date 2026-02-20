"""
 @file
 @brief Natural language search engine for media files
 @author Flowcut Development Team

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
 This file is part of OpenShot Video Editor (http://www.openshot.org)
"""

import asyncio
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

from classes.logger import log
from classes.app import get_app
from classes.query import File
from classes.tag_manager import get_tag_manager
from classes.ai_providers import ProviderFactory, ProviderType


class SearchEngine:
    """Natural language search engine for media files"""
    
    def __init__(self):
        """Initialize search engine"""
        self.provider = None
        self._init_provider()
    
    def _init_provider(self):
        """Initialize AI provider for query parsing"""
        try:
            s = get_app().get_settings()
            
            if not s.get('ai-enabled'):
                return
            
            # Use OpenAI for query parsing (best NLP capabilities)
            api_key = s.get('openai-api-key')
            if api_key:
                self.provider = ProviderFactory.create_provider(
                    ProviderType.OPENAI,
                    api_key=api_key
                )
        except Exception as e:
            log.error(f"Failed to initialize search provider: {e}")
    
    async def search(self, query: str, **kwargs) -> List[Tuple[str, float]]:
        """
        Search for files using natural language query
        
        Args:
            query: Natural language search query
            **kwargs: Additional search parameters
        
        Returns:
            List of tuples (file_id, relevance_score) sorted by relevance
        """
        log.info(f"Searching for: {query}")
        
        try:
            # Parse query into structured filters
            if self.provider and self.provider.is_available():
                filters = await self.provider.parse_search_query(query)
            else:
                # Fallback to simple keyword matching
                filters = self._simple_query_parse(query)
            
            log.debug(f"Parsed filters: {filters}")
            
            # Search using filters
            results = self._search_with_filters(filters)
            
            # Rank results by relevance
            ranked_results = self._rank_results(results, filters, query)
            
            log.info(f"Found {len(ranked_results)} results")
            return ranked_results
            
        except Exception as e:
            log.error(f"Search failed: {e}")
            return []
    
    def _simple_query_parse(self, query: str) -> Dict[str, Any]:
        """
        Simple keyword-based query parsing (fallback)
        
        Args:
            query: Search query
        
        Returns:
            Filter dictionary
        """
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
        
        # Scene keywords
        scene_map = {
            'outdoor': ['outdoor', 'outside'],
            'indoor': ['indoor', 'inside', 'room'],
            'city': ['city', 'urban', 'street'],
            'nature': ['nature', 'forest', 'mountain', 'beach', 'landscape']
        }
        
        for scene, keywords in scene_map.items():
            if any(kw in query_lower for kw in keywords):
                filters['scenes'].append(scene)
        
        # People detection
        if any(word in query_lower for word in ['people', 'person', 'face', 'man', 'woman']):
            filters['people'] = True
            filters['objects'].append('person')
        
        # Activity keywords
        activity_keywords = ['walking', 'talking', 'running', 'sitting', 'standing', 'driving']
        for activity in activity_keywords:
            if activity in query_lower:
                filters['activities'].append(activity)
        
        # Mood keywords
        mood_keywords = ['happy', 'sad', 'serious', 'energetic', 'calm', 'dramatic']
        for mood in mood_keywords:
            if mood in query_lower:
                filters['mood'].append(mood)
        
        # Common objects
        object_keywords = ['car', 'building', 'tree', 'water', 'sky', 'animal', 'dog', 'cat']
        for obj in object_keywords:
            if obj in query_lower:
                filters['objects'].append(obj)
        
        return filters
    
    def _search_with_filters(self, filters: Dict[str, Any]) -> List[str]:
        """
        Search files using structured filters
        
        Args:
            filters: Filter dictionary
        
        Returns:
            List of matching file IDs
        """
        # Get all files with AI metadata
        all_files = File.filter()
        matching_files = []
        
        for file_obj in all_files:
            if not file_obj.has_ai_metadata():
                continue
            
            # Check if file matches filters
            if self._file_matches_filters(file_obj, filters):
                matching_files.append(file_obj.id)
        
        return matching_files
    
    def _file_matches_filters(self, file_obj: File, filters: Dict[str, Any]) -> bool:
        """
        Check if a file matches the given filters
        
        Args:
            file_obj: File object
            filters: Filter dictionary
        
        Returns:
            True if file matches
        """
        ai_tags = file_obj.get_ai_tags()
        
        # Check objects
        if filters.get('objects'):
            file_objects = ai_tags.get('objects', [])
            if not any(obj in file_objects for obj in filters['objects']):
                return False
        
        # Check scenes
        if filters.get('scenes'):
            file_scenes = ai_tags.get('scenes', [])
            if not any(scene in file_scenes for scene in filters['scenes']):
                return False
        
        # Check activities
        if filters.get('activities'):
            file_activities = ai_tags.get('activities', [])
            if not any(activity in file_activities for activity in filters['activities']):
                return False
        
        # Check mood
        if filters.get('mood'):
            file_mood = ai_tags.get('mood', [])
            if not any(mood in file_mood for mood in filters['mood']):
                return False
        
        # Check people
        if filters.get('people'):
            ai_metadata = file_obj.get_ai_metadata()
            faces = ai_metadata.get('faces', [])
            if not faces:
                return False
        
        return True
    
    def _rank_results(self, file_ids: List[str], filters: Dict[str, Any], query: str) -> List[Tuple[str, float]]:
        """
        Rank search results by relevance
        
        Args:
            file_ids: List of matching file IDs
            filters: Filter dictionary
            query: Original query string
        
        Returns:
            List of tuples (file_id, relevance_score) sorted by score
        """
        ranked = []
        
        for file_id in file_ids:
            file_obj = File.get(id=file_id)
            if not file_obj:
                continue
            
            score = self._calculate_relevance_score(file_obj, filters, query)
            ranked.append((file_id, score))
        
        # Sort by score descending
        ranked.sort(key=lambda x: x[1], reverse=True)
        
        return ranked
    
    def _calculate_relevance_score(self, file_obj: File, filters: Dict[str, Any], query: str) -> float:
        """
        Calculate relevance score for a file
        
        Args:
            file_obj: File object
            filters: Filter dictionary
            query: Original query
        
        Returns:
            Relevance score (0.0 to 1.0)
        """
        score = 0.0
        max_score = 0.0
        
        ai_tags = file_obj.get_ai_tags()
        ai_metadata = file_obj.get_ai_metadata()
        
        # Object matches (weight: 0.3)
        if filters.get('objects'):
            max_score += 0.3
            file_objects = ai_tags.get('objects', [])
            matches = sum(1 for obj in filters['objects'] if obj in file_objects)
            score += (matches / len(filters['objects'])) * 0.3
        
        # Scene matches (weight: 0.25)
        if filters.get('scenes'):
            max_score += 0.25
            file_scenes = ai_tags.get('scenes', [])
            matches = sum(1 for scene in filters['scenes'] if scene in file_scenes)
            score += (matches / len(filters['scenes'])) * 0.25
        
        # Activity matches (weight: 0.2)
        if filters.get('activities'):
            max_score += 0.2
            file_activities = ai_tags.get('activities', [])
            matches = sum(1 for activity in filters['activities'] if activity in file_activities)
            score += (matches / len(filters['activities'])) * 0.2
        
        # Mood matches (weight: 0.15)
        if filters.get('mood'):
            max_score += 0.15
            file_mood = ai_tags.get('mood', [])
            matches = sum(1 for mood in filters['mood'] if mood in file_mood)
            score += (matches / len(filters['mood'])) * 0.15
        
        # Description match (weight: 0.1)
        max_score += 0.1
        description = ai_metadata.get('description', '').lower()
        query_words = query.lower().split()
        desc_matches = sum(1 for word in query_words if word in description)
        if query_words:
            score += (desc_matches / len(query_words)) * 0.1
        
        # Normalize score
        if max_score > 0:
            score = score / max_score
        
        # Boost by AI confidence
        confidence = ai_metadata.get('confidence', 0.5)
        score = score * (0.7 + 0.3 * confidence)
        
        return min(1.0, score)
    
    def get_search_suggestions(self, partial_query: str) -> List[str]:
        """
        Get search suggestions based on partial query
        
        Args:
            partial_query: Partial search query
        
        Returns:
            List of suggested queries
        """
        suggestions = []
        
        try:
            tag_manager = get_tag_manager()
            all_tags = tag_manager.get_all_tags()
            
            partial_lower = partial_query.lower()
            
            # Suggest based on tags
            for category, tags in all_tags.items():
                for tag in tags:
                    if tag.startswith(partial_lower):
                        suggestions.append(f"{category[:-1]}: {tag}")
            
            # Add common query templates
            templates = [
                "outdoor shots with people",
                "indoor scenes",
                "videos with cars",
                "happy people",
                "nature scenes",
                "city streets",
                "people talking"
            ]
            
            for template in templates:
                if partial_lower in template:
                    suggestions.append(template)
            
            return suggestions[:10]  # Limit to 10 suggestions
            
        except Exception as e:
            log.error(f"Failed to get search suggestions: {e}")
            return []


# Global search engine instance
_search_engine = None

def get_search_engine() -> SearchEngine:
    """Get global search engine instance"""
    global _search_engine
    if _search_engine is None:
        _search_engine = SearchEngine()
    return _search_engine
