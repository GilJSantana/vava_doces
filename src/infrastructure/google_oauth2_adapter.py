"""Google OAuth2 Authentication and Drive Permission Validation.

This module handles:
1. OAuth2 login flow via Google
2. Validation of user email
3. Drive permission checking for access control
4. Session state management for authentication
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import streamlit as st
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# OAuth2 Scopes
OAUTH2_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]


class GoogleOAuth2Adapter:
    """Handles OAuth2 authentication and user session management."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """Initialize OAuth2 adapter.

        Args:
            client_id: OAuth2 Client ID from Google Cloud Console
            client_secret: OAuth2 Client Secret from Google Cloud Console
            redirect_uri: Redirect URI for OAuth2 callback configured in Streamlit secrets
        """
        self.client_id = client_id
        self.client_secret = client_secret
        # Keep redirect URI exactly as configured in st.secrets/GCP Console.
        self.redirect_uri = redirect_uri

    @staticmethod
    def _sanitize_secret_value(value: str) -> str:
        """Normalize OAuth credential values to avoid hidden whitespace/newline issues."""
        return str(value).strip().replace("\r", "").replace("\n", "")

    @staticmethod
    def _get_redirect_uri_from_secrets() -> str:
        """Return the exact OAuth2 redirect URI configured in Streamlit secrets."""
        configured = st.secrets.get("OAUTH2_REDIRECT_URI")
        if not configured:
            raise ValueError("Missing required secret: OAUTH2_REDIRECT_URI")
        return str(configured)

    def get_login_url(self) -> str:
        """Generate Google OAuth2 login URL."""
        redirect_uri = self._get_redirect_uri_from_secrets()
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={self._sanitize_secret_value(self.client_id)}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope={'+'.join(OAUTH2_SCOPES)}&"
            f"access_type=online&"
            f"prompt=select_account"
        )
        return auth_url

    def exchange_code_for_token(self, code: str) -> dict | None:
        """Exchange authorization code for access token.

        Credentials are sent as form-urlencoded body (not headers).
        redirect_uri is read directly from st.secrets to guarantee
        an exact match with the GCP Console registration.

        Args:
            code: Authorization code from OAuth2 callback

        Returns:
            Dictionary with access_token, id_token, etc. or None on error
        """
        import urllib.error
        import urllib.parse
        import urllib.request

        try:
            token_url = "https://oauth2.googleapis.com/token"

            # Canonical values — stripped of any hidden whitespace / newlines
            redirect_uri = self._get_redirect_uri_from_secrets()
            client_id = self._sanitize_secret_value(self.client_id)
            client_secret = self._sanitize_secret_value(self.client_secret)

            logger.debug("Exchanging OAuth2 code for token at %s", token_url)

            payload = {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
            data = urllib.parse.urlencode(payload).encode("utf-8")

            req = urllib.request.Request(
                token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )

            with urllib.request.urlopen(req) as response:
                token_data = json.loads(response.read().decode())
                logger.info("OAuth2 token exchange successful")
                return token_data

        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            logger.error("OAuth2 token exchange HTTP %s: %s", e.code, body)
            return None
        except Exception as e:
            logger.error("OAuth2 token exchange failed: %s", e)
            return None

    def get_user_email_from_token(self, access_token: str) -> str | None:
        """Extract user email from OAuth2 access token.

        Args:
            access_token: OAuth2 access token

        Returns:
            User's email address or None on error
        """
        import urllib.request
        import json

        try:
            url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                user_info = json.loads(response.read().decode())
                return user_info.get("email")
        except Exception as e:
            logger.error("Failed to get user email from token: %s", e)
            return None


class GoogleDrivePermissionChecker:
    """Checks if a user has appropriate access to Drive resources."""

    def __init__(self, credential_file: str):
        """Initialize permission checker with service account credentials.

        Args:
            credential_file: Path to service account JSON key file
        """
        self.credential_file = credential_file
        self._service = None

    @property
    def service(self):
        """Build and cache the Drive API service."""
        if self._service is None:
            try:
                credentials = ServiceAccountCredentials.from_service_account_file(
                    self.credential_file,
                    scopes=DRIVE_SCOPES,
                )
                self._service = build("drive", "v3", credentials=credentials)
            except Exception as e:
                logger.error("Failed to build Drive service: %s", e)
        return self._service

    def check_user_permission_on_file(
        self,
        file_id: str,
        user_email: str,
        min_role: str = "reader",
    ) -> bool:
        """Check if user has at least the specified role on a Drive file.

        Args:
            file_id: Google Drive file ID
            user_email: User's email address
            min_role: Minimum required role ('reader', 'writer', 'owner')

        Returns:
            True if user has permission, False otherwise
        """
        allowed_roles = {"owner", "writer", "reader"}

        try:
            if self.service is None:
                logger.error("Drive service not initialized")
                return False

            # Get the file's permissions (Drive API pageSize=100)
            logger.debug("Checking permissions for user %s on file %s", user_email, file_id)
            permissions_result = self.service.permissions().list(
                fileId=file_id,
                fields="permissions(emailAddress,role,type)",
                pageSize=100,
            ).execute()

            permissions = permissions_result.get("permissions", [])
            logger.debug("Retrieved %d permission(s) from file", len(permissions))

            for permission in permissions:
                # Extract email and role safely
                perm_email = permission.get("emailAddress", "").strip().lower()
                perm_role = permission.get("role", "").strip().lower()

                # Normalize user_email for comparison
                user_email_normalized = str(user_email).strip().lower()

                # Check for direct email match
                if perm_email == user_email_normalized and perm_email:
                    if perm_role in allowed_roles:
                        logger.info(
                            "User %s has permission '%s' on file %s",
                            user_email,
                            perm_role,
                            file_id,
                        )
                        return True
                    else:
                        logger.warning(
                            "User %s has role '%s' which is not in allowed roles: %s",
                            user_email,
                            perm_role,
                            allowed_roles,
                        )

            logger.warning(
                "User %s does not have required permission on file %s",
                user_email,
                file_id,
            )
            return False

        except HttpError as e:
            if e.resp.status == 404:
                logger.error("File %s not found in Drive", file_id)
            elif e.resp.status == 403:
                logger.error(
                    "Permission denied. Service account may not have access to file %s",
                    file_id,
                )
            else:
                logger.error("HttpError checking permissions: %s", e)
            return False
        except Exception as e:
            logger.error("Error checking permissions: %s", e)
            return False

    def check_user_permission_on_folder(
        self,
        folder_id: str,
        user_email: str,
        min_role: str = "reader",
    ) -> bool:
        """Check if user has at least the specified role on a Drive folder.

        Args:
            folder_id: Google Drive folder ID
            user_email: User's email address
            min_role: Minimum required role

        Returns:
            True if user has permission, False otherwise
        """
        return self.check_user_permission_on_file(folder_id, user_email, min_role)


def init_session_state_auth():
    """Initialize authentication-related session state variables."""
    if "user_email" not in st.session_state:
        st.session_state["user_email"] = None
    if "auth_user_email" not in st.session_state:
        st.session_state["auth_user_email"] = None
    if "auth_access_token" not in st.session_state:
        st.session_state["auth_access_token"] = None
    if "auth_is_authorized" not in st.session_state:
        st.session_state["auth_is_authorized"] = False
    if "auth_login_attempted" not in st.session_state:
        st.session_state["auth_login_attempted"] = False


def is_user_authenticated() -> bool:
    """Check if user is currently authenticated."""
    return bool(st.session_state.get("user_email")) and bool(
        st.session_state.get("auth_access_token")
    )


def is_user_authorized() -> bool:
    """Check if user is authorized to access the application."""
    return bool(st.session_state.get("auth_is_authorized"))


def set_user_authenticated(email: str, access_token: str):
    """Set user as authenticated."""
    st.session_state["user_email"] = email
    st.session_state["auth_user_email"] = email
    st.session_state["auth_access_token"] = access_token
    st.session_state["auth_login_attempted"] = True


def set_user_authorized(is_authorized: bool):
    """Set user authorization status."""
    st.session_state["auth_is_authorized"] = is_authorized


def clear_auth_session():
    """Clear all authentication session state."""
    st.session_state["user_email"] = None
    st.session_state["auth_user_email"] = None
    st.session_state["auth_access_token"] = None
    st.session_state["auth_is_authorized"] = False
    st.session_state["auth_login_attempted"] = False

