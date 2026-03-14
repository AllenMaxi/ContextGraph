from __future__ import annotations

import unittest

from contextgraph.bootstrap import create_repository, create_service
from contextgraph.config import Settings
from contextgraph.in_memory import InMemoryRepository


class ContextGraphBootstrapTest(unittest.TestCase):
    def test_create_repository_uses_memory_backend(self) -> None:
        repository = create_repository(Settings(repository_backend="memory"))

        self.assertIsInstance(repository, InMemoryRepository)
        repository.close()

    def test_create_service_reports_configured_backend(self) -> None:
        service = create_service(Settings(repository_backend="memory", trust_threshold=0.72))

        health = service.health()

        self.assertEqual(health["repository_backend"], "memory")
        self.assertEqual(health["federation_enabled"], False)
        service.close()


if __name__ == "__main__":
    unittest.main()
