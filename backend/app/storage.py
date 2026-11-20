"""Private object storage for source documents and creative assets."""
from __future__ import annotations

import io
from pathlib import Path, PurePosixPath

from .config import get_settings


class StorageError(RuntimeError):
    """Raised when a configured private storage backend cannot complete an operation."""


def _key_path(key: str) -> PurePosixPath:
    path = PurePosixPath(key)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise StorageError("Invalid private object key.")
    return path


def put_private_object(key: str, data: bytes, content_type: str) -> None:
    path = _key_path(key)
    settings = get_settings()
    if settings.storage_backend == "s3":
        if not settings.s3_bucket or not settings.s3_access_key_id or not settings.s3_secret_access_key:
            raise StorageError(
                "S3 storage is selected but bucket and credentials are not configured."
            )
        try:
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url or None,
                region_name=settings.s3_region,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
            )
            client.put_object(
                Bucket=settings.s3_bucket,
                Key=str(path),
                Body=io.BytesIO(data),
                ContentLength=len(data),
                ContentType=content_type,
            )
        except Exception as exc:
            raise StorageError("Could not save the private file to S3-compatible storage.") from exc
        return

    destination = settings.private_storage_dir.joinpath(*path.parts).resolve()
    if not destination.is_relative_to(settings.private_storage_dir):
        raise StorageError("Invalid private object path.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)


def get_private_object(key: str) -> bytes:
    path = _key_path(key)
    settings = get_settings()
    if settings.storage_backend == "s3":
        if not settings.s3_bucket or not settings.s3_access_key_id or not settings.s3_secret_access_key:
            raise StorageError("S3 storage is selected but its credentials are not configured.")
        try:
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url or None,
                region_name=settings.s3_region,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
            )
            result = client.get_object(Bucket=settings.s3_bucket, Key=str(path))
            return result["Body"].read()
        except Exception as exc:
            raise StorageError("Could not retrieve the private file from object storage.") from exc

    destination = settings.private_storage_dir.joinpath(*path.parts).resolve()
    if not destination.is_relative_to(settings.private_storage_dir):
        raise StorageError("Invalid private object path.")
    try:
        return destination.read_bytes()
    except FileNotFoundError as exc:
        raise StorageError("The stored file is missing.") from exc
    except OSError as exc:
        raise StorageError("Could not read the stored file.") from exc
