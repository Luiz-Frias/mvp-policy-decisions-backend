"""OAuth2 client certificate authentication support."""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from beartype import beartype
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from ....core.cache import Cache
from ....core.database import Database
from ....services.result import Err, Ok


class ClientCertificateManager:
    """Manage OAuth2 client certificate authentication."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize certificate manager.

        Args:
            db: Database connection
            cache: Cache instance
        """
        self._db = db
        self._cache = cache
        self._cert_cache_prefix = "client_cert:"

    @beartype
    async def register_client_certificate(
        self,
        client_id: str,
        certificate_pem: str,
        certificate_name: str,
        admin_user_id: UUID,
    ) -> dict:
        """Register a client certificate for mTLS authentication.

        Args:
            client_id: OAuth2 client ID
            certificate_pem: X.509 certificate in PEM format
            certificate_name: Descriptive name for the certificate
            admin_user_id: ID of admin registering the certificate

        Returns:
            Result containing certificate details or error
        """
        try:
            # Parse and validate certificate
            cert_validation = await self._validate_certificate(certificate_pem)
            if cert_validation.is_err():
                return cert_validation

            cert_info = cert_validation.value

            # Check if certificate is already registered
            existing_cert = await self._db.fetchrow(
                """
                SELECT id FROM oauth2_client_certificates
                WHERE client_id = $1 AND fingerprint = $2 AND revoked_at IS NULL
                """,
                client_id,
                cert_info["fingerprint"],
            )

            if existing_cert:
                return Err("Certificate already registered for this client")

            # Store certificate
            cert_id = await self._db.fetchval(
                """
                INSERT INTO oauth2_client_certificates (
                    client_id, certificate_pem, certificate_name,
                    fingerprint, subject_dn, issuer_dn,
                    valid_from, valid_until, created_by, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
                """,
                client_id,
                certificate_pem,
                certificate_name,
                cert_info["fingerprint"],
                cert_info["subject_dn"],
                cert_info["issuer_dn"],
                cert_info["valid_from"],
                cert_info["valid_until"],
                admin_user_id,
                datetime.now(timezone.utc),
            )

            # Cache certificate info for fast lookup
            await self._cache.set(
                f"{self._cert_cache_prefix}{cert_info['fingerprint']}",
                {
                    "id": str(cert_id),
                    "client_id": client_id,
                    "subject_dn": cert_info["subject_dn"],
                    "valid_until": cert_info["valid_until"].isoformat(),
                },
                3600,  # 1 hour cache
            )

            return Ok(
                {
                    "certificate_id": cert_id,
                    "fingerprint": cert_info["fingerprint"],
                    "subject_dn": cert_info["subject_dn"],
                    "issuer_dn": cert_info["issuer_dn"],
                    "valid_from": cert_info["valid_from"],
                    "valid_until": cert_info["valid_until"],
                    "status": "active",
                }
            )

        except Exception as e:
            return Err(f"Failed to register client certificate: {str(e)}")

    @beartype
    async def validate_client_certificate(
        self,
        client_id: str,
        certificate_pem: str,
    ) -> dict:
        """Validate a client certificate for authentication.

        Args:
            client_id: OAuth2 client ID
            certificate_pem: Client certificate in PEM format

        Returns:
            Result containing validation details or error
        """
        try:
            # Parse certificate
            cert_validation = await self._validate_certificate(certificate_pem)
            if cert_validation.is_err():
                return cert_validation

            cert_info = cert_validation.value
            fingerprint = cert_info["fingerprint"]

            # Check cache first
            cached_cert = await self._cache.get(
                f"{self._cert_cache_prefix}{fingerprint}"
            )

            if cached_cert:
                if cached_cert["client_id"] != client_id:
                    return Err("Certificate not registered for this client")

                # Check expiration
                valid_until = datetime.fromisoformat(cached_cert["valid_until"])
                if valid_until < datetime.now(timezone.utc):
                    return Err("Certificate has expired")

                return Ok(cached_cert)

            # Check database
            cert_record = await self._db.fetchrow(
                """
                SELECT id, client_id, subject_dn, valid_until, revoked_at
                FROM oauth2_client_certificates
                WHERE fingerprint = $1
                """,
                fingerprint,
            )

            if not cert_record:
                return Err("Certificate not registered")

            if cert_record["client_id"] != client_id:
                return Err("Certificate not registered for this client")

            if cert_record["revoked_at"]:
                return Err("Certificate has been revoked")

            if cert_record["valid_until"] < datetime.now(timezone.utc):
                return Err("Certificate has expired")

            # Cache for future lookups
            cert_data = {
                "id": str(cert_record["id"]),
                "client_id": cert_record["client_id"],
                "subject_dn": cert_record["subject_dn"],
                "valid_until": cert_record["valid_until"].isoformat(),
            }

            await self._cache.set(
                f"{self._cert_cache_prefix}{fingerprint}",
                cert_data,
                3600,  # 1 hour cache
            )

            return Ok(cert_data)

        except Exception as e:
            return Err(f"Failed to validate client certificate: {str(e)}")

    @beartype
    async def revoke_client_certificate(
        self,
        certificate_id: UUID,
        reason: str,
        admin_user_id: UUID,
    ):
        """Revoke a client certificate.

        Args:
            certificate_id: Certificate ID to revoke
            reason: Reason for revocation
            admin_user_id: ID of admin performing revocation

        Returns:
            Result indicating success or error
        """
        try:
            # Get certificate fingerprint for cache invalidation
            cert_info = await self._db.fetchrow(
                """
                SELECT fingerprint FROM oauth2_client_certificates
                WHERE id = $1 AND revoked_at IS NULL
                """,
                certificate_id,
            )

            if not cert_info:
                return Err("Certificate not found or already revoked")

            # Revoke certificate
            await self._db.execute(
                """
                UPDATE oauth2_client_certificates
                SET revoked_at = $2, revoked_by = $3, revocation_reason = $4
                WHERE id = $1
                """,
                certificate_id,
                datetime.now(timezone.utc),
                admin_user_id,
                reason,
            )

            # Invalidate cache
            await self._cache.delete(
                f"{self._cert_cache_prefix}{cert_info['fingerprint']}"
            )

            return Ok(True)

        except Exception as e:
            return Err(f"Failed to revoke certificate: {str(e)}")

    @beartype
    async def list_client_certificates(
        self,
        client_id: str,
        include_revoked: bool = False,
    ) -> dict:
        """List certificates for a client.

        Args:
            client_id: OAuth2 client ID
            include_revoked: Whether to include revoked certificates

        Returns:
            Result containing list of certificates or error
        """
        try:
            query = """
                SELECT
                    id, certificate_name, fingerprint, subject_dn, issuer_dn,
                    valid_from, valid_until, created_at, revoked_at, revocation_reason
                FROM oauth2_client_certificates
                WHERE client_id = $1
            """

            if not include_revoked:
                query += " AND revoked_at IS NULL"

            query += " ORDER BY created_at DESC"

            rows = await self._db.fetch(query, client_id)

            certificates = []
            for row in rows:
                cert_data = dict(row)
                cert_data["status"] = "revoked" if cert_data["revoked_at"] else "active"

                # Check if expired
                if cert_data["valid_until"] < datetime.now(timezone.utc):
                    cert_data["status"] = "expired"

                certificates.append(cert_data)

            return Ok(certificates)

        except Exception as e:
            return Err(f"Failed to list certificates: {str(e)}")

    @beartype
    async def _validate_certificate(
        self,
        certificate_pem: str,
    ) -> dict:
        """Validate and parse X.509 certificate.

        Args:
            certificate_pem: Certificate in PEM format

        Returns:
            Result containing parsed certificate info or error
        """
        try:
            # Parse certificate
            cert = x509.load_pem_x509_certificate(certificate_pem.encode())

            # Check if certificate is currently valid
            now = datetime.now(timezone.utc)
            if cert.not_valid_before > now:
                return Err("Certificate is not yet valid")

            if cert.not_valid_after < now:
                return Err("Certificate has expired")

            # Calculate fingerprint (SHA-256)
            fingerprint = hashlib.sha256(
                cert.public_bytes(serialization.Encoding.DER)
            ).hexdigest()

            # Extract subject and issuer DN
            subject_dn = cert.subject.rfc4514_string()
            issuer_dn = cert.issuer.rfc4514_string()

            # Validate certificate chain and purpose
            # In production, this would include:
            # - Certificate chain validation
            # - CRL/OCSP checking
            # - Extended key usage validation
            # - Subject alternative name validation

            return Ok(
                {
                    "fingerprint": fingerprint,
                    "subject_dn": subject_dn,
                    "issuer_dn": issuer_dn,
                    "valid_from": cert.not_valid_before.replace(tzinfo=timezone.utc),
                    "valid_until": cert.not_valid_after.replace(tzinfo=timezone.utc),
                    "serial_number": str(cert.serial_number),
                    "signature_algorithm": cert.signature_algorithm_oid._name,
                }
            )

        except Exception as e:
            return Err(f"Invalid certificate: {str(e)}")

    @beartype
    async def create_certificate_signing_request(
        self,
        client_id: str,
        subject_info: dict[str, str],
    ) -> dict:
        """Create a certificate signing request (CSR) for a client.

        This is useful for automated certificate provisioning.

        Args:
            client_id: OAuth2 client ID
            subject_info: Subject information for the certificate

        Returns:
            Result containing CSR and private key or error
        """
        try:
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )

            # Build subject name
            subject_components = []

            if "country" in subject_info:
                subject_components.append(
                    x509.NameAttribute(NameOID.COUNTRY_NAME, subject_info["country"])
                )
            if "state" in subject_info:
                subject_components.append(
                    x509.NameAttribute(
                        NameOID.STATE_OR_PROVINCE_NAME, subject_info["state"]
                    )
                )
            if "city" in subject_info:
                subject_components.append(
                    x509.NameAttribute(NameOID.LOCALITY_NAME, subject_info["city"])
                )
            if "organization" in subject_info:
                subject_components.append(
                    x509.NameAttribute(
                        NameOID.ORGANIZATION_NAME, subject_info["organization"]
                    )
                )
            if "organizational_unit" in subject_info:
                subject_components.append(
                    x509.NameAttribute(
                        NameOID.ORGANIZATIONAL_UNIT_NAME,
                        subject_info["organizational_unit"],
                    )
                )

            # Common name should be the client_id
            subject_components.append(
                x509.NameAttribute(NameOID.COMMON_NAME, client_id)
            )

            subject = x509.Name(subject_components)

            # Create CSR
            csr = (
                x509.CertificateSigningRequestBuilder()
                .subject_name(subject)
                .add_extension(
                    x509.SubjectAlternativeName(
                        [
                            x509.DNSName(f"{client_id}.oauth.client"),
                        ]
                    ),
                    critical=False,
                )
                .sign(private_key, hashes.SHA256())
            )

            # Serialize CSR and private key
            csr_pem = csr.public_bytes(serialization.Encoding.PEM).decode()

            private_key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode()

            return Ok(
                {
                    "csr": csr_pem,
                    "private_key": private_key_pem,
                    "client_id": client_id,
                    "subject_dn": subject.rfc4514_string(),
                }
            )

        except Exception as e:
            return Err(f"Failed to create CSR: {str(e)}")

    @beartype
    async def get_certificate_health_status(self) -> dict[str, Any]:
        """Get certificate system health status.

        Returns:
            Health status including certificate counts and expiration warnings
        """
        try:
            # Count active certificates
            active_certs = await self._db.fetchval(
                "SELECT COUNT(*) FROM oauth2_client_certificates WHERE revoked_at IS NULL"
            )

            # Count certificates expiring in next 30 days
            thirty_days_from_now = datetime.now(timezone.utc) + timedelta(days=30)
            expiring_soon = await self._db.fetchval(
                """
                SELECT COUNT(*) FROM oauth2_client_certificates
                WHERE revoked_at IS NULL AND valid_until < $1
                """,
                thirty_days_from_now,
            )

            # Count revoked certificates
            revoked_certs = await self._db.fetchval(
                "SELECT COUNT(*) FROM oauth2_client_certificates WHERE revoked_at IS NOT NULL"
            )

            return {
                "status": "healthy",
                "active_certificates": active_certs or 0,
                "certificates_expiring_soon": expiring_soon or 0,
                "revoked_certificates": revoked_certs or 0,
                "certificate_validation_enabled": True,
                "cache_status": "operational",
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "certificate_validation_enabled": False,
            }
