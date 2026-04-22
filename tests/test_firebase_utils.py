import json
import os
from unittest.mock import patch, MagicMock

import pytest
from firebase_admin import credentials

from app.utils.firebase_utils import deserialize_firebase_credentials, initialize_firebase


SERVICE_ACCOUNT_JSON = json.dumps({
  
})


class TestDeserializeFirebaseCredentials:
    """Test deserialize_firebase_credentials function."""

    def test_deserialize_returns_certificate_credential(self):
        """JSON string should deserialize into a Certificate credential."""
        cred = deserialize_firebase_credentials(SERVICE_ACCOUNT_JSON)

        assert isinstance(cred, credentials.Certificate)

    def test_deserialize_contains_project_id(self):
        """Deserialized credential should have correct project_id."""
        cred = deserialize_firebase_credentials(SERVICE_ACCOUNT_JSON)

        assert cred.project_id == "mealai-f58b5"

    def test_deserialize_creates_valid_credential(self):
        """Deserialized credential should be a valid Certificate instance."""
        cred = deserialize_firebase_credentials(SERVICE_ACCOUNT_JSON)

        assert isinstance(cred, credentials.Certificate)
        assert cred.project_id == "mealai-f58b5"

    def test_deserialize_invalid_json_raises(self):
        """Invalid JSON string should raise ValueError."""
        with pytest.raises(json.JSONDecodeError):
            deserialize_firebase_credentials("not valid json")


class TestInitializeFirebase:
    """Test initialize_firebase with various credential inputs."""

    @patch.dict(os.environ, {"FIREBASE_CREDENTIALS_JSON": SERVICE_ACCOUNT_JSON})
    @patch("app.utils.firebase_utils.firebase_admin.initialize_app")
    @patch("app.utils.firebase_utils.firestore.client")
    def test_uses_json_env_var_when_set(self, mock_firestore_client, mock_init_app):
        """When FIREBASE_CREDENTIALS_JSON is set, should use it directly."""
        mock_firestore_client.return_value = MagicMock()

        initialize_firebase()

        mock_init_app.assert_called_once()
        assert mock_init_app.call_args[0][0] is not None

    @patch.dict(os.environ, {"FIREBASE_CREDENTIALS_PATH": "/path/to/creds.json"}, clear=True)
    @patch("app.utils.firebase_utils.credentials.Certificate")
    @patch("app.utils.firebase_utils.firebase_admin.initialize_app")
    @patch("app.utils.firebase_utils.firestore.client")
    def test_uses_path_env_var_when_json_not_set(self, mock_firestore_client, mock_init_app, mock_cert):
        """When FIREBASE_CREDENTIALS_PATH is set but not JSON, should use path."""
        mock_cert.return_value = MagicMock()
        mock_firestore_client.return_value = MagicMock()

        initialize_firebase()

        mock_cert.assert_called_once_with("/path/to/creds.json")

    @patch.dict(os.environ, {}, clear=True)
    @patch("app.utils.firebase_utils.google.auth.default")
    @patch("app.utils.firebase_utils.firebase_admin.initialize_app")
    @patch("app.utils.firebase_utils.firestore.client")
    def test_uses_google_auth_when_no_creds_set(self, mock_firestore_client, mock_init_app, mock_google_auth):
        """When neither JSON nor path is set, should fall back to google.auth.default."""
        mock_google_auth.return_value = (MagicMock(), MagicMock())
        mock_firestore_client.return_value = MagicMock()

        initialize_firebase()

        mock_init_app.assert_called_once()
        call_kwargs = mock_init_app.call_args.kwargs
        assert "credential" not in call_kwargs or call_kwargs.get("credential") is None