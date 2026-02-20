"""
 @file
 @brief Main orchestrator for AI media management features
 @author Flowcut Development Team

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
 This file is part of OpenShot Video Editor (http://www.openshot.org)
"""

import asyncio
from typing import Dict, List, Any, Optional, Tuple

from classes.logger import log
from classes.app import get_app
from classes.query import File
from classes.media_analyzer import get_analysis_queue
from classes.tag_manager import get_tag_manager
from classes.face_manager import get_face_manager
from classes.search_engine import get_search_engine
from classes.collection_manager import get_collection_manager


class AIMediaManager:
    """Main orchestrator for AI media management features"""
    
    def __init__(self):
        """Initialize AI media manager"""
        self.analysis_queue = get_analysis_queue()
        self.tag_manager = get_tag_manager()
        self.face_manager = get_face_manager()
        self.search_engine = get_search_engine()
        self.collection_manager = get_collection_manager()
    
    async def analyze_file(self, file_id: str) -> Dict[str, Any]:
        """
        Analyze a single file
        
        Args:
            file_id: File ID
        
        Returns:
            Analysis result dictionary
        """
        try:
            file_obj = File.get(id=file_id)
            if not file_obj:
                return {'success': False, 'error': 'File not found'}
            
            # Add to analysis queue
            self.analysis_queue.add_to_queue(
                file_id,
                file_obj.absolute_path(),
                file_obj.data.get('media_type', 'video')
            )
            
            # Process queue
            await self.analysis_queue.process_queue()
            
            # Update tags and collections
            self.tag_manager.refresh_cache()
            self.collection_manager.update_all_collections()
            
            return {'success': True, 'file_id': file_id}
            
        except Exception as e:
            log.error(f"Failed to analyze file: {e}")
            return {'success': False, 'error': str(e)}
    
    async def analyze_multiple_files(self, file_ids: List[str]) -> Dict[str, Any]:
        """
        Analyze multiple files
        
        Args:
            file_ids: List of file IDs
        
        Returns:
            Analysis result dictionary
        """
        try:
            # Add all files to queue
            for file_id in file_ids:
                file_obj = File.get(id=file_id)
                if file_obj:
                    self.analysis_queue.add_to_queue(
                        file_id,
                        file_obj.absolute_path(),
                        file_obj.data.get('media_type', 'video')
                    )
            
            # Process queue
            await self.analysis_queue.process_queue()
            
            # Update tags and collections
            self.tag_manager.refresh_cache()
            self.collection_manager.update_all_collections()
            
            return {'success': True, 'analyzed_count': len(file_ids)}
            
        except Exception as e:
            log.error(f"Failed to analyze multiple files: {e}")
            return {'success': False, 'error': str(e)}
    
    async def search_files(self, query: str) -> List[Tuple[str, float]]:
        """
        Search files using natural language
        
        Args:
            query: Natural language search query
        
        Returns:
            List of (file_id, relevance_score) tuples
        """
        try:
            results = await self.search_engine.search(query)
            return results
        except Exception as e:
            log.error(f"Search failed: {e}")
            return []
    
    def get_file_tags(self, file_id: str) -> Dict[str, Any]:
        """
        Get AI tags for a file
        
        Args:
            file_id: File ID
        
        Returns:
            Dictionary of tags
        """
        try:
            file_obj = File.get(id=file_id)
            if file_obj:
                return file_obj.get_ai_tags()
            return {}
        except Exception as e:
            log.error(f"Failed to get file tags: {e}")
            return {}
    
    def get_all_tags(self) -> Dict[str, List[str]]:
        """Get all available tags organized by category"""
        return self.tag_manager.get_all_tags()
    
    def get_files_with_tag(self, tag: str, category: Optional[str] = None) -> List[str]:
        """
        Get files with a specific tag
        
        Args:
            tag: Tag value
            category: Optional tag category
        
        Returns:
            List of file IDs
        """
        return self.tag_manager.get_files_with_tag(tag, category)
    
    def detect_faces_in_file(self, file_id: str) -> List[Dict[str, Any]]:
        """
        Detect faces in a file
        
        Args:
            file_id: File ID
        
        Returns:
            List of detected faces
        """
        return self.face_manager.detect_faces_in_file(file_id)
    
    def get_all_people(self) -> List[Any]:
        """Get all recognized people"""
        return self.face_manager.get_all_people()
    
    def get_files_with_person(self, person_id: str) -> List[str]:
        """
        Get files containing a specific person
        
        Args:
            person_id: Person ID
        
        Returns:
            List of file IDs
        """
        return self.face_manager.get_files_with_person(person_id)
    
    def create_collection(self, name: str, rules: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new smart collection
        
        Args:
            name: Collection name
            rules: Optional list of rule dictionaries
        
        Returns:
            Collection info dictionary
        """
        try:
            from classes.collection_manager import CollectionType, CollectionRule, RuleOperator
            
            collection = self.collection_manager.create_collection(name)
            
            # Add rules if provided
            if rules:
                for rule_data in rules:
                    rule = CollectionRule(
                        field=rule_data['field'],
                        operator=RuleOperator(rule_data['operator']),
                        value=rule_data['value']
                    )
                    collection.add_rule(rule)
            
            # Update collection
            collection.update_files()
            
            return {
                'success': True,
                'collection_id': collection.collection_id,
                'name': collection.name,
                'file_count': collection.get_file_count()
            }
            
        except Exception as e:
            log.error(f"Failed to create collection: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_all_collections(self) -> List[Dict[str, Any]]:
        """Get all collections"""
        collections = self.collection_manager.get_all_collections()
        return [
            {
                'collection_id': c.collection_id,
                'name': c.name,
                'type': c.collection_type.value,
                'file_count': c.get_file_count(),
                'icon': c.icon,
                'color': c.color
            }
            for c in collections
        ]
    
    def get_files_in_collection(self, collection_id: str) -> List[str]:
        """
        Get files in a collection
        
        Args:
            collection_id: Collection ID
        
        Returns:
            List of file IDs
        """
        return self.collection_manager.get_files_in_collection(collection_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall AI media management statistics"""
        return {
            'tags': self.tag_manager.get_tag_statistics(),
            'faces': self.face_manager.get_statistics(),
            'collections': {
                'total': len(self.collection_manager.get_all_collections())
            },
            'analysis_queue': self.analysis_queue.get_queue_status()
        }
    
    async def process_command(self, command: str) -> Dict[str, Any]:
        """
        Process a natural language command
        
        Args:
            command: Natural language command
        
        Returns:
            Command result dictionary
        """
        command_lower = command.lower()
        
        try:
            # Analyze commands
            if 'analyze' in command_lower:
                if 'all' in command_lower:
                    # Analyze all files
                    all_files = File.filter()
                    file_ids = [f.id for f in all_files if not f.has_ai_metadata()]
                    result = await self.analyze_multiple_files(file_ids)
                    return {
                        'success': True,
                        'action': 'analyze_all',
                        'message': f"Analyzing {len(file_ids)} files",
                        'result': result
                    }
                else:
                    return {
                        'success': False,
                        'message': "Please specify which files to analyze"
                    }
            
            # Search commands
            elif 'search' in command_lower or 'find' in command_lower:
                # Extract search query
                query = command_lower.replace('search for', '').replace('find', '').strip()
                results = await self.search_files(query)
                
                return {
                    'success': True,
                    'action': 'search',
                    'query': query,
                    'results': results[:10],  # Top 10 results
                    'message': f"Found {len(results)} matching files"
                }
            
            # Collection commands
            elif 'create collection' in command_lower:
                # Extract collection name
                name = command_lower.replace('create collection', '').strip()
                if not name:
                    name = "New Collection"
                
                result = self.create_collection(name)
                return {
                    'success': True,
                    'action': 'create_collection',
                    'result': result,
                    'message': f"Created collection: {name}"
                }
            
            # Statistics commands
            elif 'statistics' in command_lower or 'stats' in command_lower:
                stats = self.get_statistics()
                return {
                    'success': True,
                    'action': 'statistics',
                    'stats': stats,
                    'message': "Retrieved AI media management statistics"
                }
            
            else:
                return {
                    'success': False,
                    'message': "Command not recognized. Try: 'analyze all', 'search for X', 'create collection NAME', 'statistics'"
                }
                
        except Exception as e:
            log.error(f"Failed to process command: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f"Failed to process command: {str(e)}"
            }


# Global AI media manager instance
_ai_media_manager = None

def get_ai_media_manager() -> AIMediaManager:
    """Get global AI media manager instance"""
    global _ai_media_manager
    if _ai_media_manager is None:
        _ai_media_manager = AIMediaManager()
    return _ai_media_manager
