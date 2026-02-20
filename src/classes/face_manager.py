"""
 @file
 @brief Face detection, recognition, and people management
 @author Flowcut Development Team

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
 This file is part of OpenShot Video Editor (http://www.openshot.org)
"""

import os
import json
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict

from classes.logger import log
from classes import info
from classes.app import get_app
from classes.query import File


class Person:
    """Represents a recognized person"""
    
    def __init__(self, person_id: str = None, name: str = "Unknown"):
        """
        Initialize a person
        
        Args:
            person_id: Unique person ID
            name: Person's name
        """
        self.person_id = person_id or str(uuid.uuid4())
        self.name = name
        self.face_samples: List[Dict[str, Any]] = []
        self.file_appearances: Dict[str, List[float]] = defaultdict(list)  # file_id -> timestamps
        self.created_at = datetime.now()
        self.thumbnail_path = None
    
    def add_face_sample(self, face_data: Dict[str, Any], file_id: str, timestamp: float = 0.0):
        """
        Add a face sample for this person
        
        Args:
            face_data: Face detection data
            file_id: File ID where face was detected
            timestamp: Timestamp in video (0 for images)
        """
        self.face_samples.append({
            'face_data': face_data,
            'file_id': file_id,
            'timestamp': timestamp,
            'added_at': datetime.now().isoformat()
        })
        
        self.file_appearances[file_id].append(timestamp)
    
    def get_file_count(self) -> int:
        """Get number of files this person appears in"""
        return len(self.file_appearances)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'person_id': self.person_id,
            'name': self.name,
            'face_samples': self.face_samples,
            'file_appearances': dict(self.file_appearances),
            'created_at': self.created_at.isoformat(),
            'thumbnail_path': self.thumbnail_path
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Person':
        """Create Person from dictionary"""
        person = Person(data['person_id'], data['name'])
        person.face_samples = data.get('face_samples', [])
        person.file_appearances = defaultdict(list, data.get('file_appearances', {}))
        person.thumbnail_path = data.get('thumbnail_path')
        
        if 'created_at' in data:
            person.created_at = datetime.fromisoformat(data['created_at'])
        
        return person


class FaceManager:
    """Manages face detection, recognition, and people database"""
    
    def __init__(self):
        """Initialize face manager"""
        self.people_db_path = os.path.join(info.USER_PATH, 'ai_people_database.json')
        self.people: Dict[str, Person] = {}
        self.face_clusters: Dict[str, List[str]] = {}  # cluster_id -> list of face_ids
        self._load_database()
    
    def _load_database(self):
        """Load people database from disk"""
        try:
            if os.path.exists(self.people_db_path):
                with open(self.people_db_path, 'r') as f:
                    data = json.load(f)
                    
                    for person_data in data.get('people', []):
                        person = Person.from_dict(person_data)
                        self.people[person.person_id] = person
                    
                    self.face_clusters = data.get('face_clusters', {})
                    
                log.info(f"Loaded {len(self.people)} people from database")
        except Exception as e:
            log.error(f"Failed to load people database: {e}")
    
    def _save_database(self):
        """Save people database to disk"""
        try:
            data = {
                'people': [person.to_dict() for person in self.people.values()],
                'face_clusters': self.face_clusters,
                'version': '1.0',
                'updated_at': datetime.now().isoformat()
            }
            
            with open(self.people_db_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            log.debug("Saved people database")
        except Exception as e:
            log.error(f"Failed to save people database: {e}")
    
    def detect_faces_in_file(self, file_id: str) -> List[Dict[str, Any]]:
        """
        Detect faces in a file
        
        Args:
            file_id: File ID
        
        Returns:
            List of detected faces
        """
        try:
            file_obj = File.get(id=file_id)
            if not file_obj:
                return []
            
            ai_metadata = file_obj.get_ai_metadata()
            if not ai_metadata.get('analyzed'):
                return []
            
            faces = ai_metadata.get('faces', [])
            return faces
            
        except Exception as e:
            log.error(f"Failed to detect faces in file {file_id}: {e}")
            return []
    
    def cluster_faces(self, faces: List[Dict[str, Any]], similarity_threshold: float = 0.8) -> Dict[str, List[int]]:
        """
        Cluster similar faces together
        
        Args:
            faces: List of face detection data
            similarity_threshold: Similarity threshold for clustering
        
        Returns:
            Dictionary mapping cluster_id to list of face indices
        """
        # Simple clustering based on face features
        # In a real implementation, this would use face embeddings and proper clustering
        
        clusters = {}
        cluster_id = 0
        
        for i, face in enumerate(faces):
            # Check if face belongs to existing cluster
            assigned = False
            
            for cid, indices in clusters.items():
                # Compare with first face in cluster (simplified)
                if self._faces_similar(face, faces[indices[0]], similarity_threshold):
                    clusters[cid].append(i)
                    assigned = True
                    break
            
            if not assigned:
                # Create new cluster
                clusters[f"cluster_{cluster_id}"] = [i]
                cluster_id += 1
        
        return clusters
    
    def _faces_similar(self, face1: Dict[str, Any], face2: Dict[str, Any], threshold: float) -> bool:
        """
        Check if two faces are similar
        Simplified implementation - in production, use face embeddings
        
        Args:
            face1: First face data
            face2: Second face data
            threshold: Similarity threshold
        
        Returns:
            True if faces are similar
        """
        # Simplified: compare bounding box sizes and positions
        bbox1 = face1.get('bounding_box', {})
        bbox2 = face2.get('bounding_box', {})
        
        if not bbox1 or not bbox2:
            return False
        
        # Compare box dimensions (very simplified)
        # In reality, use face embeddings and cosine similarity
        return True  # Placeholder
    
    def create_person(self, name: str = "Unknown") -> Person:
        """
        Create a new person entry
        
        Args:
            name: Person's name
        
        Returns:
            Person object
        """
        person = Person(name=name)
        self.people[person.person_id] = person
        self._save_database()
        
        log.info(f"Created person: {name} ({person.person_id})")
        return person
    
    def add_face_to_person(self, person_id: str, face_data: Dict[str, Any], file_id: str, timestamp: float = 0.0):
        """
        Add a face sample to a person
        
        Args:
            person_id: Person ID
            face_data: Face detection data
            file_id: File ID
            timestamp: Timestamp in video
        """
        if person_id not in self.people:
            log.warning(f"Person {person_id} not found")
            return
        
        person = self.people[person_id]
        person.add_face_sample(face_data, file_id, timestamp)
        self._save_database()
        
        log.debug(f"Added face sample to person {person.name}")
    
    def identify_face(self, face_data: Dict[str, Any]) -> Optional[Tuple[str, float]]:
        """
        Identify a face by comparing with known people
        
        Args:
            face_data: Face detection data
        
        Returns:
            Tuple of (person_id, confidence) or None if not identified
        """
        # Simplified implementation
        # In production, use face recognition algorithms
        
        best_match = None
        best_confidence = 0.0
        
        for person_id, person in self.people.items():
            if not person.face_samples:
                continue
            
            # Compare with person's face samples
            confidence = self._compare_face_to_person(face_data, person)
            
            if confidence > best_confidence and confidence > 0.7:  # Threshold
                best_confidence = confidence
                best_match = person_id
        
        if best_match:
            return (best_match, best_confidence)
        
        return None
    
    def _compare_face_to_person(self, face_data: Dict[str, Any], person: Person) -> float:
        """
        Compare a face to a person's known faces
        
        Args:
            face_data: Face to compare
            person: Person object
        
        Returns:
            Similarity confidence (0.0 to 1.0)
        """
        # Simplified - in production use face embeddings
        return 0.5  # Placeholder
    
    def get_person(self, person_id: str) -> Optional[Person]:
        """Get person by ID"""
        return self.people.get(person_id)
    
    def get_all_people(self) -> List[Person]:
        """Get all people"""
        return list(self.people.values())
    
    def rename_person(self, person_id: str, new_name: str):
        """
        Rename a person
        
        Args:
            person_id: Person ID
            new_name: New name
        """
        if person_id in self.people:
            self.people[person_id].name = new_name
            self._save_database()
            log.info(f"Renamed person {person_id} to {new_name}")
    
    def delete_person(self, person_id: str):
        """
        Delete a person
        
        Args:
            person_id: Person ID
        """
        if person_id in self.people:
            del self.people[person_id]
            self._save_database()
            log.info(f"Deleted person {person_id}")
    
    def merge_people(self, person_id1: str, person_id2: str, keep_name: str = None):
        """
        Merge two people into one
        
        Args:
            person_id1: First person ID
            person_id2: Second person ID
            keep_name: Name to keep (defaults to first person's name)
        """
        if person_id1 not in self.people or person_id2 not in self.people:
            log.warning("Cannot merge: one or both people not found")
            return
        
        person1 = self.people[person_id1]
        person2 = self.people[person_id2]
        
        # Merge face samples
        person1.face_samples.extend(person2.face_samples)
        
        # Merge file appearances
        for file_id, timestamps in person2.file_appearances.items():
            person1.file_appearances[file_id].extend(timestamps)
        
        # Update name if specified
        if keep_name:
            person1.name = keep_name
        
        # Delete second person
        del self.people[person_id2]
        self._save_database()
        
        log.info(f"Merged person {person_id2} into {person_id1}")
    
    def get_files_with_person(self, person_id: str) -> List[str]:
        """
        Get all files where a person appears
        
        Args:
            person_id: Person ID
        
        Returns:
            List of file IDs
        """
        if person_id not in self.people:
            return []
        
        person = self.people[person_id]
        return list(person.file_appearances.keys())
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get face recognition statistics"""
        total_faces = sum(len(p.face_samples) for p in self.people.values())
        
        return {
            'total_people': len(self.people),
            'total_faces': total_faces,
            'named_people': len([p for p in self.people.values() if p.name != "Unknown"]),
            'clusters': len(self.face_clusters)
        }


# Global face manager instance
_face_manager = None

def get_face_manager() -> FaceManager:
    """Get global face manager instance"""
    global _face_manager
    if _face_manager is None:
        _face_manager = FaceManager()
    return _face_manager
