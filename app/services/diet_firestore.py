"""
Firestore service for storing and retrieving weekly diet plans.

Document structure:
- Collection: users/{userId}/diet/{dietId}
- Document: WeeklyDietOutput as dict
"""

import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from firebase_admin import firestore

from app.models.diet_model import WeeklyDietOutput
from app.utils.firebase_utils import get_firestore


@dataclass
class DietFirestore:
    """
    Firestore service for diet plan storage.

    Structure:
    - Collection: users/{userId}/diet
    - Each document is a WeeklyDietOutput with auto-generated dietId
    """

    _initialized: bool = field(default=False, init=False)
    _db: Optional[firestore.Client] = field(default=None, init=False)

    def _initialize(self) -> None:
        """Initialize Firebase Admin SDK and Firestore client."""
        if self._initialized:
            return

        self._db = get_firestore()
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "DietFirestore":
        """Get singleton instance of DietFirestore."""
        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance

    def _get_db(self) -> firestore.Client:
        """Get Firestore client, initializing if needed."""
        if not self._initialized:
            self._initialize()
        return self._db

    def _dict_to_weekly_diet(self, doc_dict: Dict[str, Any]) -> WeeklyDietOutput:
        """Convert Firestore document dict to WeeklyDietOutput."""
        created_at = doc_dict.get("createdAt")
        updated_at = doc_dict.get("updatedAt")

        if hasattr(created_at, "isoformat"):
            doc_dict["createdAt"] = created_at.isoformat()
        if hasattr(updated_at, "isoformat"):
            doc_dict["updatedAt"] = updated_at.isoformat()

        return WeeklyDietOutput(**doc_dict)

    def save(self, diet: WeeklyDietOutput) -> str:
        """
        Save a weekly diet plan to Firestore.

        Args:
            diet: WeeklyDietOutput to save

        Returns:
            The dietId of the saved document
        """
        db = self._get_db()

        self._mark_all_active_as_completed(diet.userId)

        diet_id = f"diet_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        diet.dietId = diet_id
        if diet.createdAt is None:
            diet.createdAt = now.isoformat()
        diet.updatedAt = now.isoformat()

        doc_ref = db.collection("users").document(diet.userId).collection("diet").document(diet_id)

        doc_dict = diet.model_dump()
        doc_dict["createdAt"] = now
        doc_dict["updatedAt"] = now

        doc_ref.set(doc_dict)
        return diet_id

    def _mark_all_active_as_completed(self, user_id: str) -> None:
        """Mark all active diets for a user as completed."""
        db = self._get_db()

        docs = (
            db.collection("users")
            .document(user_id)
            .collection("diet")
            .where("status", "==", "active")
            .get()
        )

        for doc in docs:
            doc.reference.update({"status": "completed", "updatedAt": datetime.now(timezone.utc)})

    def update(self, user_id: str, diet_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update specific fields of a diet document.

        Args:
            user_id: The user ID
            diet_id: The diet document ID
            updates: Dictionary of fields to update

        Returns:
            True if updated successfully
        """
        db = self._get_db()

        updates["updatedAt"] = datetime.now(timezone.utc)

        clean_updates = {}

        def process_value(value):
            if hasattr(value, 'model_dump'):
                return value.model_dump()
            elif isinstance(value, list):
                result = []
                for item in value:
                    result.append(process_value(item))
                return result
            else:
                return value

        for key, value in updates.items():
            clean_updates[key] = process_value(value)

        doc_ref = db.collection("users").document(user_id).collection("diet").document(diet_id)
        doc_ref.update(clean_updates)
        return True

    def get_active(self, user_id: str) -> Optional[tuple]:
        """
        Get the active weekly diet for a user.

        Args:
            user_id: The user ID

        Returns:
            Tuple of (diet_id, WeeklyDietOutput) or None
        """
        db = self._get_db()

        docs = (
            db.collection("users")
            .document(user_id)
            .collection("diet")
            .where("status", "==", "active")
            .get()
        )

        active_diets = []
        for doc in docs:
            doc_dict = doc.to_dict()
            diet = self._dict_to_weekly_diet(doc_dict)
            active_diets.append((doc.id, diet))

        if not active_diets:
            return None

        active_diets.sort(key=lambda x: x[1].createdAt or "", reverse=True)
        return active_diets[0]

    def get_by_id(self, user_id: str, diet_id: str) -> Optional[WeeklyDietOutput]:
        """
        Get a specific diet by ID.

        Args:
            user_id: The user ID
            diet_id: The diet document ID

        Returns:
            WeeklyDietOutput or None
        """
        db = self._get_db()

        doc_ref = db.collection("users").document(user_id).collection("diet").document(diet_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        return self._dict_to_weekly_diet(doc.to_dict())

    def get_history(
        self, user_id: str, limit: int = 10, offset: int = 0
    ) -> tuple[List[tuple[str, WeeklyDietOutput]], int]:
        """
        Get diet history for a user with pagination.
        Returns all diets regardless of status.

        Args:
            user_id: The user ID
            limit: Maximum number of diets to return
            offset: Number of diets to skip

        Returns:
            Tuple of (list of (diet_id, WeeklyDietOutput) tuples, total count)
        """
        db = self._get_db()

        collection_ref = (
            db.collection("users")
            .document(user_id)
            .collection("diet")
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
        )

        total = len(collection_ref.get())
        docs = collection_ref.offset(offset).limit(limit).get()

        diets = []
        for doc in docs:
            doc_dict = doc.to_dict()
            diets.append((doc.id, self._dict_to_weekly_diet(doc_dict)))

        return diets, total

    def mark_completed(self, user_id: str, diet_id: str) -> bool:
        """
        Mark a diet as completed.

        Args:
            user_id: The user ID
            diet_id: The diet document ID

        Returns:
            True if updated successfully
        """
        return self.update(user_id, diet_id, {"status": "completed"})

    def mark_modified(self, user_id: str, diet_id: str) -> bool:
        """
        Mark a diet as modified.

        Args:
            user_id: The user ID
            diet_id: The diet document ID

        Returns:
            True if updated successfully
        """
        return self.update(user_id, diet_id, {"status": "modified"})


diet_firestore = DietFirestore.get_instance()