"""
Firestore service for storing and retrieving chat messages.

Collection structure:
- Collection: chats
- Documents: {userId}/messages/{messageId}
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore

from app.models.chat_models import ChatMessage


@dataclass
class ChatFirestore:
    """
    Firestore service for chat message storage.

    Structure:
    - Collection: chats
    - Each document ID is the userId
    - Subcollection: messages/{messageId}
    """

    _initialized: bool = field(default=False, init=False)
    _db: Optional[firestore.Client] = field(default=None, init=False)

    def _initialize(self) -> None:
        """Initialize Firebase Admin SDK and Firestore client."""
        if self._initialized:
            return

        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        if not cred_path:
            raise ValueError(
                "FIREBASE_CREDENTIALS_PATH environment variable is required"
            )

        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

        self._db = firestore.client()
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "ChatFirestore":
        """Get singleton instance of ChatFirestore."""
        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance

    def _get_db(self) -> firestore.Client:
        """Get Firestore client, initializing if needed."""
        if not self._initialized:
            self._initialize()
        return self._db

    async def add_message(
        self,
        user_id: str,
        text: str,
        role: str,
        sources: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> str:
        """
        Add a message to Firestore.

        Args:
            user_id: The user ID
            text: The message text
            role: "user" or "model"
            sources: Optional nutrition analysis result
            timestamp: Optional timestamp (defaults to now)

        Returns:
            The message ID
        """
        db = self._get_db()

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        message_data = {
            "text": text,
            "role": role,
            "sources": sources,
            "timestamp": timestamp,
            "userId": user_id,
        }

        user_chats_ref = db.collection("chats").document(user_id)
        messages_ref = user_chats_ref.collection("messages")
        doc_ref = messages_ref.document()

        doc_ref.set(message_data)
        return doc_ref.id

    async def get_messages(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[List[ChatMessage], int]:
        """
        Get messages for a user with pagination.

        Args:
            user_id: The user ID
            offset: Number of messages to skip
            limit: Maximum number of messages to return

        Returns:
            Tuple of (messages list, total count)
        """
        db = self._get_db()

        user_chats_ref = db.collection("chats").document(user_id)
        messages_ref = user_chats_ref.collection("messages")

        query = messages_ref.order_by("timestamp", direction=firestore.Query.DESCENDING)

        total_result = query.count().get()
        total = total_result[0][0].value if total_result else 0

        query = query.offset(offset).limit(limit)
        docs = query.get()

        messages = []
        for doc in docs:
            data = doc.to_dict()
            message: ChatMessage = {
                "role": data.get("role", "user"),
                "text": data.get("text", ""),
                "sources": data.get("sources"),
                "timestamp": data.get("timestamp"),
            }
            if isinstance(message["timestamp"], datetime):
                message["timestamp"] = message["timestamp"].isoformat()
            messages.append(message)

        messages.reverse()
        return messages, total

    async def get_message_by_id(
        self,
        user_id: str,
        message_id: str,
    ) -> Optional[ChatMessage]:
        """
        Get a specific message by ID.

        Args:
            user_id: The user ID
            message_id: The message ID

        Returns:
            The message or None if not found
        """
        db = self._get_db()

        doc_ref = (
            db.collection("chats")
            .document(user_id)
            .collection("messages")
            .document(message_id)
        )
        doc = doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        message: ChatMessage = {
            "role": data.get("role", "user"),
            "text": data.get("text", ""),
            "sources": data.get("sources"),
            "timestamp": data.get("timestamp"),
        }
        if isinstance(message["timestamp"], datetime):
            message["timestamp"] = message["timestamp"].isoformat()
        return message


chat_firestore = ChatFirestore.get_instance()
