"""PDF blob storage. Web and worker share objects through this interface, never through a filesystem path."""
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator, Protocol

from app.config import Settings


class Storage(Protocol):
    def save(self, key: str, source: BinaryIO) -> None: ...

    def delete(self, key: str) -> None: ...

    @contextmanager
    def local_copy(self, key: str) -> Iterator[Path]: ...


def _safe_key(key: str) -> str:
    parts = key.split("/")
    if not key or key.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"Invalid storage key: {key!r}")
    return key


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, key: str) -> Path:
        return self.root / _safe_key(key)

    def save(self, key: str, source: BinaryIO) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        source.seek(0)
        with path.open("wb") as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    @contextmanager
    def local_copy(self, key: str) -> Iterator[Path]:
        path = self._path(key)
        if not path.exists():
            raise FileNotFoundError(key)
        yield path


class S3Storage:
    def __init__(self, bucket: str, client):
        self.bucket = bucket
        self.client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> "S3Storage":
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            config=Config(retries={"max_attempts": 3, "mode": "standard"}, connect_timeout=10, read_timeout=60),
        )
        return cls(settings.s3_bucket, client)

    def save(self, key: str, source: BinaryIO) -> None:
        source.seek(0)
        self.client.put_object(Bucket=self.bucket, Key=_safe_key(key), Body=source.read(), ContentType="application/pdf")

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=_safe_key(key))

    @contextmanager
    def local_copy(self, key: str) -> Iterator[Path]:
        with tempfile.TemporaryDirectory(prefix="paperchat-") as directory:
            path = Path(directory) / "document.pdf"
            response = self.client.get_object(Bucket=self.bucket, Key=_safe_key(key))
            with path.open("wb") as output:
                shutil.copyfileobj(response["Body"], output, length=1024 * 1024)
            yield path


def create_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "s3":
        return S3Storage.from_settings(settings)
    return LocalStorage(settings.upload_dir)
