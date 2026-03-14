from __future__ import annotations

from .bootstrap import create_service
from .web import create_app


service = create_service()
app = create_app(service)

