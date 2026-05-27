import json
import tempfile
import unittest
from pathlib import Path

from backup_core import BackupItem


class MemoryCloudStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_order: list[str] = []

    def exists(self, key: str) -> bool:
        return key in self.objects

    def put_bytes(self, key: str, data: bytes) -> None:
        self.objects[key] = data
        self.put_order.append(key)

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def list_keys(self, prefix: str = "") -> list[str]:
        return sorted(key for key in self.objects if key.startswith(prefix))


class CloudBackupTests(unittest.TestCase):
    def test_object_key_uses_sha256_prefix_layout(self):
        from cloud_backup import object_key_for_hash

        digest = "abcdef1234567890"

        self.assertEqual(object_key_for_hash(digest, "root"), "root/objects/sha256/ab/cd/abcdef1234567890.blob.enc")

    def test_encryptor_round_trip_and_rejects_wrong_password(self):
        from cloud_backup import CloudEncryptor

        encrypted = CloudEncryptor.encrypt_json({"name": ".codex", "value": "secret"}, "correct horse")

        self.assertNotIn(b"secret", encrypted)
        self.assertEqual(CloudEncryptor.decrypt_json(encrypted, "correct horse")["value"], "secret")
        with self.assertRaises(ValueError):
            CloudEncryptor.decrypt_json(encrypted, "wrong password")

    def test_cloud_backup_uploads_missing_objects_once_and_manifest_last(self):
        from cloud_backup import CloudBackupConfig, CloudBackupService

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "home" / ".codex"
            source.mkdir(parents=True)
            (source / "config.toml").write_text("config", encoding="utf-8")
            (source / "tmp").mkdir()
            (source / "tmp" / "skip.txt").write_text("skip", encoding="utf-8")
            (source / "state.sqlite-shm").write_text("volatile", encoding="utf-8")
            storage = MemoryCloudStorage()
            config = CloudBackupConfig(
                account_id="account",
                bucket="bucket",
                access_key_id="access",
                secret_access_key="secret",
                remote_root="remote",
            )
            service = CloudBackupService(storage)

            first = service.create_cloud_snapshot(
                [BackupItem(".codex", source)],
                config=config,
                password="password",
                snapshot_id="snap-1",
                device_id="device-1",
            )
            second = service.create_cloud_snapshot(
                [BackupItem(".codex", source)],
                config=config,
                password="password",
                snapshot_id="snap-2",
                device_id="device-1",
            )

            object_keys = [key for key in storage.put_order if "/objects/" in key]
            manifest_keys = [key for key in storage.put_order if key.endswith("/manifest.json.enc")]
            self.assertEqual(first.uploaded_objects, 1)
            self.assertEqual(second.uploaded_objects, 0)
            self.assertEqual(first.skipped_objects, 0)
            self.assertEqual(second.skipped_objects, 1)
            self.assertEqual(len(object_keys), 1)
            self.assertEqual(manifest_keys, ["remote/snapshots/snap-1/manifest.json.enc", "remote/snapshots/snap-2/manifest.json.enc"])
            self.assertTrue(storage.put_order.index(object_keys[0]) < storage.put_order.index("remote/snapshots/snap-1/manifest.json.enc"))

            manifest = service.read_manifest(storage.get_bytes("remote/snapshots/snap-1/manifest.json.enc"), "password")
            file_paths = [file["relative_path"] for item in manifest["items"] for file in item["files"]]
            self.assertEqual(file_paths, ["config.toml"])
            self.assertTrue(manifest["encrypted"])

    def test_cloud_backup_does_not_reuse_objects_encrypted_with_different_password(self):
        from cloud_backup import CloudBackupConfig, CloudBackupService

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "home" / ".happy"
            source.mkdir(parents=True)
            (source / "sessions.json").write_text("same content", encoding="utf-8")
            storage = MemoryCloudStorage()
            config = CloudBackupConfig(
                account_id="account",
                bucket="bucket",
                access_key_id="access",
                secret_access_key="secret",
                remote_root="remote",
            )
            service = CloudBackupService(storage)

            first = service.create_cloud_snapshot(
                [BackupItem(".happy", source)],
                config=config,
                password="first-password",
                snapshot_id="snap-1",
            )
            second = service.create_cloud_snapshot(
                [BackupItem(".happy", source)],
                config=config,
                password="second-password",
                snapshot_id="snap-2",
            )

            object_keys = [key for key in storage.put_order if "/objects/" in key]
            self.assertEqual(first.uploaded_objects, 1)
            self.assertEqual(second.uploaded_objects, 1)
            self.assertEqual(len(object_keys), 2)
            self.assertNotEqual(object_keys[0], object_keys[1])

    def test_cloud_settings_round_trip_preserves_existing_backup_config(self):
        from backup_core import load_user_settings, write_user_settings
        from cloud_backup import CloudBackupConfig, load_cloud_config_from_settings, write_cloud_config_to_settings

        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "data" / "user-settings.json"
            write_user_settings(settings_path, [".ssh"], backup_root=Path("D:/backups"), schedule_time="06:30")

            write_cloud_config_to_settings(
                settings_path,
                CloudBackupConfig(
                    account_id="account",
                    bucket="bucket",
                    access_key_id="access",
                    secret_access_key="secret",
                    remote_root="remote",
                ),
            )
            settings = load_user_settings(settings_path)
            cloud_config = load_cloud_config_from_settings(settings)

            self.assertEqual(settings["selected_items"], [".ssh"])
            self.assertEqual(Path(settings["backup_root"]), Path("D:/backups"))
            self.assertEqual(settings["schedule_time"], "06:30")
            self.assertEqual(cloud_config.bucket, "bucket")
            self.assertEqual(cloud_config.secret_access_key, "secret")
            raw = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertIn("cloud_backup", raw)

            write_user_settings(settings_path, [".codex"])
            cloud_config_after_selection_save = load_cloud_config_from_settings(load_user_settings(settings_path))

            self.assertEqual(cloud_config_after_selection_save.bucket, "bucket")
            self.assertEqual(cloud_config_after_selection_save.secret_access_key, "secret")

    def test_cloud_config_can_be_loaded_from_global_login_environment(self):
        from unittest.mock import patch

        from cloud_backup import cloud_config_from_environment

        env = {
            "CLOUDFLARE_ACCOUNT_ID": "account",
            "R2_ACCESS_KEY_ID": "access",
            "R2_SECRET_ACCESS_KEY": "secret",
            "R2_ENDPOINT": "https://account.r2.cloudflarestorage.com",
        }
        with patch.dict("os.environ", env, clear=True):
            config = cloud_config_from_environment(bucket="ai-session-backup")

        self.assertEqual(config.account_id, "account")
        self.assertEqual(config.bucket, "ai-session-backup")
        self.assertEqual(config.access_key_id, "access")
        self.assertEqual(config.secret_access_key, "secret")
        self.assertEqual(config.endpoint_url, "https://account.r2.cloudflarestorage.com")

    def test_backup_cli_cloud_backup_uses_saved_r2_config(self):
        from unittest.mock import patch

        from backup_cli import run_cloud_backup
        from cloud_backup import CloudBackupConfig, write_cloud_config_to_settings

        class RecordingStorage(MemoryCloudStorage):
            config = None

            def __init__(self, config) -> None:
                super().__init__()
                type(self).config = config

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "home" / ".codex"
            source.mkdir(parents=True)
            (source / "config.toml").write_text("config", encoding="utf-8")
            settings_path = root / "data" / "user-settings.json"
            write_cloud_config_to_settings(
                settings_path,
                CloudBackupConfig(
                    account_id="account",
                    bucket="bucket",
                    access_key_id="access",
                    secret_access_key="secret",
                    remote_root="remote",
                ),
            )

            with patch("backup_cli.Path.home", return_value=root / "home"), patch("backup_cli.R2Storage", RecordingStorage):
                exit_code = run_cloud_backup({".codex"}, "password", settings_path=settings_path)

            self.assertEqual(exit_code, 0)
            self.assertEqual(RecordingStorage.config.bucket, "bucket")


if __name__ == "__main__":
    unittest.main()
