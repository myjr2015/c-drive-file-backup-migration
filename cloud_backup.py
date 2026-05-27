from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from backup_core import BackupItem, VOLATILE_DIR_NAMES, VOLATILE_FILE_PATTERNS, load_user_settings
import fnmatch


CLOUD_ENVELOPE_VERSION = 1
DEFAULT_REMOTE_ROOT = "ai-session-backup"


class CloudStorage(Protocol):
    def exists(self, key: str) -> bool:
        ...

    def put_bytes(self, key: str, data: bytes) -> None:
        ...

    def get_bytes(self, key: str) -> bytes:
        ...

    def list_keys(self, prefix: str = "") -> list[str]:
        ...


@dataclass(frozen=True)
class CloudBackupConfig:
    account_id: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    remote_root: str = DEFAULT_REMOTE_ROOT
    endpoint_url: str = ""

    def normalized_remote_root(self) -> str:
        return normalize_remote_root(self.remote_root)

    def endpoint(self) -> str:
        if self.endpoint_url.strip():
            return self.endpoint_url.strip().rstrip("/")
        return f"https://{self.account_id}.r2.cloudflarestorage.com"

    def validate(self) -> None:
        missing = []
        if not self.account_id.strip():
            missing.append("Account ID")
        if not self.bucket.strip():
            missing.append("Bucket")
        if not self.access_key_id.strip():
            missing.append("Access Key ID")
        if not self.secret_access_key.strip():
            missing.append("Secret Access Key")
        if missing:
            raise ValueError(f"云端配置缺少：{', '.join(missing)}")


@dataclass(frozen=True)
class CloudBackupResult:
    snapshot_id: str
    manifest_key: str
    uploaded_objects: int
    skipped_objects: int
    total_files: int
    skipped_items: list[str]


def normalize_remote_root(value: str) -> str:
    cleaned = str(value or DEFAULT_REMOTE_ROOT).replace("\\", "/").strip("/")
    return cleaned or DEFAULT_REMOTE_ROOT


def object_key_for_hash(sha256: str, remote_root: str = DEFAULT_REMOTE_ROOT) -> str:
    root = normalize_remote_root(remote_root)
    return f"{root}/objects/sha256/{sha256[:2]}/{sha256[2:4]}/{sha256}.blob.enc"


def object_key_for_hash_and_password(sha256: str, password: str, remote_root: str = DEFAULT_REMOTE_ROOT) -> str:
    root = normalize_remote_root(remote_root)
    password_scope = hashlib.sha256(password.encode("utf-8")).hexdigest()[:16]
    return f"{root}/objects/aesgcm/{password_scope}/sha256/{sha256[:2]}/{sha256[2:4]}/{sha256}.blob.enc"


def snapshot_manifest_key(snapshot_id: str, remote_root: str = DEFAULT_REMOTE_ROOT) -> str:
    return f"{normalize_remote_root(remote_root)}/snapshots/{snapshot_id}/manifest.json.enc"


class CloudEncryptor:
    @staticmethod
    def encrypt_bytes(data: bytes, password: str) -> bytes:
        if not password:
            raise ValueError("请输入云端加密密码。")
        salt = os.urandom(16)
        nonce = os.urandom(12)
        key = _derive_key(password, salt)
        ciphertext = AESGCM(key).encrypt(nonce, data, None)
        envelope = {
            "version": CLOUD_ENVELOPE_VERSION,
            "algorithm": "AES-256-GCM",
            "kdf": "PBKDF2-HMAC-SHA256",
            "iterations": 390000,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }
        return json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def decrypt_bytes(encrypted: bytes, password: str) -> bytes:
        try:
            envelope = json.loads(encrypted.decode("utf-8"))
            salt = base64.b64decode(envelope["salt"])
            nonce = base64.b64decode(envelope["nonce"])
            ciphertext = base64.b64decode(envelope["ciphertext"])
        except Exception as exc:
            raise ValueError("云端加密数据格式无效。") from exc
        try:
            return AESGCM(_derive_key(password, salt)).decrypt(nonce, ciphertext, None)
        except InvalidTag as exc:
            raise ValueError("云端加密密码不正确，无法解密。") from exc

    @staticmethod
    def encrypt_json(data: dict, password: str) -> bytes:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return CloudEncryptor.encrypt_bytes(payload, password)

    @staticmethod
    def decrypt_json(encrypted: bytes, password: str) -> dict:
        payload = CloudEncryptor.decrypt_bytes(encrypted, password)
        data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("云端 manifest 格式无效。")
        return data


def _derive_key(password: str, salt: bytes) -> bytes:
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390000,
    ).derive(password.encode("utf-8"))


class CloudBackupService:
    def __init__(self, storage: CloudStorage) -> None:
        self.storage = storage

    def create_cloud_snapshot(
        self,
        items: Iterable[BackupItem],
        config: CloudBackupConfig,
        password: str,
        snapshot_id: str | None = None,
        device_id: str | None = None,
    ) -> CloudBackupResult:
        config.validate()
        if not password:
            raise ValueError("请输入云端加密密码。")
        snapshot = snapshot_id or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        device = device_id or os.environ.get("COMPUTERNAME") or "windows-device"
        uploaded_objects = 0
        skipped_objects = 0
        skipped_items: list[str] = []
        manifest_items: list[dict] = []

        for item in items:
            source = Path(item.source)
            if not source.exists():
                skipped_items.append(item.name)
                continue
            file_entries = []
            for file_path in self._iter_backup_files(source):
                digest = self._sha256_file(file_path)
                key = object_key_for_hash_and_password(digest, password, config.remote_root)
                size = file_path.stat().st_size
                if self.storage.exists(key):
                    skipped_objects += 1
                else:
                    encrypted_blob = CloudEncryptor.encrypt_bytes(file_path.read_bytes(), password)
                    self.storage.put_bytes(key, encrypted_blob)
                    uploaded_objects += 1
                relative_path = "." if source.is_file() else file_path.relative_to(source).as_posix()
                file_entries.append(
                    {
                        "relative_path": relative_path,
                        "sha256": digest,
                        "size": size,
                        "mtime": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(timespec="seconds"),
                        "object_key": key,
                    }
                )
            manifest_items.append(
                {
                    "name": item.name,
                    "source": str(source),
                    "restore_target": str(item.restore_target) if item.restore_target else "",
                    "sensitive": item.sensitive,
                    "files": file_entries,
                }
            )

        manifest = {
            "kind": "ai-session-backup-cloud-manifest",
            "version": CLOUD_ENVELOPE_VERSION,
            "snapshot_id": snapshot,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "device_id": device,
            "encrypted": True,
            "remote_root": config.normalized_remote_root(),
            "items": manifest_items,
        }
        manifest_key = snapshot_manifest_key(snapshot, config.remote_root)
        self.storage.put_bytes(manifest_key, CloudEncryptor.encrypt_json(manifest, password))
        return CloudBackupResult(
            snapshot_id=snapshot,
            manifest_key=manifest_key,
            uploaded_objects=uploaded_objects,
            skipped_objects=skipped_objects,
            total_files=sum(len(item["files"]) for item in manifest_items),
            skipped_items=skipped_items,
        )

    def read_manifest(self, encrypted_manifest: bytes, password: str) -> dict:
        return CloudEncryptor.decrypt_json(encrypted_manifest, password)

    def _iter_backup_files(self, source: Path) -> list[Path]:
        source = Path(source)
        if source.is_file():
            return [] if _is_volatile_path(source) else [source]
        files = []
        for path in sorted(source.rglob("*")):
            if not path.is_file() or _is_volatile_path(path):
                continue
            files.append(path)
        return files

    def _sha256_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


class R2Storage:
    def __init__(self, config: CloudBackupConfig) -> None:
        config.validate()
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("缺少 boto3/botocore，无法连接 Cloudflare R2。请先安装 requirements.txt。") from exc
        self.bucket = config.bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=config.endpoint(),
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = response.get("Error", {}).get("Code", "")
            if str(code) in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def put_bytes(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def list_keys(self, prefix: str = "") -> list[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(item["Key"] for item in page.get("Contents", []))
        return sorted(keys)


def cloud_config_from_mapping(data: dict | None) -> CloudBackupConfig:
    raw = data or {}
    return CloudBackupConfig(
        account_id=str(raw.get("account_id", "")).strip(),
        bucket=str(raw.get("bucket", "")).strip(),
        access_key_id=str(raw.get("access_key_id", "")).strip(),
        secret_access_key=str(raw.get("secret_access_key", "")).strip(),
        remote_root=str(raw.get("remote_root", DEFAULT_REMOTE_ROOT)).strip() or DEFAULT_REMOTE_ROOT,
        endpoint_url=str(raw.get("endpoint_url", "")).strip(),
    )


def cloud_config_from_environment(bucket: str = "", remote_root: str = DEFAULT_REMOTE_ROOT) -> CloudBackupConfig:
    endpoint = os.environ.get("R2_ENDPOINT") or os.environ.get("ASSET_S3_ENDPOINT") or ""
    return CloudBackupConfig(
        account_id=(os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("ASSET_S3_ACCOUNT_ID") or "").strip(),
        bucket=bucket.strip(),
        access_key_id=(os.environ.get("R2_ACCESS_KEY_ID") or os.environ.get("ASSET_S3_ACCESS_KEY_ID") or "").strip(),
        secret_access_key=(os.environ.get("R2_SECRET_ACCESS_KEY") or os.environ.get("ASSET_S3_SECRET_ACCESS_KEY") or "").strip(),
        remote_root=remote_root.strip() or DEFAULT_REMOTE_ROOT,
        endpoint_url=endpoint.strip(),
    )


def load_cloud_config_from_settings(settings: dict) -> CloudBackupConfig:
    raw = settings.get("cloud_backup", {}) if isinstance(settings, dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    return cloud_config_from_mapping(raw)


def write_cloud_config_to_settings(settings_path: Path, config: CloudBackupConfig) -> None:
    settings_path = Path(settings_path)
    current = {}
    if settings_path.exists():
        try:
            current = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}
    if not isinstance(current, dict):
        current = {}
    current["cloud_backup"] = {
        "account_id": config.account_id,
        "bucket": config.bucket,
        "access_key_id": config.access_key_id,
        "secret_access_key": config.secret_access_key,
        "remote_root": config.remote_root,
        "endpoint_url": config.endpoint_url,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")


def load_cloud_config(settings_path: Path) -> CloudBackupConfig:
    return load_cloud_config_from_settings(load_user_settings(settings_path))


def _is_volatile_path(path: Path) -> bool:
    if any(part in VOLATILE_DIR_NAMES for part in path.parts):
        return True
    return any(fnmatch.fnmatch(path.name, pattern) for pattern in VOLATILE_FILE_PATTERNS)
