import pytest
from fastapi import HTTPException
from api.auth import (
    create_access_token,
    verify_api_key,
    authenticate_admin
)
from unittest.mock import patch, MagicMock

def test_create_access_token():
    token = create_access_token({"sub": "test"})
    assert isinstance(token, str)
    assert len(token) > 0

def test_verify_api_key_success():
    with patch("api.auth.settings") as mock_settings:
        mock_settings.api_key.get_secret_value.return_value = "secret_key"
        assert verify_api_key("secret_key") == "secret_key"

def test_verify_api_key_failure():
    with patch("api.auth.settings") as mock_settings:
        mock_settings.api_key.get_secret_value.return_value = "secret_key"
        with pytest.raises(HTTPException) as exc:
            verify_api_key("wrong_key")
        assert exc.value.status_code == 401

def test_authenticate_admin():
    with patch("api.auth.settings") as mock_settings:
        mock_settings.admin_username = "admin"
        mock_settings.admin_password.get_secret_value.return_value = "secret"
        
        assert authenticate_admin("admin", "secret")
        assert not authenticate_admin("admin", "wrong")
        assert not authenticate_admin("wrong", "secret")
