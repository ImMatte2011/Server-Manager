from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from server_manager.models import Availability, ConfigStatus, ServiceType
from server_manager.registry import load_registry


class RegistryTests(unittest.TestCase):
    def test_missing_compose_file_makes_one_service_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            config = tmp_path / "services.toml"
            missing = tmp_path / "missing" / "docker-compose.yml"
            config.write_text(
                f"""
[services.bad_compose]
name = "Bad Compose"
type = "docker_compose"
enabled = true
compose_file = "{missing.as_posix()}"

[services.disabled_compose]
name = "Disabled Compose"
type = "docker_compose"
enabled = false
compose_file = "{missing.as_posix()}"

[services.systemd_ok]
name = "systemd ok"
type = "systemd"
unit = "example.service"
""",
                encoding="utf-8",
            )

            records = load_registry(config)

            self.assertEqual(records["bad_compose"].config_status, ConfigStatus.VALID)
            self.assertEqual(records["bad_compose"].availability, Availability.UNAVAILABLE)
            self.assertTrue(records["bad_compose"].capabilities.status)
            self.assertTrue(records["bad_compose"].capabilities.start)

            self.assertEqual(records["disabled_compose"].config_status, ConfigStatus.VALID)
            self.assertEqual(records["disabled_compose"].availability, Availability.DISABLED)

            self.assertEqual(records["systemd_ok"].type, ServiceType.SYSTEMD)
            self.assertEqual(records["systemd_ok"].config_status, ConfigStatus.VALID)


    def test_invalid_systemd_unit_is_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            config = tmp_path / "services.toml"
            config.write_text(
                """
[services.bad_unit]
name = "Bad Unit"
type = "systemd"
unit = "../../evil.service"

[services.good_unit]
name = "Good Unit"
type = "systemd"
unit = "good.service"
""",
                encoding="utf-8",
            )

            records = load_registry(config)

            self.assertEqual(records["bad_unit"].config_status, ConfigStatus.INVALID)
            self.assertEqual(records["good_unit"].config_status, ConfigStatus.VALID)

    def test_unsupported_schema_version_invalidates_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            config = tmp_path / "services.toml"
            config.write_text(
                """
schema_version = 999

[services.good_unit]
name = "Good Unit"
type = "systemd"
unit = "good.service"
""",
                encoding="utf-8",
            )

            records = load_registry(config)

            self.assertEqual(records["__registry__"].config_status, ConfigStatus.INVALID)

    def test_invalid_enabled_type_is_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            config = tmp_path / "services.toml"
            config.write_text(
                """
[services.bad]
name = "Bad"
type = "systemd"
enabled = "yes"
unit = "bad.service"

[services.good]
name = "Good"
type = "systemd"
unit = "good.service"
""",
                encoding="utf-8",
            )

            records = load_registry(config)

            self.assertEqual(records["bad"].config_status, ConfigStatus.INVALID)
            self.assertEqual(records["good"].config_status, ConfigStatus.VALID)


if __name__ == "__main__":
    unittest.main()
