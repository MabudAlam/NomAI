"""
Firestore service for storing and retrieving chat messages.

Document structure:
- Collection: chats
- Document ID: {userId}
- Document: {
    userId: string,
    messages: array<{
      text: string,
      role: "user" | "model",
      sources: object | null,
      timestamp: timestamp
    }>,
    updatedAt: timestamp
  }
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore

from app.models.chat_models import ChatMessage


MAX_MESSAGES = 50


@dataclass
class ChatFirestore:
    """
    Firestore service for chat message storage.

    Structure:
    - Collection: chats
    - Each document ID is the userId
    - Document contains array of messages (max 50, oldest trimmed)
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

        self._db = firestore.client(database_id="mealai")
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

    def _trim_old_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keep only the last MAX_MESSAGES based on timestamp."""
        if len(messages) <= MAX_MESSAGES:
            return messages

        sorted_msgs = sorted(
            messages,
            key=lambda x: x.get("timestamp", datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True
        )
        return sorted_msgs[:MAX_MESSAGES]

    def add_message(
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

        doc_ref = db.collection("chats").document(user_id)

        doc = doc_ref.get()
        doc_dict = doc.to_dict() if doc.exists else {}

        messages = list(doc_dict.get("messages", []))
        messages.append({
            "text": text,
            "role": role,
            "sources": sources,
            "timestamp": timestamp,
        })

        messages = self._trim_old_messages(messages)

        write_data = {
            "userId": user_id,
            "messages": messages,
            "updatedAt": timestamp,
        }

        doc_ref.set(write_data, merge=True)
        return f"msg_{timestamp.timestamp()}"

    def get_messages(
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

        doc_ref = db.collection("chats").document(user_id)
        doc = doc_ref.get()

        if not doc.exists:
            return [], 0

        doc_dict = doc.to_dict()
        messages_list = doc_dict.get("messages", [])

        messages_list.sort(
            key=lambda x: x.get("timestamp") or datetime.min.replace(tzinfo=timezone.utc)
        )

        total = len(messages_list)

        paginated = messages_list[offset : offset + limit]

        result: List[ChatMessage] = []
        for msg in paginated:
            timestamp = msg.get("timestamp")
            if isinstance(timestamp, datetime):
                timestamp = timestamp.isoformat()
            result.append(
                {
                    "role": msg.get("role", "user"),
                    "text": msg.get("text", ""),
                    "sources": msg.get("sources"),
                    "timestamp": timestamp,
                }
            )

        return result, total

    def get_all_messages_for_context(
        self,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all messages for AI context (sorted oldest first).

        Args:
            user_id: The user ID

        Returns:
            List of messages for langchain context
        """
        messages, _ = self.get_messages(user_id, offset=0, limit=MAX_MESSAGES)

        formatted = []
        for msg in messages:
            formatted.append({
                "role": msg["role"],
                "content": msg["text"],
            })

        return formatted


chat_firestore = ChatFirestore.get_instance()
