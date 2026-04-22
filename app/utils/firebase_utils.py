import json
import os

import firebase_admin
from firebase_admin import credentials, firestore
import google.auth

DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "mealai")


def deserialize_firebase_credentials(json_string: str) -> credentials.Certificate:
    """
    Deserialize a Firebase service account JSON string into a Certificate credential.
    """
    cred_dict = json.loads(json_string)
    return credentials.Certificate(cred_dict)


def initialize_firebase() -> firestore.Client:
    """
    Initialize Firebase Admin SDK and return Firestore client.
    Uses FIREBASE_CREDENTIALS_JSON if set (Railway/deployed env),
    FIREBASE_CREDENTIALS_PATH if set (local dev),
    otherwise uses google.auth.default() (Cloud Run/workload identity).
    """
    if firebase_admin._apps:
        return firestore.client(database_id=DATABASE_ID)

    cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if cred_json:
        cred = deserialize_firebase_credentials(cred_json)
        firebase_admin.initialize_app(cred)
    else:
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        if cred_path:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            credentials_anon, _ = google.auth.default()
            firebase_admin.initialize_app()

    return firestore.client(database_id=DATABASE_ID)


def get_firestore() -> firestore.Client:
    """Get Firestore client instance."""
    return initialize_firebase()
