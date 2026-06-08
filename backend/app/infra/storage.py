"""Object storage abstraction (S3-compatible).

Documents and generated report PDFs live in object storage, **outside any public
path**, and are served only via short-lived pre-signed URLs after authorization
(security-review §5). The application talks to this interface, not to a specific
vendor SDK, so MinIO (local) and S3 (prod) are interchangeable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def presigned_url(self, key: str, expires_seconds: int = 900) -> str: ...
    def ping(self) -> bool:
        """Best-effort reachability check for /readyz."""
        ...


@dataclass
class InMemoryStorage:
    """Dev/test implementation. Keys are opaque; nothing is web-served."""

    objects: dict[str, bytes] = field(default_factory=dict)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    def get(self, key: str) -> bytes:
        return self.objects[key]

    def presigned_url(self, key: str, expires_seconds: int = 900) -> str:
        # A stand-in; the real impl returns a signed, time-boxed S3/MinIO URL.
        return f"memory://{key}?expires={expires_seconds}"

    def ping(self) -> bool:
        return True


class S3Storage:
    """S3/MinIO implementation (boto3 imported lazily so dev/tests need no AWS deps).

    Bucket is private; access is only ever via :meth:`presigned_url`.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
    ) -> None:
        self._bucket = bucket
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region
        self._client = None

    def _c(self):  # pragma: no cover - requires boto3 + a live endpoint
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                region_name=self._region,
            )
        return self._client

    def put(self, key: str, data: bytes, content_type: str) -> None:  # pragma: no cover
        self._c().put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:  # pragma: no cover
        return self._c().get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def presigned_url(self, key: str, expires_seconds: int = 900) -> str:  # pragma: no cover
        return self._c().generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=expires_seconds
        )

    def ping(self) -> bool:  # pragma: no cover - requires a live endpoint
        try:
            self._c().head_bucket(Bucket=self._bucket)
            return True
        except Exception:
            return False
