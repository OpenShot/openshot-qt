"""
 @file
 @brief Tag manager for organizing and filtering media by AI-generated tags
 @author Flowcut Development Team

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
 This file is part of OpenShot Video Editor (http://www.openshot.org)
"""

from typing import Dict, List, Set, Any, Optional
from collections import defaultdict

from classes.logger import log
from classes.app import get_app
from classes.query import File


class TagManager:
    """Manages AI-generated tags and tag-based filtering"""
    
    def __init__(self):
        """Initialize tag manager"""
        self.tag_cache = defaultdict(set)  # tag -> set of file_ids
        self._build_cache()
    
    def _build_cache(self):
        """Build tag cache from all files with AI metadata"""
        log.debug("Building tag cache")
        
        try:
            all_files = File.filter()
            
            for file_obj in all_files:
                if 'ai_metadata' in file_obj.data:
                    self._index_file(file_obj.id, file_obj.data['ai_metadata'])
            
            log.info(f"Tag cache built with {len(self.tag_cache)} unique tags")
            
        except Exception as e:
            log.error(f"Failed to build tag cache: {e}")
    
    def _index_file(self, file_id: str, ai_metadata: Dict[str, Any]):
        """
        Index a file's tags in the cache
        
        Args:
            file_id: File ID
            ai_metadata: AI metadata dictionary
        """
        if not ai_metadata.get('analyzed'):
            return
        
        tags = ai_metadata.get('tags', {})
        
        # Index all tag types
        for obj in tags.get('objects', []):
            self.tag_cache[f"object:{obj}"].add(file_id)
        
        for scene in tags.get('scenes', []):
            self.tag_cache[f"scene:{scene}"].add(file_id)
        
        for activity in tags.get('activities', []):
            self.tag_cache[f"activity:{activity}"].add(file_id)
        
        for mood in tags.get('mood', []):
            self.tag_cache[f"mood:{mood}"].add(file_id)
    
    def update_file_tags(self, file_id: str, ai_metadata: Dict[str, Any]):
        """
        Update tags for a file
        
        Args:
            file_id: File ID
            ai_metadata: AI metadata dictionary
        """
        # Remove old tags
        self.remove_file_tags(file_id)
        
        # Add new tags
        self._index_file(file_id, ai_metadata)
        
        log.debug(f"Updated tags for file: {file_id}")
    
    def remove_file_tags(self, file_id: str):
        """
        Remove all tags for a file
        
        Args:
            file_id: File ID
        """
        for tag, file_ids in list(self.tag_cache.items()):
            if file_id in file_ids:
                file_ids.remove(file_id)
                if not file_ids:
                    del self.tag_cache[tag]
    
    def get_all_tags(self) -> Dict[str, List[str]]:
        """
        Get all unique tags organized by category
        
        Returns:
            Dictionary of tag categories and their tags
        """
        tags_by_category = {
            'objects': [],
            'scenes': [],
            'activities': [],
            'mood': []
        }
        
        for tag in self.tag_cache.keys():
            if ':' in tag:
                category, value = tag.split(':', 1)
                if category == 'object':
                    tags_by_category['objects'].append(value)
                elif category == 'scene':
                    tags_by_category['scenes'].append(value)
                elif category == 'activity':
                    tags_by_category['activities'].append(value)
                elif category == 'mood':
                    tags_by_category['mood'].append(value)
        
        # Sort each category
        for category in tags_by_category:
            tags_by_category[category].sort()
        
        return tags_by_category
    
    def get_files_with_tag(self, tag: str, tag_category: Optional[str] = None) -> List[str]:
        """
        Get all files with a specific tag
        
        Args:
            tag: Tag value
            tag_category: Optional category (object, scene, activity, mood)
        
        Returns:
            List of file IDs
        """
        if tag_category:
            full_tag = f"{tag_category}:{tag}"
        else:
            # Search all categories
            full_tag = tag
            if full_tag not in self.tag_cache:
                # Try with category prefixes
                for category in ['object', 'scene', 'activity', 'mood']:
                    full_tag = f"{category}:{tag}"
                    if full_tag in self.tag_cache:
                        break
        
        return list(self.tag_cache.get(full_tag, set()))
    
    def search_files(self, filters: Dict[str, Any]) -> List[str]:
        """
        Search for files matching filter criteria
        
        Args:
            filters: Dictionary with filter criteria
                objects: List of object tags
                scenes: List of scene tags
                activities: List of activity tags
                mood: List of mood tags
                match_all: Boolean, if True require all tags (AND), else any tag (OR)
        
        Returns:
            List of file IDs matching criteria
        """
        match_all = filters.get('match_all', False)
        matching_files = set()
        first_set = True
        
        # Process each filter type
        for tag_type in ['objects', 'scenes', 'activities', 'mood']:
            tags = filters.get(tag_type, [])
            if not tags:
                continue
            
            # Get files for these tags
            tag_category = tag_type[:-1] if tag_type.endswith('s') else tag_type  # Remove plural 's'
            
            for tag in tags:
                files = set(self.get_files_with_tag(tag, tag_category))
                
                if first_set:
                    matching_files = files
                    first_set = False
                else:
                    if match_all:
                        matching_files &= files  # Intersection (AND)
                    else:
                        matching_files |= files  # Union (OR)
        
        return list(matching_files)
    
    def get_tag_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about tags
        
        Returns:
            Dictionary with tag statistics
        """
        stats = {
            'total_tags': len(self.tag_cache),
            'by_category': {},
            'most_common': []
        }
        
        # Count by category
        category_counts = defaultdict(int)
        for tag in self.tag_cache.keys():
            if ':' in tag:
                category = tag.split(':', 1)[0]
                category_counts[category] += 1
        
        stats['by_category'] = dict(category_counts)
        
        # Most common tags
        tag_usage = [(tag, len(files)) for tag, files in self.tag_cache.items()]
        tag_usage.sort(key=lambda x: x[1], reverse=True)
        stats['most_common'] = tag_usage[:20]  # Top 20
        
        return stats
    
    def get_related_tags(self, tag: str, tag_category: Optional[str] = None, limit: int = 10) -> List[str]:
        """
        Get tags that commonly appear with the given tag
        
        Args:
            tag: Tag value
            tag_category: Optional category
            limit: Maximum number of related tags to return
        
        Returns:
            List of related tags
        """
        # Get files with this tag
        file_ids = set(self.get_files_with_tag(tag, tag_category))
        
        if not file_ids:
            return []
        
        # Count co-occurring tags
        related_counts = defaultdict(int)
        
        for other_tag, other_files in self.tag_cache.items():
            if other_tag == f"{tag_category}:{tag}":
                continue
            
            # Count overlap
            overlap = len(file_ids & other_files)
            if overlap > 0:
                related_counts[other_tag] = overlap
        
        # Sort by count
        related = sorted(related_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [tag for tag, count in related[:limit]]
    
    def refresh_cache(self):
        """Rebuild the entire tag cache"""
        self.tag_cache.clear()
        self._build_cache()


# Global tag manager instance
_tag_manager = None

def get_tag_manager() -> TagManager:
    """Get global tag manager instance"""
    global _tag_manager
    if _tag_manager is None:
        _tag_manager = TagManager()
    return _tag_manager
