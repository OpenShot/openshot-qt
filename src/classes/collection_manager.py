"""
 @file
 @brief Smart collections manager for organizing media files
 @author Flowcut Development Team

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
 This file is part of OpenShot Video Editor (http://www.openshot.org)
"""

import uuid
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from enum import Enum

from classes.logger import log
from classes.app import get_app
from classes.query import File


class CollectionType(Enum):
    """Types of collections"""
    SMART = "smart"  # Auto-updating based on rules
    MANUAL = "manual"  # Manually curated
    PERSON = "person"  # Based on face recognition
    PRESET = "preset"  # Built-in preset collection


class RuleOperator(Enum):
    """Operators for collection rules"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    IN_LIST = "in_list"
    NOT_IN_LIST = "not_in_list"


class CollectionRule:
    """Represents a single rule for a smart collection"""
    
    def __init__(self, field: str, operator: RuleOperator, value: Any):
        """
        Initialize a collection rule
        
        Args:
            field: Field path (e.g., "ai_metadata.tags.objects")
            operator: Rule operator
            value: Value to compare against
        """
        self.field = field
        self.operator = operator
        self.value = value
    
    def evaluate(self, file_obj: File) -> bool:
        """
        Evaluate rule against a file
        
        Args:
            file_obj: File object to evaluate
        
        Returns:
            True if file matches rule
        """
        try:
            # Get field value from file
            field_value = self._get_field_value(file_obj, self.field)
            
            # Evaluate based on operator
            if self.operator == RuleOperator.EQUALS:
                return field_value == self.value
            elif self.operator == RuleOperator.NOT_EQUALS:
                return field_value != self.value
            elif self.operator == RuleOperator.CONTAINS:
                if isinstance(field_value, list):
                    return self.value in field_value
                elif isinstance(field_value, str):
                    return self.value in field_value
                return False
            elif self.operator == RuleOperator.NOT_CONTAINS:
                if isinstance(field_value, list):
                    return self.value not in field_value
                elif isinstance(field_value, str):
                    return self.value not in field_value
                return True
            elif self.operator == RuleOperator.GREATER_THAN:
                return field_value > self.value
            elif self.operator == RuleOperator.LESS_THAN:
                return field_value < self.value
            elif self.operator == RuleOperator.IN_LIST:
                return field_value in self.value
            elif self.operator == RuleOperator.NOT_IN_LIST:
                return field_value not in self.value
            
            return False
            
        except Exception as e:
            log.debug(f"Rule evaluation failed: {e}")
            return False
    
    def _get_field_value(self, file_obj: File, field_path: str) -> Any:
        """
        Get field value from file using dot notation path
        
        Args:
            file_obj: File object
            field_path: Dot-notation path (e.g., "ai_metadata.tags.objects")
        
        Returns:
            Field value
        """
        parts = field_path.split('.')
        value = file_obj.data
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        
        return value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary"""
        return {
            'field': self.field,
            'operator': self.operator.value,
            'value': self.value
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'CollectionRule':
        """Create rule from dictionary"""
        return CollectionRule(
            field=data['field'],
            operator=RuleOperator(data['operator']),
            value=data['value']
        )


class Collection:
    """Represents a media collection"""
    
    def __init__(self, collection_id: str = None, name: str = "New Collection",
                 collection_type: CollectionType = CollectionType.SMART):
        """
        Initialize a collection
        
        Args:
            collection_id: Unique collection ID
            name: Collection name
            collection_type: Type of collection
        """
        self.collection_id = collection_id or str(uuid.uuid4())
        self.name = name
        self.collection_type = collection_type
        self.rules: List[CollectionRule] = []
        self.match_all = True  # True = AND, False = OR
        self.file_ids: List[str] = []
        self.icon = "folder"
        self.color = "#4CAF50"
        self.auto_update = True
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def add_rule(self, rule: CollectionRule):
        """Add a rule to the collection"""
        self.rules.append(rule)
        self.updated_at = datetime.now()
    
    def remove_rule(self, index: int):
        """Remove a rule by index"""
        if 0 <= index < len(self.rules):
            del self.rules[index]
            self.updated_at = datetime.now()
    
    def evaluate_file(self, file_obj: File) -> bool:
        """
        Evaluate if a file matches collection rules
        
        Args:
            file_obj: File object
        
        Returns:
            True if file matches
        """
        if not self.rules:
            return False
        
        results = [rule.evaluate(file_obj) for rule in self.rules]
        
        if self.match_all:
            return all(results)  # AND
        else:
            return any(results)  # OR
    
    def update_files(self):
        """Update file list based on rules"""
        if self.collection_type != CollectionType.SMART or not self.auto_update:
            return
        
        self.file_ids = []
        
        try:
            all_files = File.filter()
            
            for file_obj in all_files:
                if self.evaluate_file(file_obj):
                    self.file_ids.append(file_obj.id)
            
            self.updated_at = datetime.now()
            log.debug(f"Collection '{self.name}' updated: {len(self.file_ids)} files")
            
        except Exception as e:
            log.error(f"Failed to update collection: {e}")
    
    def add_file(self, file_id: str):
        """Manually add a file to collection"""
        if file_id not in self.file_ids:
            self.file_ids.append(file_id)
            self.updated_at = datetime.now()
    
    def remove_file(self, file_id: str):
        """Remove a file from collection"""
        if file_id in self.file_ids:
            self.file_ids.remove(file_id)
            self.updated_at = datetime.now()
    
    def get_file_count(self) -> int:
        """Get number of files in collection"""
        return len(self.file_ids)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert collection to dictionary"""
        return {
            'collection_id': self.collection_id,
            'name': self.name,
            'type': self.collection_type.value,
            'rules': [rule.to_dict() for rule in self.rules],
            'match_all': self.match_all,
            'file_ids': self.file_ids,
            'icon': self.icon,
            'color': self.color,
            'auto_update': self.auto_update,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Collection':
        """Create collection from dictionary"""
        collection = Collection(
            collection_id=data['collection_id'],
            name=data['name'],
            collection_type=CollectionType(data['type'])
        )
        
        collection.rules = [CollectionRule.from_dict(r) for r in data.get('rules', [])]
        collection.match_all = data.get('match_all', True)
        collection.file_ids = data.get('file_ids', [])
        collection.icon = data.get('icon', 'folder')
        collection.color = data.get('color', '#4CAF50')
        collection.auto_update = data.get('auto_update', True)
        
        if 'created_at' in data:
            collection.created_at = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data:
            collection.updated_at = datetime.fromisoformat(data['updated_at'])
        
        return collection


class CollectionManager:
    """Manages smart collections"""
    
    def __init__(self):
        """Initialize collection manager"""
        self.collections: Dict[str, Collection] = {}
        self._init_preset_collections()
    
    def _init_preset_collections(self):
        """Initialize preset collections"""
        # High Quality collection
        high_quality = Collection(
            name="High Quality",
            collection_type=CollectionType.PRESET
        )
        high_quality.add_rule(CollectionRule(
            "ai_metadata.tags.quality.resolution_score",
            RuleOperator.GREATER_THAN,
            0.8
        ))
        high_quality.icon = "star"
        high_quality.color = "#FFD700"
        self.collections[high_quality.collection_id] = high_quality
        
        # Outdoor Shots collection
        outdoor = Collection(
            name="Outdoor Shots",
            collection_type=CollectionType.PRESET
        )
        outdoor.add_rule(CollectionRule(
            "ai_metadata.tags.scenes",
            RuleOperator.CONTAINS,
            "outdoor"
        ))
        outdoor.icon = "landscape"
        outdoor.color = "#4CAF50"
        self.collections[outdoor.collection_id] = outdoor
        
        # People collection
        people = Collection(
            name="With People",
            collection_type=CollectionType.PRESET
        )
        people.add_rule(CollectionRule(
            "ai_metadata.tags.objects",
            RuleOperator.CONTAINS,
            "person"
        ))
        people.icon = "people"
        people.color = "#2196F3"
        self.collections[people.collection_id] = people
        
        log.info("Initialized preset collections")
    
    def create_collection(self, name: str, collection_type: CollectionType = CollectionType.SMART) -> Collection:
        """
        Create a new collection
        
        Args:
            name: Collection name
            collection_type: Type of collection
        
        Returns:
            Collection object
        """
        collection = Collection(name=name, collection_type=collection_type)
        self.collections[collection.collection_id] = collection
        
        log.info(f"Created collection: {name}")
        return collection
    
    def get_collection(self, collection_id: str) -> Optional[Collection]:
        """Get collection by ID"""
        return self.collections.get(collection_id)
    
    def get_all_collections(self) -> List[Collection]:
        """Get all collections"""
        return list(self.collections.values())
    
    def delete_collection(self, collection_id: str):
        """Delete a collection"""
        if collection_id in self.collections:
            collection = self.collections[collection_id]
            
            # Don't delete preset collections
            if collection.collection_type == CollectionType.PRESET:
                log.warning("Cannot delete preset collection")
                return
            
            del self.collections[collection_id]
            log.info(f"Deleted collection: {collection.name}")
    
    def update_all_collections(self):
        """Update all smart collections"""
        for collection in self.collections.values():
            if collection.collection_type == CollectionType.SMART and collection.auto_update:
                collection.update_files()
        
        log.info("Updated all smart collections")
    
    def update_collection(self, collection_id: str):
        """Update a specific collection"""
        collection = self.get_collection(collection_id)
        if collection:
            collection.update_files()
    
    def get_files_in_collection(self, collection_id: str) -> List[str]:
        """Get all file IDs in a collection"""
        collection = self.get_collection(collection_id)
        if collection:
            return collection.file_ids
        return []
    
    def find_collections_for_file(self, file_id: str) -> List[str]:
        """
        Find all collections containing a file
        
        Args:
            file_id: File ID
        
        Returns:
            List of collection IDs
        """
        collection_ids = []
        
        for collection in self.collections.values():
            if file_id in collection.file_ids:
                collection_ids.append(collection.collection_id)
        
        return collection_ids
    
    def load_from_project(self, project_data: Dict[str, Any]):
        """
        Load collections from project data
        
        Args:
            project_data: Project data dictionary
        """
        try:
            collections_data = project_data.get('collections', [])
            
            for coll_data in collections_data:
                collection = Collection.from_dict(coll_data)
                self.collections[collection.collection_id] = collection
            
            log.info(f"Loaded {len(collections_data)} collections from project")
            
        except Exception as e:
            log.error(f"Failed to load collections: {e}")
    
    def save_to_project(self) -> List[Dict[str, Any]]:
        """
        Save collections to project data format
        
        Returns:
            List of collection dictionaries
        """
        # Don't save preset collections to project
        user_collections = [
            coll.to_dict()
            for coll in self.collections.values()
            if coll.collection_type != CollectionType.PRESET
        ]
        
        return user_collections


# Global collection manager instance
_collection_manager = None

def get_collection_manager() -> CollectionManager:
    """Get global collection manager instance"""
    global _collection_manager
    if _collection_manager is None:
        _collection_manager = CollectionManager()
    return _collection_manager
