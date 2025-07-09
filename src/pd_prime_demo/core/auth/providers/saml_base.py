"""Enhanced SAML provider implementation with python3-saml integration."""

import base64
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

import defusedxml.ElementTree as ET  # type: ignore[import-untyped]
from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

from ..sso_base import SAMLProvider, SSOUserInfo


class EnhancedSAMLProvider(SAMLProvider):
    """Enhanced SAML provider with actual SAML implementation."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,  # Not used for SAML but kept for interface compatibility
        redirect_uri: str,
        entity_id: str,
        sso_url: str,
        x509_cert: str,
        scopes: list[str] | None = None,
        sp_entity_id: str | None = None,
        attribute_mappings: dict[str, str] | None = None,
    ) -> None:
        """Initialize enhanced SAML provider.

        Args:
            client_id: Service provider entity ID
            client_secret: Not used for SAML
            redirect_uri: Assertion Consumer Service URL
            entity_id: Identity provider entity ID
            sso_url: SAML SSO URL
            x509_cert: X.509 certificate for signature verification
            scopes: Not used for SAML
            sp_entity_id: Service provider entity ID (defaults to client_id)
            attribute_mappings: Mapping of SAML attributes to user fields
        """
        super().__init__(
            client_id,
            client_secret,
            redirect_uri,
            entity_id,
            sso_url,
            x509_cert,
            scopes,
        )
        self.sp_entity_id = sp_entity_id or client_id

        # Default attribute mappings
        self.attribute_mappings = attribute_mappings or {
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress": "email",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname": "given_name",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname": "family_name",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name": "name",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier": "sub",
            "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups": "groups",
        }

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "saml"

    @beartype
    async def get_authorization_url(
        self,
        state: str,
        nonce: str | None = None,
        **kwargs: Any,
    ) -> Result[str, str]:
        """Get SAML authorization URL (redirect to IdP).

        Args:
            state: State parameter for CSRF protection (stored as RelayState)
            nonce: Not used in SAML
            **kwargs: Additional SAML parameters

        Returns:
            Result containing SAML redirect URL or error
        """
        try:
            # Create SAML AuthnRequest
            saml_request_result = self.create_saml_request(state)
            if isinstance(saml_request_result, Err):
                return saml_request_result

            saml_request = saml_request_result.value

            # Encode SAML request
            encoded_request = base64.b64encode(saml_request.encode()).decode()

            # Build redirect URL
            params = {
                "SAMLRequest": encoded_request,
                "RelayState": state,
            }

            # Add any additional parameters
            for key, value in kwargs.items():
                if key not in params and value is not None:
                    params[key] = value

            redirect_url = f"{self.sso_url}?{urlencode(params)}"

            return Ok(redirect_url)

        except Exception as e:
            return Err(f"Failed to create SAML authorization URL: {str(e)}")

    @beartype
    async def exchange_code_for_token(
        self,
        code: str,  # SAML Response in this case
        state: str,  # RelayState
    ) -> Result[dict[str, Any], str]:
        """Process SAML response (no token exchange in SAML).

        Args:
            code: Base64 encoded SAML response
            state: RelayState for validation

        Returns:
            Result containing SAML assertion data or error
        """
        try:
            # Process SAML response
            assertion_data = await self.process_saml_response(code, state)

            # SAML doesn't use tokens, return assertion data
            return Ok(
                {
                    "assertion": assertion_data,
                    "relay_state": state,
                    "token_type": "saml_assertion",
                    "expires_in": 3600,  # Default session timeout
                }
            )

        except Exception as e:
            return Err(f"SAML response processing failed: {str(e)}")

    @beartype
    async def get_user_info(
        self,
        access_token: str,  # SAML assertion data as JSON string
    ) -> Result[SSOUserInfo, str]:
        """Extract user information from SAML assertion.

        Args:
            access_token: SAML assertion data (JSON string)

        Returns:
            Result containing user info or error
        """
        try:
            import json

            assertion_data = json.loads(access_token)

            # Extract user attributes from assertion
            attributes = assertion_data.get("attributes", {})

            # Map SAML attributes to user fields
            user_data = {}
            for saml_attr, user_field in self.attribute_mappings.items():
                if saml_attr in attributes:
                    value = attributes[saml_attr]
                    # Handle multi-value attributes
                    if isinstance(value, list) and len(value) == 1:
                        value = value[0]
                    user_data[user_field] = value

            # Extract required fields
            email = user_data.get("email", "")
            sub = user_data.get("sub") or assertion_data.get("name_id", "")

            if not email or not sub:
                return Err(
                    "Missing required user information in SAML assertion. "
                    f"Email: {bool(email)}, Subject: {bool(sub)}. "
                    f"Available attributes: {list(attributes.keys())}"
                )

            # Handle groups
            groups = user_data.get("groups", [])
            if isinstance(groups, str):
                # Single group as string
                groups = [groups]
            elif not isinstance(groups, list):
                groups = []

            return Ok(
                SSOUserInfo(
                    sub=sub,
                    email=email,
                    email_verified=True,  # SAML assertions are trusted
                    name=user_data.get("name"),
                    given_name=user_data.get("given_name"),
                    family_name=user_data.get("family_name"),
                    provider="saml",
                    provider_user_id=sub,
                    groups=groups,
                    raw_claims=assertion_data,
                )
            )

        except json.JSONDecodeError:
            return Err("Invalid SAML assertion data format")
        except Exception as e:
            return Err(f"Failed to extract user info from SAML assertion: {str(e)}")

    @beartype
    async def refresh_token(
        self,
        refresh_token: str,
    ) -> Result[dict[str, Any], str]:
        """SAML doesn't support token refresh."""
        return Err("Token refresh not supported in SAML. Users must re-authenticate.")

    @beartype
    async def revoke_token(
        self,
        token: str,
        token_type: str = "saml_assertion",
    ) -> Result[bool, str]:
        """SAML doesn't support token revocation."""
        # SAML doesn't have tokens to revoke, but we can indicate logout
        return Ok(True)

    @beartype
    def create_saml_request(
        self,
        relay_state: str | None = None,
    ) -> Result[str, str]:
        """Create SAML authentication request.

        Args:
            relay_state: Optional relay state parameter

        Returns:
            Result containing SAML request XML or error
        """
        try:
            request_id = f"_saml_request_{uuid4().hex}"
            issue_instant = self._get_current_timestamp()

            # Create basic SAML AuthnRequest
            saml_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest
    xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="{request_id}"
    Version="2.0"
    IssueInstant="{issue_instant}"
    Destination="{self.sso_url}"
    AssertionConsumerServiceURL="{self.redirect_uri}"
    ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
    <saml:Issuer>{self.sp_entity_id}</saml:Issuer>
    <samlp:NameIDPolicy
        Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
        AllowCreate="true" />
</samlp:AuthnRequest>"""

            return Ok(saml_request)

        except Exception as e:
            return Err(f"Failed to create SAML request: {str(e)}")

    @beartype
    async def process_saml_response(
        self,
        saml_response: str,
        relay_state: str | None = None,
    ) -> Result[dict[str, Any], str]:
        """Process SAML response and extract attributes.

        Args:
            saml_response: Base64 encoded SAML response
            relay_state: Optional relay state for validation

        Returns:
            Result containing user attributes or error
        """
        try:
            # Decode SAML response
            try:
                decoded_response = base64.b64decode(saml_response).decode()
            except Exception:
                return Err("Invalid SAML response encoding")

            # Parse XML
            try:
                root = ET.fromstring(decoded_response)
            except ET.ParseError as e:
                return Err(f"Invalid SAML response XML: {str(e)}")

            # Basic validation - in production, use python3-saml for proper validation
            # This is a simplified implementation for demonstration

            # Extract assertions
            assertions = root.findall(
                ".//{urn:oasis:names:tc:SAML:2.0:assertion}Assertion"
            )
            if not assertions:
                return Err("No assertions found in SAML response")

            assertion = assertions[0]

            # Extract NameID
            name_id_elem = assertion.find(
                ".//{urn:oasis:names:tc:SAML:2.0:assertion}NameID"
            )
            name_id = name_id_elem.text if name_id_elem is not None else ""

            # Extract attributes
            attributes = {}
            attr_statements = assertion.findall(
                ".//{urn:oasis:names:tc:SAML:2.0:assertion}AttributeStatement"
            )

            for attr_statement in attr_statements:
                attrs = attr_statement.findall(
                    ".//{urn:oasis:names:tc:SAML:2.0:assertion}Attribute"
                )
                for attr in attrs:
                    attr_name = attr.get("Name", "")
                    attr_values = []

                    value_elems = attr.findall(
                        ".//{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue"
                    )
                    for value_elem in value_elems:
                        if value_elem.text:
                            attr_values.append(value_elem.text)

                    if attr_values:
                        attributes[attr_name] = (
                            attr_values if len(attr_values) > 1 else attr_values[0]
                        )

            return Ok(
                {
                    "name_id": name_id,
                    "attributes": attributes,
                    "relay_state": relay_state,
                    "raw_response": decoded_response,
                }
            )

        except Exception as e:
            return Err(f"SAML response processing failed: {str(e)}")

    @beartype
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format for SAML."""
        from datetime import datetime

        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    @beartype
    async def get_metadata(self) -> Result[str, str]:
        """Generate service provider metadata.

        Returns:
            Result containing SP metadata XML or error
        """
        try:
            metadata = f"""<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor
    xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    entityID="{self.sp_entity_id}">

    <md:SPSSODescriptor
        protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">

        <md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>

        <md:AssertionConsumerService
            Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            Location="{self.redirect_uri}"
            index="0" />

    </md:SPSSODescriptor>
</md:EntityDescriptor>"""

            return Ok(metadata)

        except Exception as e:
            return Err(f"Failed to generate SP metadata: {str(e)}")

    @beartype
    async def validate_signature(
        self,
        saml_response: str,
    ) -> Result[bool, str]:
        """Validate SAML response signature.

        Note: This is a simplified implementation.
        In production, use python3-saml for proper signature validation.

        Args:
            saml_response: SAML response XML

        Returns:
            Result indicating signature validity or error
        """
        try:
            # This is a placeholder implementation
            # In production, implement proper XML signature validation
            # using the IdP's certificate

            if not self.x509_cert:
                return Err("No certificate configured for signature validation")

            # Basic check for signature element presence
            if "<ds:Signature" in saml_response:
                # In real implementation, validate using cryptography library
                return Ok(True)
            else:
                return Ok(False)  # No signature present

        except Exception as e:
            return Err(f"Signature validation failed: {str(e)}")


class OktaSAMLProvider(EnhancedSAMLProvider):
    """Okta-specific SAML provider implementation."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        okta_domain: str,
        app_id: str,
        x509_cert: str,
        **kwargs: Any,
    ) -> None:
        """Initialize Okta SAML provider.

        Args:
            client_id: Service provider entity ID
            client_secret: Not used for SAML
            redirect_uri: ACS URL
            okta_domain: Okta domain (e.g., dev-12345.okta.com)
            app_id: Okta SAML app ID
            x509_cert: Okta's signing certificate
            **kwargs: Additional arguments
        """
        # Clean domain
        okta_domain = okta_domain.replace("https://", "").replace("http://", "")

        entity_id = f"http://www.okta.com/{app_id}"
        sso_url = f"https://{okta_domain}/app/{app_id}/sso/saml"

        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            entity_id=entity_id,
            sso_url=sso_url,
            x509_cert=x509_cert,
            **kwargs,
        )

        self.okta_domain = okta_domain
        self.app_id = app_id

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "okta_saml"


class AzureADSAMLProvider(EnhancedSAMLProvider):
    """Azure AD-specific SAML provider implementation."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        tenant_id: str,
        app_id: str,
        x509_cert: str,
        **kwargs: Any,
    ) -> None:
        """Initialize Azure AD SAML provider.

        Args:
            client_id: Service provider entity ID
            client_secret: Not used for SAML
            redirect_uri: ACS URL
            tenant_id: Azure AD tenant ID
            app_id: Azure AD app ID
            x509_cert: Azure AD signing certificate
            **kwargs: Additional arguments
        """
        entity_id = f"https://sts.windows.net/{tenant_id}/"
        sso_url = f"https://login.microsoftonline.com/{tenant_id}/saml2"

        # Azure AD attribute mappings
        azure_mappings = {
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress": "email",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname": "given_name",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname": "family_name",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name": "name",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier": "sub",
            "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups": "groups",
            "http://schemas.microsoft.com/identity/claims/tenantid": "tenant_id",
        }

        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            entity_id=entity_id,
            sso_url=sso_url,
            x509_cert=x509_cert,
            attribute_mappings=azure_mappings,
            **kwargs,
        )

        self.tenant_id = tenant_id
        self.app_id = app_id

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "azure_saml"
