from __future__ import annotations

from pathlib import Path
import unittest

from server_manager.controller import ServiceController
from server_manager.errors import ServiceUnavailableError
from server_manager.models import ServiceType
from server_manager.providers.fake import FakeProvider
from server_manager.registry import ServiceRegistry


class ControllerTests(unittest.TestCase):
    def test_controller_blocks_unavailable_service_start(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            config = tmp_path / "services.toml"
            config.write_text(
                f"""
[services.missing]
name = "Missing"
type = "docker_compose"
enabled = true
compose_file = "{(tmp_path / "missing.yml").as_posix()}"
""",
                encoding="utf-8",
            )
            controller = ServiceController(
                ServiceRegistry(config),
                providers={ServiceType.DOCKER_COMPOSE: FakeProvider()},
            )

            with self.assertRaises(ServiceUnavailableError):
                controller.start("missing")


if __name__ == "__main__":
    unittest.main()
