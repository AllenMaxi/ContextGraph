# One-Click Agent Creation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a native agent runtime with container isolation, MCP tool bundles, creation wizard, and chat interface — fully integrated with ContextGraph's knowledge, sentinel, and discovery systems.

**Architecture:** New `contextgraph/runtime/` package (~500-800 lines total) with protocol-based LLM providers, isolation modes (Docker/process), and MCP tool loading. New API endpoints for runtime lifecycle and chat. Dashboard wizard and chat pages in existing `dashboard.py` pattern.

**Tech Stack:** Python, FastAPI, Claude Agent SDK (default provider), Docker (optional), MCP protocol, pure HTML/CSS/JS dashboard.

**Spec:** `docs/superpowers/specs/2026-03-21-one-click-agent-creation-design.md`

**Prerequisite:** Sub-project 1 (Agent Discovery Panel) must be implemented first — this plan assumes its endpoints, service methods, and dashboard pages exist.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `contextgraph/models.py` | Modify | Add `runtime_config` field to Agent dataclass |
| `contextgraph/api/schemas.py` | Modify | Add `runtime_config` to `AgentResponse`, add new request/response schemas |
| `contextgraph/runtime/__init__.py` | Create | Package init, re-exports |
| `contextgraph/runtime/providers.py` | Create | LLMProvider protocol, LLMResponse, ToolCall dataclasses, ClaudeProvider |
| `contextgraph/runtime/isolation.py` | Create | DockerIsolation, ProcessIsolation, IsolationBackend protocol |
| `contextgraph/runtime/tools.py` | Create | ToolManager, bundle loading, MCP tool routing |
| `contextgraph/runtime/bundles.json` | Create | Pre-configured tool bundle definitions |
| `contextgraph/runtime/engine.py` | Create | AgentRuntime class — core execution loop |
| `contextgraph/service.py` | Modify | Add runtime lifecycle, chat, SOUL.md generation service methods |
| `contextgraph/api/routes.py` | Modify | Add 10 new API endpoints |
| `contextgraph/api/dashboard.py` | Modify | Add creation wizard and chat pages |
| `sdk/contextgraph_sdk/client.py` | Modify | Add Transport protocol methods, HttpTransport, ContextGraph methods |
| `sdk/contextgraph_sdk/_local.py` | Modify | Add LocalTransport methods |
| `contextgraph/cli.py` | Modify | Add runtime and tools CLI commands |
| `tests/test_runtime_providers.py` | Create | Provider tests |
| `tests/test_runtime_isolation.py` | Create | Isolation tests |
| `tests/test_runtime_tools.py` | Create | Tool loading and bundle tests |
| `tests/test_runtime_engine.py` | Create | AgentRuntime lifecycle and ReAct loop tests |
| `tests/test_runtime_api.py` | Create | API endpoint tests |
| `tests/test_runtime_chat.py` | Create | Chat and conversation tests |

---

### Task 1: Data Model — Add `runtime_config` to Agent

**Files:**
- Modify: `contextgraph/models.py:122-141`
- Modify: `contextgraph/api/schemas.py:18-34`
- Test: `tests/test_runtime_engine.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runtime_engine.py
from __future__ import annotations

import unittest

from contextgraph import ContextGraphService


class RuntimeConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()

    def tearDown(self) -> None:
        self.service.close()

    def test_agent_has_runtime_config_field(self) -> None:
        agent = self.service.register_agent("test-agent", "acme", ["research"])
        self.assertEqual(agent.runtime_config, {})

    def test_runtime_config_persists(self) -> None:
        agent = self.service.register_agent("test-agent", "acme", ["research"])
        agent.runtime_config = {"provider": "claude", "model": "claude-sonnet-4-6"}
        self.service.repository.save_agent(agent)
        loaded = self.service.get_agent(agent.agent_id)
        self.assertEqual(loaded.runtime_config["provider"], "claude")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_runtime_engine.py::RuntimeConfigTest -v`
Expected: FAIL — `Agent` has no attribute `runtime_config`

- [ ] **Step 3: Add `runtime_config` field to Agent dataclass**

In `contextgraph/models.py`, add after `role: str = "agent"` (line 141):

```python
runtime_config: dict[str, Any] = field(default_factory=dict)
```

Also add the `Any` import if not already present (check `from typing import Any` at top).

- [ ] **Step 4: Add `runtime_config` to `AgentResponse` schema**

In `contextgraph/api/schemas.py`, add to `AgentResponse` class (after `default_price: float = 0.0`, line 34):

```python
runtime_config: dict[str, Any] = Field(default_factory=dict)
```

Add `Any` to typing imports if needed.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_runtime_engine.py::RuntimeConfigTest -v`
Expected: PASS

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: All existing tests still pass

- [ ] **Step 7: Commit**

```bash
git add contextgraph/models.py contextgraph/api/schemas.py tests/test_runtime_engine.py
git commit -m "feat: add runtime_config field to Agent model and response schema"
```

---

### Task 2: LLM Provider Abstraction

**Files:**
- Create: `contextgraph/runtime/__init__.py`
- Create: `contextgraph/runtime/providers.py`
- Test: `tests/test_runtime_providers.py` (create)

- [ ] **Step 1: Create runtime package init**

```python
# contextgraph/runtime/__init__.py
```

Empty file to make it a package.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_runtime_providers.py
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from contextgraph.runtime.providers import (
    ClaudeProvider,
    LLMResponse,
    ToolCall,
    get_provider,
)


class LLMResponseTest(unittest.TestCase):
    def test_response_with_text_only(self) -> None:
        resp = LLMResponse(content="Hello", tool_calls=[], usage={"input_tokens": 10, "output_tokens": 5})
        self.assertEqual(resp.content, "Hello")
        self.assertEqual(resp.tool_calls, [])

    def test_response_with_tool_calls(self) -> None:
        tc = ToolCall(id="tc1", name="search", arguments={"query": "test"})
        resp = LLMResponse(content="", tool_calls=[tc], usage={})
        self.assertEqual(len(resp.tool_calls), 1)
        self.assertEqual(resp.tool_calls[0].name, "search")


class GetProviderTest(unittest.TestCase):
    def test_get_claude_provider(self) -> None:
        provider = get_provider("claude", model="claude-sonnet-4-6", api_key="test-key")
        self.assertIsInstance(provider, ClaudeProvider)

    def test_get_unknown_provider_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_provider("unknown_provider", model="x", api_key="k")


class ClaudeProviderTest(unittest.TestCase):
    @patch("contextgraph.runtime.providers.anthropic")
    def test_complete_formats_messages(self, mock_anthropic: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Hi there")]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_client.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = provider.complete(
            messages=[{"role": "user", "content": "Hello"}],
            tools=[],
        )
        self.assertEqual(result.content, "Hi there")
        mock_client.messages.create.assert_called_once()

    def test_complete_without_api_key_raises(self) -> None:
        with self.assertRaises(ValueError):
            ClaudeProvider(api_key="", model="claude-sonnet-4-6")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_runtime_providers.py -v`
Expected: FAIL — module not found

- [ ] **Step 4: Implement providers.py**

```python
# contextgraph/runtime/providers.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore[assignment]


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class LLMResponse:
    content: str
    tool_calls: list[ToolCall]
    usage: dict[str, int]


class LLMProvider(Protocol):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], system: str = "") -> LLMResponse: ...


@dataclass
class ClaudeProvider:
    api_key: str
    model: str = "claude-sonnet-4-6"
    _client: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("ClaudeProvider requires a non-empty api_key")
        if anthropic is None:
            raise ImportError("pip install anthropic to use ClaudeProvider")
        self._client = anthropic.Anthropic(api_key=self.api_key)

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], system: str = "") -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = self._client.messages.create(**kwargs)

        content = ""
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=block.input)
                )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )


def get_provider(provider_name: str, *, model: str, api_key: str) -> LLMProvider:
    if provider_name == "claude":
        return ClaudeProvider(api_key=api_key, model=model)
    raise ValueError(f"Unknown provider: {provider_name!r}. Supported: claude")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_runtime_providers.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add contextgraph/runtime/__init__.py contextgraph/runtime/providers.py tests/test_runtime_providers.py
git commit -m "feat: add LLM provider abstraction with ClaudeProvider"
```

---

### Task 3: Container and Process Isolation

**Files:**
- Create: `contextgraph/runtime/isolation.py`
- Test: `tests/test_runtime_isolation.py` (create)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_runtime_isolation.py
from __future__ import annotations

import os
import tempfile
import unittest

from contextgraph.runtime.isolation import (
    IsolationBackend,
    ProcessIsolation,
    get_isolation,
)


class ProcessIsolationTest(unittest.TestCase):
    def test_creates_workspace_directory(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            iso = ProcessIsolation(agent_id="test-agent", base_dir=base)
            iso.start()
            self.assertTrue(os.path.isdir(iso.workspace_path))
            iso.stop()

    def test_blocks_dangerous_paths(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            iso = ProcessIsolation(agent_id="test-agent", base_dir=base)
            iso.start()
            self.assertFalse(iso.is_path_allowed(os.path.expanduser("~/.ssh/id_rsa")))
            self.assertFalse(iso.is_path_allowed(os.path.expanduser("~/.aws/credentials")))
            iso.stop()

    def test_allows_workspace_paths(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            iso = ProcessIsolation(agent_id="test-agent", base_dir=base)
            iso.start()
            workspace_file = os.path.join(iso.workspace_path, "test.py")
            self.assertTrue(iso.is_path_allowed(workspace_file))
            iso.stop()

    def test_blocks_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            iso = ProcessIsolation(agent_id="test-agent", base_dir=base)
            iso.start()
            # Symlink pointing outside workspace
            link = os.path.join(iso.workspace_path, "escape")
            os.symlink("/etc/passwd", link)
            self.assertFalse(iso.is_path_allowed(link))
            iso.stop()


class GetIsolationTest(unittest.TestCase):
    def test_get_process_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            iso = get_isolation("process", agent_id="test", base_dir=base)
            self.assertIsInstance(iso, ProcessIsolation)

    def test_get_none_isolation(self) -> None:
        iso = get_isolation("none", agent_id="test")
        self.assertIsNotNone(iso)

    def test_unknown_isolation_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_isolation("unknown", agent_id="test")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_runtime_isolation.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement isolation.py**

```python
# contextgraph/runtime/isolation.py
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class IsolationBackend(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def is_path_allowed(self, path: str) -> bool: ...
    @property
    def workspace_path(self) -> str: ...
    def execute(self, command: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]: ...


_DEFAULT_BLOCKED = ("~/.ssh", "~/.gnupg", "~/.aws", "/etc")
_DEFAULT_ALLOWED_CMDS = ("python", "python3", "node", "git", "curl")


@dataclass
class ProcessIsolation:
    agent_id: str
    base_dir: str = ""
    blocked_paths: tuple[str, ...] = _DEFAULT_BLOCKED
    allowed_commands: tuple[str, ...] = _DEFAULT_ALLOWED_CMDS
    _workspace: str = ""

    def __post_init__(self) -> None:
        if not self.base_dir:
            self.base_dir = str(Path.home() / ".contextgraph" / "agents")

    @property
    def workspace_path(self) -> str:
        return self._workspace

    def start(self) -> None:
        self._workspace = os.path.join(self.base_dir, self.agent_id)
        os.makedirs(self._workspace, exist_ok=True)

    def stop(self) -> None:
        pass  # workspace preserved for state

    def is_path_allowed(self, path: str) -> bool:
        try:
            real = os.path.realpath(path)
        except (OSError, ValueError):
            return False

        workspace_real = os.path.realpath(self._workspace)
        if not real.startswith(workspace_real + os.sep) and real != workspace_real:
            return False

        for blocked in self.blocked_paths:
            expanded = os.path.expanduser(blocked)
            if real.startswith(os.path.realpath(expanded)):
                return False

        return True

    def execute(self, command: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        if command and command[0] not in self.allowed_commands:
            raise PermissionError(f"Command {command[0]!r} not in allowed list: {self.allowed_commands}")
        return subprocess.run(
            command,
            cwd=self._workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
        )


@dataclass
class NoIsolation:
    agent_id: str

    @property
    def workspace_path(self) -> str:
        return os.getcwd()

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def is_path_allowed(self, path: str) -> bool:
        return True

    def execute(self, command: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


@dataclass
class DockerIsolation:
    agent_id: str
    image: str = "python:3.12-slim"
    cpu_limit: int = 1
    memory_mb: int = 512
    _container_id: str = ""
    _workspace: str = ""

    @property
    def workspace_path(self) -> str:
        return self._workspace

    def start(self) -> None:
        self._workspace = os.path.join(
            str(Path.home()), ".contextgraph", "agents", self.agent_id
        )
        os.makedirs(self._workspace, exist_ok=True)

        result = subprocess.run(
            [
                "docker", "run", "-d",
                "--name", f"cg-agent-{self.agent_id[:12]}",
                f"--cpus={self.cpu_limit}",
                f"--memory={self.memory_mb}m",
                "-v", f"{self._workspace}:/workspace",
                "-w", "/workspace",
                self.image,
                "sleep", "infinity",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Docker start failed: {result.stderr}")
        self._container_id = result.stdout.strip()

    def stop(self) -> None:
        if self._container_id:
            subprocess.run(
                ["docker", "rm", "-f", self._container_id],
                capture_output=True,
            )
            self._container_id = ""

    def is_path_allowed(self, path: str) -> bool:
        return True  # container handles isolation

    def execute(self, command: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["docker", "exec", self._container_id] + command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )


def docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_isolation(
    mode: str, *, agent_id: str, base_dir: str = "", **kwargs: Any
) -> IsolationBackend:
    if mode == "docker":
        return DockerIsolation(agent_id=agent_id, **kwargs)
    if mode == "process":
        return ProcessIsolation(agent_id=agent_id, base_dir=base_dir)
    if mode == "none":
        return NoIsolation(agent_id=agent_id)
    raise ValueError(f"Unknown isolation mode: {mode!r}. Supported: docker, process, none")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_runtime_isolation.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add contextgraph/runtime/isolation.py tests/test_runtime_isolation.py
git commit -m "feat: add container and process isolation backends"
```

---

### Task 4: MCP Tool System

**Files:**
- Create: `contextgraph/runtime/bundles.json`
- Create: `contextgraph/runtime/tools.py`
- Test: `tests/test_runtime_tools.py` (create)

- [ ] **Step 1: Create bundles.json**

```json
{
    "developer": {
        "description": "Tools for coding agents",
        "servers": [
            {"name": "filesystem", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]},
            {"name": "shell", "command": "npx", "args": ["-y", "@anthropic/mcp-shell"]},
            {"name": "git", "command": "npx", "args": ["-y", "@anthropic/mcp-git"]}
        ]
    },
    "research": {
        "description": "Tools for research and analysis agents",
        "servers": [
            {"name": "web-search", "command": "npx", "args": ["-y", "@anthropic/mcp-web-search"]},
            {"name": "fetch", "command": "npx", "args": ["-y", "@anthropic/mcp-fetch"]}
        ]
    },
    "data": {
        "description": "Tools for data analysis agents",
        "servers": [
            {"name": "sqlite", "command": "npx", "args": ["-y", "@anthropic/mcp-sqlite"]},
            {"name": "csv-reader", "command": "npx", "args": ["-y", "@anthropic/mcp-csv"]}
        ]
    },
    "communication": {
        "description": "Tools for assistant agents",
        "servers": [
            {"name": "slack", "command": "npx", "args": ["-y", "@anthropic/mcp-slack"]},
            {"name": "email", "command": "npx", "args": ["-y", "@anthropic/mcp-email"]}
        ]
    },
    "minimal": {
        "description": "Minimal read-only tools for restricted agents",
        "servers": [
            {"name": "filesystem", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "--read-only", "/workspace"]}
        ]
    }
}
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_runtime_tools.py
from __future__ import annotations

import json
import os
import unittest

from contextgraph.runtime.tools import ToolManager, load_bundles


class LoadBundlesTest(unittest.TestCase):
    def test_load_bundles_returns_dict(self) -> None:
        bundles = load_bundles()
        self.assertIsInstance(bundles, dict)
        self.assertIn("developer", bundles)
        self.assertIn("research", bundles)
        self.assertIn("minimal", bundles)

    def test_bundle_has_servers(self) -> None:
        bundles = load_bundles()
        dev = bundles["developer"]
        self.assertIn("servers", dev)
        self.assertGreater(len(dev["servers"]), 0)

    def test_bundle_server_has_name_and_command(self) -> None:
        bundles = load_bundles()
        server = bundles["developer"]["servers"][0]
        self.assertIn("name", server)
        self.assertIn("command", server)


class ToolManagerTest(unittest.TestCase):
    def test_get_tool_definitions_from_bundles(self) -> None:
        """ToolManager builds tool defs from bundle configs (without starting MCP servers)."""
        tm = ToolManager(bundles=["minimal"], manual_tools=[], permissions={})
        defs = tm.get_tool_definitions()
        # Without running MCP servers, tool defs come from bundle metadata
        self.assertIsInstance(defs, list)

    def test_permission_defaults_dangerous_to_confirm(self) -> None:
        tm = ToolManager(bundles=["developer"], manual_tools=[], permissions={})
        self.assertEqual(tm.get_permission("shell"), "confirm")
        self.assertEqual(tm.get_permission("filesystem"), "auto")

    def test_permission_override(self) -> None:
        tm = ToolManager(
            bundles=["developer"],
            manual_tools=[],
            permissions={"shell": "auto"},
        )
        self.assertEqual(tm.get_permission("shell"), "auto")

    def test_add_manual_tool(self) -> None:
        manual = {"name": "custom-tool", "command": "python", "args": ["server.py"]}
        tm = ToolManager(bundles=[], manual_tools=[manual], permissions={})
        self.assertIn("custom-tool", [t["name"] for t in tm.list_configured_tools()])
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_runtime_tools.py -v`
Expected: FAIL — module not found

- [ ] **Step 4: Implement tools.py**

```python
# contextgraph/runtime/tools.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_BUNDLES_PATH = Path(__file__).parent / "bundles.json"
_DANGEROUS_TOOLS = frozenset({"shell", "filesystem-write"})


def load_bundles() -> dict[str, Any]:
    return json.loads(_BUNDLES_PATH.read_text())


@dataclass
class ToolManager:
    bundles: list[str]
    manual_tools: list[dict[str, Any]]
    permissions: dict[str, str]
    _tool_configs: list[dict[str, Any]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        all_bundles = load_bundles()
        for bundle_name in self.bundles:
            if bundle_name in all_bundles:
                for server in all_bundles[bundle_name]["servers"]:
                    self._tool_configs.append(server)
        for tool in self.manual_tools:
            self._tool_configs.append(tool)

    def get_permission(self, tool_name: str) -> str:
        if tool_name in self.permissions:
            return self.permissions[tool_name]
        if tool_name in _DANGEROUS_TOOLS:
            return "confirm"
        return "auto"

    def list_configured_tools(self) -> list[dict[str, Any]]:
        return list(self._tool_configs)

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return LLM-compatible tool definitions from configured servers.

        Without live MCP connections, returns metadata-based definitions.
        """
        defs = []
        for tool in self._tool_configs:
            defs.append({
                "name": tool["name"],
                "description": f"MCP tool: {tool['name']}",
                "input_schema": {"type": "object", "properties": {}},
            })
        return defs
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_runtime_tools.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add contextgraph/runtime/bundles.json contextgraph/runtime/tools.py tests/test_runtime_tools.py
git commit -m "feat: add MCP tool manager with bundle loading and permissions"
```

---

### Task 5: Agent Runtime Engine

**Files:**
- Create: `contextgraph/runtime/engine.py`
- Test: `tests/test_runtime_engine.py` (add to existing)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_runtime_engine.py`:

```python
from unittest.mock import MagicMock, patch

from contextgraph.runtime.engine import AgentRuntime
from contextgraph.runtime.providers import LLMResponse, ToolCall


class AgentRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.agent = self.service.register_agent("runtime-test", "acme", ["research"])
        self.agent.runtime_config = {
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "isolation": "none",
            "soul_md": "You are a helpful assistant.",
            "bundles": [],
            "manual_tools": [],
            "tool_permissions": {},
            "context_window_messages": 20,
            "auto_store": False,
        }
        self.service.repository.save_agent(self.agent)

    def tearDown(self) -> None:
        self.service.close()

    @patch("contextgraph.runtime.engine.get_provider")
    def test_start_and_stop_lifecycle(self, mock_get_provider: MagicMock) -> None:
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider

        runtime = AgentRuntime(
            agent_id=self.agent.agent_id,
            service=self.service,
            api_key="test-key",
        )
        runtime.start()
        self.assertTrue(runtime.is_running)
        runtime.stop()
        self.assertFalse(runtime.is_running)

    @patch("contextgraph.runtime.engine.get_provider")
    def test_send_returns_text_response(self, mock_get_provider: MagicMock) -> None:
        mock_provider = MagicMock()
        mock_provider.complete.return_value = LLMResponse(
            content="Hello! I can help.",
            tool_calls=[],
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        mock_get_provider.return_value = mock_provider

        runtime = AgentRuntime(
            agent_id=self.agent.agent_id,
            service=self.service,
            api_key="test-key",
        )
        runtime.start()
        response = runtime.send("Hello")
        self.assertEqual(response.content, "Hello! I can help.")
        runtime.stop()

    @patch("contextgraph.runtime.engine.get_provider")
    def test_react_loop_executes_tool_calls(self, mock_get_provider: MagicMock) -> None:
        mock_provider = MagicMock()
        # First call returns tool use, second returns final text
        mock_provider.complete.side_effect = [
            LLMResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="filesystem", arguments={"path": "/test"})],
                usage={"input_tokens": 10, "output_tokens": 5},
            ),
            LLMResponse(
                content="I found the file.",
                tool_calls=[],
                usage={"input_tokens": 20, "output_tokens": 10},
            ),
        ]
        mock_get_provider.return_value = mock_provider

        runtime = AgentRuntime(
            agent_id=self.agent.agent_id,
            service=self.service,
            api_key="test-key",
        )
        runtime.start()
        response = runtime.send("Find the file")
        self.assertEqual(response.content, "I found the file.")
        self.assertEqual(mock_provider.complete.call_count, 2)
        runtime.stop()

    @patch("contextgraph.runtime.engine.get_provider")
    def test_max_iterations_prevents_infinite_loop(self, mock_get_provider: MagicMock) -> None:
        mock_provider = MagicMock()
        # Always returns tool calls — should hit max iterations
        mock_provider.complete.return_value = LLMResponse(
            content="",
            tool_calls=[ToolCall(id="tc1", name="search", arguments={})],
            usage={"input_tokens": 5, "output_tokens": 5},
        )
        mock_get_provider.return_value = mock_provider

        runtime = AgentRuntime(
            agent_id=self.agent.agent_id,
            service=self.service,
            api_key="test-key",
            max_iterations=3,
        )
        runtime.start()
        response = runtime.send("Loop forever")
        # Should stop after max_iterations
        self.assertLessEqual(mock_provider.complete.call_count, 3)
        runtime.stop()

    @patch("contextgraph.runtime.engine.get_provider")
    def test_conversation_history_maintained(self, mock_get_provider: MagicMock) -> None:
        mock_provider = MagicMock()
        mock_provider.complete.return_value = LLMResponse(
            content="Response",
            tool_calls=[],
            usage={"input_tokens": 5, "output_tokens": 5},
        )
        mock_get_provider.return_value = mock_provider

        runtime = AgentRuntime(
            agent_id=self.agent.agent_id,
            service=self.service,
            api_key="test-key",
        )
        runtime.start()
        runtime.send("First message")
        runtime.send("Second message")

        # Check that the second call included history
        second_call_messages = mock_provider.complete.call_args_list[1][0][0]
        self.assertGreater(len(second_call_messages), 1)
        runtime.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_runtime_engine.py::AgentRuntimeTest -v`
Expected: FAIL — `AgentRuntime` not found

- [ ] **Step 3: Implement engine.py**

```python
# contextgraph/runtime/engine.py
from __future__ import annotations

import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from ..service import ContextGraphService
from .providers import LLMResponse, ToolCall, get_provider
from .isolation import get_isolation, IsolationBackend
from .tools import ToolManager

logger = logging.getLogger(__name__)


@dataclass
class AgentRuntime:
    agent_id: str
    service: ContextGraphService
    api_key: str
    max_iterations: int = 10
    _running: bool = field(default=False, init=False)
    _history: list[dict[str, Any]] = field(default_factory=list, init=False)
    _provider: Any = field(default=None, init=False)
    _isolation: Any = field(default=None, init=False)
    _tool_manager: Any = field(default=None, init=False)
    _session_id: str = field(default="", init=False)

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        agent = self.service.get_agent(self.agent_id)
        config = agent.runtime_config

        # Initialize provider
        provider_name = config.get("provider", "claude")
        model = config.get("model", "claude-sonnet-4-6")
        self._provider = get_provider(provider_name, model=model, api_key=self.api_key)

        # Initialize isolation
        isolation_mode = config.get("isolation", "none")
        self._isolation = get_isolation(isolation_mode, agent_id=self.agent_id)
        self._isolation.start()

        # Initialize tools
        self._tool_manager = ToolManager(
            bundles=config.get("bundles", []),
            manual_tools=config.get("manual_tools", []),
            permissions=config.get("tool_permissions", {}),
        )

        self._session_id = uuid.uuid4().hex[:16]
        self._history = []
        self._running = True
        logger.info("AgentRuntime started for %s (session %s)", self.agent_id, self._session_id)

    def stop(self) -> None:
        if self._isolation:
            self._isolation.stop()
        self._running = False
        logger.info("AgentRuntime stopped for %s", self.agent_id)

    def send(self, message: str) -> LLMResponse:
        if not self._running:
            raise RuntimeError("AgentRuntime is not running. Call start() first.")

        agent = self.service.get_agent(self.agent_id)
        config = agent.runtime_config

        # Add user message to history
        self._history.append({"role": "user", "content": message})

        # Trim to context window
        max_messages = config.get("context_window_messages", 20)
        if len(self._history) > max_messages:
            self._history = self._history[-max_messages:]

        # Build messages: SOUL.md as system prompt + conversation history
        soul_md = config.get("soul_md", "You are a helpful assistant.")
        messages = [{"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]} for m in self._history]

        # Get tool definitions
        tools = self._tool_manager.get_tool_definitions() if self._tool_manager else []

        # ReAct loop
        for iteration in range(self.max_iterations):
            response = self._provider.complete(messages, tools, system=soul_md)

            if not response.tool_calls:
                # Final text response
                self._history.append({"role": "assistant", "content": response.content})

                # Auto-store if enabled
                if config.get("auto_store", False) and response.content:
                    try:
                        self.service.store_memory(
                            agent_id=self.agent_id,
                            content=response.content,
                            metadata={"type": "conversation", "session_id": self._session_id},
                        )
                    except Exception:
                        logger.warning("Auto-store failed for agent %s", self.agent_id)

                return response

            # Execute tool calls
            for tc in response.tool_calls:
                tool_result = self._execute_tool(tc)
                messages.append({"role": "assistant", "content": f"[Tool call: {tc.name}({tc.arguments})]"})
                messages.append({"role": "user", "content": f"[Tool result: {tool_result}]"})

        # Max iterations reached
        self._history.append({"role": "assistant", "content": response.content or "(max iterations reached)"})
        return response

    def _execute_tool(self, tool_call: ToolCall) -> str:
        permission = self._tool_manager.get_permission(tool_call.name) if self._tool_manager else "auto"
        if permission == "confirm":
            return f"[Tool {tool_call.name} requires user confirmation — skipped in automated mode]"

        try:
            # For now, return a placeholder — actual MCP routing added when MCP servers are live
            return f"[Tool {tool_call.name} executed with args: {tool_call.arguments}]"
        except Exception as e:
            logger.warning("Tool %s failed: %s", tool_call.name, e)
            return f"[Tool {tool_call.name} error: {e}]"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_runtime_engine.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add contextgraph/runtime/engine.py tests/test_runtime_engine.py
git commit -m "feat: add AgentRuntime engine with ReAct loop and context assembly"
```

---

### Task 6: Service — Runtime lifecycle and chat methods

**Files:**
- Modify: `contextgraph/service.py`
- Test: `tests/test_runtime_chat.py` (create)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_runtime_chat.py
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from contextgraph import ContextGraphService
from contextgraph.models import Visibility


class RuntimeServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.agent = self.service.register_agent("runtime-agent", "acme", ["research"])
        self.agent.runtime_config = {
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "isolation": "none",
            "soul_md": "You are a helpful assistant.",
            "bundles": [],
            "manual_tools": [],
            "tool_permissions": {},
            "auto_store": False,
        }
        self.service.repository.save_agent(self.agent)

    def tearDown(self) -> None:
        # Stop any running runtimes
        try:
            self.service.stop_agent_runtime(
                agent_id=self.agent.agent_id,
                requester_agent_id=self.agent.agent_id,
            )
        except Exception:
            pass
        self.service.close()

    @patch("contextgraph.runtime.engine.get_provider")
    def test_start_agent_runtime(self, mock_get_provider: MagicMock) -> None:
        mock_get_provider.return_value = MagicMock()
        result = self.service.start_agent_runtime(
            agent_id=self.agent.agent_id,
            requester_agent_id=self.agent.agent_id,
            api_key="test-key",
        )
        self.assertEqual(result["status"], "running")

    @patch("contextgraph.runtime.engine.get_provider")
    def test_stop_agent_runtime(self, mock_get_provider: MagicMock) -> None:
        mock_get_provider.return_value = MagicMock()
        self.service.start_agent_runtime(
            agent_id=self.agent.agent_id,
            requester_agent_id=self.agent.agent_id,
            api_key="test-key",
        )
        result = self.service.stop_agent_runtime(
            agent_id=self.agent.agent_id,
            requester_agent_id=self.agent.agent_id,
        )
        self.assertEqual(result["status"], "stopped")

    def test_agent_runtime_status_not_started(self) -> None:
        result = self.service.get_agent_runtime_status(
            agent_id=self.agent.agent_id,
            requester_agent_id=self.agent.agent_id,
        )
        self.assertEqual(result["status"], "stopped")

    def test_update_runtime_config(self) -> None:
        result = self.service.update_runtime_config(
            agent_id=self.agent.agent_id,
            requester_agent_id=self.agent.agent_id,
            config={"model": "claude-opus-4-6", "bundles": ["developer"]},
        )
        self.assertEqual(result.runtime_config["model"], "claude-opus-4-6")
        self.assertEqual(result.runtime_config["bundles"], ["developer"])

    def test_update_runtime_config_cross_org_rejected(self) -> None:
        other = self.service.register_agent("other", "globex", [])
        from contextgraph.errors import PermissionDeniedError

        with self.assertRaises(PermissionDeniedError):
            self.service.update_runtime_config(
                agent_id=self.agent.agent_id,
                requester_agent_id=other.agent_id,
                config={"model": "claude-opus-4-6"},
            )


class ConversationServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.agent = self.service.register_agent("chat-agent", "acme", [])

    def tearDown(self) -> None:
        self.service.close()

    def test_list_conversations_empty(self) -> None:
        result = self.service.list_conversations(
            agent_id=self.agent.agent_id,
            requester_agent_id=self.agent.agent_id,
        )
        self.assertEqual(result, [])

    def test_conversation_stored_as_memory(self) -> None:
        """Conversation messages stored via store_memory are retrievable."""
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="User asked about Python",
            metadata={"type": "conversation", "session_id": "sess-123"},
        )
        result = self.service.list_conversations(
            agent_id=self.agent.agent_id,
            requester_agent_id=self.agent.agent_id,
        )
        self.assertGreater(len(result), 0)


class GenerateSoulTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.agent = self.service.register_agent("soul-agent", "acme", [])

    def tearDown(self) -> None:
        self.service.close()

    def test_generate_soul_without_api_key_returns_template(self) -> None:
        """When no ANTHROPIC_API_KEY is set, returns default template."""
        result = self.service.generate_soul(
            agent_id=self.agent.agent_id,
            requester_agent_id=self.agent.agent_id,
            description="A helpful coding assistant",
        )
        self.assertIn("soul_md", result)
        self.assertGreater(len(result["soul_md"]), 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_runtime_chat.py -v`
Expected: FAIL — methods don't exist

- [ ] **Step 3: Implement service methods**

Add to `contextgraph/service.py` (after existing methods). Add import at top: `from .runtime.engine import AgentRuntime`.

```python
# --- Agent Runtime Lifecycle ---

# In ContextGraphService.__init__(), add:
# self._active_runtimes: dict[str, AgentRuntime] = {}

def start_agent_runtime(
    self,
    agent_id: str,
    requester_agent_id: str,
    api_key: str,
) -> dict[str, Any]:
    requester = self.get_agent(requester_agent_id)
    target = self.get_agent(agent_id)
    if requester.org_id != target.org_id:
        raise PermissionDeniedError("Only agents in the same org can start runtimes.")

    if agent_id in self._active_runtimes:
        return {"status": "running", "agent_id": agent_id}

    runtime = AgentRuntime(
        agent_id=agent_id,
        service=self,
        api_key=api_key,
    )
    runtime.start()
    self._active_runtimes[agent_id] = runtime

    self._audit("start_agent_runtime", actor_agent_id=requester_agent_id, details={"agent_id": agent_id})
    return {"status": "running", "agent_id": agent_id}

def stop_agent_runtime(
    self,
    agent_id: str,
    requester_agent_id: str,
) -> dict[str, Any]:
    requester = self.get_agent(requester_agent_id)
    target = self.get_agent(agent_id)
    if requester.org_id != target.org_id:
        raise PermissionDeniedError("Only agents in the same org can stop runtimes.")

    runtime = self._active_runtimes.pop(agent_id, None)
    if runtime:
        runtime.stop()

    return {"status": "stopped", "agent_id": agent_id}

def get_agent_runtime_status(
    self,
    agent_id: str,
    requester_agent_id: str,
) -> dict[str, Any]:
    self.get_agent(agent_id)  # validate exists
    runtime = self._active_runtimes.get(agent_id)
    status = "running" if runtime and runtime.is_running else "stopped"
    return {"status": status, "agent_id": agent_id}

def chat_with_agent(
    self,
    agent_id: str,
    requester_agent_id: str,
    message: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    runtime = self._active_runtimes.get(agent_id)
    if not runtime or not runtime.is_running:
        raise NotFoundError(f"Agent {agent_id} runtime is not running. Start it first.")

    response = runtime.send(message)
    return {
        "content": response.content,
        "tool_calls": [{"name": tc.name, "arguments": tc.arguments} for tc in response.tool_calls],
        "usage": response.usage,
    }

def update_runtime_config(
    self,
    agent_id: str,
    requester_agent_id: str,
    config: dict[str, Any],
) -> Agent:
    requester = self.get_agent(requester_agent_id)
    target = self.get_agent(agent_id)
    if requester.org_id != target.org_id:
        raise PermissionDeniedError("Only agents in the same org can update runtime config.")

    # Merge config — don't overwrite, update
    target.runtime_config.update(config)
    target.updated_at = utcnow()
    self.repository.save_agent(target)

    self._audit("update_runtime_config", actor_agent_id=requester_agent_id, details={"agent_id": agent_id})
    return target

def list_conversations(
    self,
    agent_id: str,
    requester_agent_id: str,
) -> list[dict[str, Any]]:
    self.get_agent(agent_id)  # validate exists
    # list_memories_by_agent added to Repository protocol in Sub-project 1 (Discovery Panel, Task 3)
    memories = self.repository.list_memories_by_agent(agent_id)
    sessions: dict[str, list[Any]] = {}
    for mem in memories:
        if mem.metadata.get("type") == "conversation":
            sid = mem.metadata.get("session_id", "default")
            sessions.setdefault(sid, []).append(mem)

    return [
        {"session_id": sid, "message_count": len(msgs), "last_message_at": max(m.created_at for m in msgs).isoformat()}
        for sid, msgs in sessions.items()
    ]

def generate_soul(
    self,
    agent_id: str,
    requester_agent_id: str,
    description: str,
) -> dict[str, str]:
    import os
    requester = self.get_agent(requester_agent_id)
    target = self.get_agent(agent_id)
    if requester.org_id != target.org_id:
        raise PermissionDeniedError("Only agents in the same org can generate SOUL.md.")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        # Fallback template
        soul_md = f"# {target.name}\n\n## Role\n{description}\n\n## Goals\n- Help users effectively\n\n## Constraints\n- Be accurate and helpful\n"
        return {"soul_md": soul_md}

    try:
        from .runtime.providers import ClaudeProvider
        provider = ClaudeProvider(api_key=api_key, model="claude-sonnet-4-6")
        response = provider.complete(
            messages=[{"role": "user", "content": f"Generate a SOUL.md personality file for an AI agent described as: {description}\n\nFormat: markdown with sections: Role, Goals, Constraints, Personality."}],
            tools=[],
        )
        return {"soul_md": response.content}
    except Exception:
        soul_md = f"# {target.name}\n\n## Role\n{description}\n\n## Goals\n- Help users effectively\n\n## Constraints\n- Be accurate and helpful\n"
        return {"soul_md": soul_md}
```

**Important:** Before implementing these methods, add `self._active_runtimes: dict[str, AgentRuntime] = {}` to `ContextGraphService.__init__()` (find it in `service.py`). All the methods below reference `self._active_runtimes` — it must be an instance attribute, not a module-level variable. Also add the import: `from .runtime.engine import AgentRuntime`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_runtime_chat.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add contextgraph/service.py tests/test_runtime_chat.py
git commit -m "feat: add runtime lifecycle, chat, and SOUL.md generation service methods"
```

---

### Task 7: API — Runtime and chat endpoints

**Files:**
- Modify: `contextgraph/api/schemas.py`
- Modify: `contextgraph/api/routes.py`
- Test: `tests/test_runtime_api.py` (create)

- [ ] **Step 1: Add request/response schemas**

Add to `contextgraph/api/schemas.py`:

```python
class RuntimeStatusResponse(BaseModel):
    status: str  # "running" | "stopped" | "error"
    agent_id: str


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    content: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)


class ConversationListResponse(BaseModel):
    session_id: str
    message_count: int
    last_message_at: datetime


class RuntimeConfigUpdateRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    isolation: str | None = None
    soul_md: str | None = None
    bundles: list[str] | None = None
    manual_tools: list[dict[str, Any]] | None = None
    tool_permissions: dict[str, str] | None = None
    resource_limits: dict[str, Any] | None = None
    auto_store: bool | None = None
    context_window_messages: int | None = None
    role_label: str | None = None


class GenerateSoulRequest(BaseModel):
    description: str


class GenerateSoulResponse(BaseModel):
    soul_md: str


class ToolBundleResponse(BaseModel):
    name: str
    description: str
    servers: list[dict[str, Any]]
```

- [ ] **Step 2: Add API endpoints**

Add to `contextgraph/api/routes.py` inside `register_routes()`. Place these **after** existing agent endpoints. Add schema imports at top.

```python
# --- Tool bundles (no auth required for listing) ---

@app.get("/v1/tools/bundles")
def list_tool_bundles() -> Any:
    from contextgraph.runtime.tools import load_bundles
    bundles = load_bundles()
    return [
        {"name": name, "description": b["description"], "servers": b["servers"]}
        for name, b in bundles.items()
    ]

# --- Agent runtime lifecycle ---

@app.post("/v1/agents/{agent_id}/start", response_model=RuntimeStatusResponse)
def start_agent_runtime(
    agent_id: str,
    authenticated: Any = Depends(authenticated_agent),
) -> Any:
    return graph.start_agent_runtime(
        agent_id=agent_id,
        requester_agent_id=authenticated.agent_id,
        api_key=authenticated.api_key,
    )

@app.post("/v1/agents/{agent_id}/stop", response_model=RuntimeStatusResponse)
def stop_agent_runtime(
    agent_id: str,
    authenticated: Any = Depends(authenticated_agent),
) -> Any:
    return graph.stop_agent_runtime(
        agent_id=agent_id,
        requester_agent_id=authenticated.agent_id,
    )

@app.get("/v1/agents/{agent_id}/status", response_model=RuntimeStatusResponse)
def agent_runtime_status(
    agent_id: str,
    authenticated: Any = Depends(authenticated_agent),
) -> Any:
    return graph.get_agent_runtime_status(
        agent_id=agent_id,
        requester_agent_id=authenticated.agent_id,
    )

@app.post("/v1/agents/{agent_id}/chat", response_model=ChatResponse)
def chat_with_agent(
    agent_id: str,
    payload: ChatRequest,
    authenticated: Any = Depends(authenticated_agent),
) -> Any:
    return graph.chat_with_agent(
        agent_id=agent_id,
        requester_agent_id=authenticated.agent_id,
        message=payload.message,
        session_id=payload.session_id,
    )

@app.get("/v1/agents/{agent_id}/conversations")
def list_conversations(
    agent_id: str,
    authenticated: Any = Depends(authenticated_agent),
) -> Any:
    return graph.list_conversations(
        agent_id=agent_id,
        requester_agent_id=authenticated.agent_id,
    )

@app.post("/v1/agents/{agent_id}/generate-soul", response_model=GenerateSoulResponse)
def generate_soul(
    agent_id: str,
    payload: GenerateSoulRequest,
    authenticated: Any = Depends(authenticated_agent),
) -> Any:
    return graph.generate_soul(
        agent_id=agent_id,
        requester_agent_id=authenticated.agent_id,
        description=payload.description,
    )

@app.patch("/v1/agents/{agent_id}/runtime-config", response_model=AgentResponse)
def update_runtime_config(
    agent_id: str,
    payload: RuntimeConfigUpdateRequest,
    authenticated: Any = Depends(authenticated_agent),
) -> Any:
    # Build config dict from non-None fields
    config = {k: v for k, v in payload.model_dump().items() if v is not None}
    return to_jsonable(
        graph.update_runtime_config(
            agent_id=agent_id,
            requester_agent_id=authenticated.agent_id,
            config=config,
        )
    )
```

- [ ] **Step 3: Write API tests**

```python
# tests/test_runtime_api.py
from __future__ import annotations

import unittest

from contextgraph import ContextGraphService
from contextgraph.runtime.tools import load_bundles


class ToolBundlesAPITest(unittest.TestCase):
    def test_load_bundles_returns_all_bundles(self) -> None:
        bundles = load_bundles()
        self.assertIn("developer", bundles)
        self.assertIn("research", bundles)
        self.assertIn("data", bundles)
        self.assertIn("communication", bundles)
        self.assertIn("minimal", bundles)


class RuntimeConfigAPITest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.agent = self.service.register_agent("api-test", "acme", [])

    def tearDown(self) -> None:
        self.service.close()

    def test_update_runtime_config_merges(self) -> None:
        self.agent.runtime_config = {"provider": "claude", "model": "claude-sonnet-4-6"}
        self.service.repository.save_agent(self.agent)

        updated = self.service.update_runtime_config(
            agent_id=self.agent.agent_id,
            requester_agent_id=self.agent.agent_id,
            config={"bundles": ["developer"]},
        )
        # Original keys preserved
        self.assertEqual(updated.runtime_config["provider"], "claude")
        # New key added
        self.assertEqual(updated.runtime_config["bundles"], ["developer"])

    def test_generate_soul_returns_markdown(self) -> None:
        result = self.service.generate_soul(
            agent_id=self.agent.agent_id,
            requester_agent_id=self.agent.agent_id,
            description="A research assistant for scientific papers",
        )
        self.assertIn("soul_md", result)
        self.assertIn("research", result["soul_md"].lower())
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_runtime_api.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add contextgraph/api/schemas.py contextgraph/api/routes.py tests/test_runtime_api.py
git commit -m "feat: add runtime lifecycle, chat, and tools API endpoints"
```

---

### Task 8: SDK — Add runtime and chat client methods

**Files:**
- Modify: `sdk/contextgraph_sdk/client.py`
- Modify: `sdk/contextgraph_sdk/_local.py`

- [ ] **Step 1: Add to Transport protocol**

In `sdk/contextgraph_sdk/client.py`, add to the `Transport` protocol class (after line 45):

```python
def start_agent(self, payload: dict[str, Any]) -> dict[str, Any]: ...
def stop_agent(self, payload: dict[str, Any]) -> dict[str, Any]: ...
def agent_status(self, payload: dict[str, Any]) -> dict[str, Any]: ...
def chat(self, payload: dict[str, Any]) -> dict[str, Any]: ...
def list_conversations(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...
def get_conversation(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...
def list_tool_bundles(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...
def generate_soul(self, payload: dict[str, Any]) -> dict[str, Any]: ...
def update_runtime_config(self, payload: dict[str, Any]) -> dict[str, Any]: ...
```

- [ ] **Step 2: Add HttpTransport methods**

```python
def start_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
    return self._request("POST", f"/v1/agents/{payload['agent_id']}/start")

def stop_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
    return self._request("POST", f"/v1/agents/{payload['agent_id']}/stop")

def agent_status(self, payload: dict[str, Any]) -> dict[str, Any]:
    return self._request("GET", f"/v1/agents/{payload['agent_id']}/status")

def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
    local = dict(payload)
    agent_id = local.pop("agent_id")
    return self._request("POST", f"/v1/agents/{agent_id}/chat", local)

def list_conversations(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
    return self._request("GET", f"/v1/agents/{payload['agent_id']}/conversations")

def get_conversation(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
    return self._request("GET", f"/v1/agents/{payload['agent_id']}/conversations/{payload['session_id']}")

def list_tool_bundles(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
    return self._request("GET", "/v1/tools/bundles")

def generate_soul(self, payload: dict[str, Any]) -> dict[str, Any]:
    local = dict(payload)
    agent_id = local.pop("agent_id")
    return self._request("POST", f"/v1/agents/{agent_id}/generate-soul", local)

def update_runtime_config(self, payload: dict[str, Any]) -> dict[str, Any]:
    local = dict(payload)
    agent_id = local.pop("agent_id")
    return self._request("PATCH", f"/v1/agents/{agent_id}/runtime-config", local)
```

- [ ] **Step 3: Add ContextGraph class methods**

```python
def start_agent(self) -> dict[str, Any]:
    return self.transport.start_agent({"agent_id": self._agent_id})

def stop_agent(self) -> dict[str, Any]:
    return self.transport.stop_agent({"agent_id": self._agent_id})

def agent_status(self) -> dict[str, Any]:
    return self.transport.agent_status({"agent_id": self._agent_id})

def chat(self, message: str, session_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"agent_id": self._agent_id, "message": message}
    if session_id:
        payload["session_id"] = session_id
    return self.transport.chat(payload)

def list_conversations(self, agent_id: str | None = None) -> list[dict[str, Any]]:
    return self.transport.list_conversations({"agent_id": agent_id or self._agent_id})

def get_conversation(self, session_id: str, agent_id: str | None = None) -> list[dict[str, Any]]:
    return self.transport.get_conversation({
        "agent_id": agent_id or self._agent_id,
        "session_id": session_id,
    })

def list_tool_bundles(self) -> list[dict[str, Any]]:
    return self.transport.list_tool_bundles({})

def generate_soul(self, description: str) -> dict[str, Any]:
    return self.transport.generate_soul({
        "agent_id": self._agent_id,
        "description": description,
    })

def update_runtime_config(self, config: dict[str, Any]) -> dict[str, Any]:
    payload = {"agent_id": self._agent_id}
    payload.update(config)
    return self.transport.update_runtime_config(payload)
```

- [ ] **Step 4: Add LocalTransport methods**

Add to `sdk/contextgraph_sdk/_local.py`:

```python
def start_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
    return to_jsonable(self.service.start_agent_runtime(
        agent_id=payload["agent_id"],
        requester_agent_id=payload["agent_id"],
        api_key="local-transport",
    ))

def stop_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
    return to_jsonable(self.service.stop_agent_runtime(
        agent_id=payload["agent_id"],
        requester_agent_id=payload["agent_id"],
    ))

def agent_status(self, payload: dict[str, Any]) -> dict[str, Any]:
    return to_jsonable(self.service.get_agent_runtime_status(
        agent_id=payload["agent_id"],
        requester_agent_id=payload["agent_id"],
    ))

def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
    return to_jsonable(self.service.chat_with_agent(
        agent_id=payload["agent_id"],
        requester_agent_id=payload["agent_id"],
        message=payload["message"],
        session_id=payload.get("session_id"),
    ))

def list_conversations(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
    return to_jsonable(self.service.list_conversations(
        agent_id=payload["agent_id"],
        requester_agent_id=payload["agent_id"],
    ))

def get_conversation(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
    return []  # placeholder — session-based retrieval added later

def list_tool_bundles(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
    from contextgraph.runtime.tools import load_bundles
    bundles = load_bundles()
    return [{"name": n, **b} for n, b in bundles.items()]

def generate_soul(self, payload: dict[str, Any]) -> dict[str, Any]:
    return to_jsonable(self.service.generate_soul(
        agent_id=payload["agent_id"],
        requester_agent_id=payload["agent_id"],
        description=payload["description"],
    ))

def update_runtime_config(self, payload: dict[str, Any]) -> dict[str, Any]:
    local = dict(payload)
    agent_id = local.pop("agent_id")
    return to_jsonable(self.service.update_runtime_config(
        agent_id=agent_id,
        requester_agent_id=agent_id,
        config=local,
    ))
```

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add sdk/contextgraph_sdk/client.py sdk/contextgraph_sdk/_local.py
git commit -m "feat: add runtime and chat SDK client methods"
```

---

### Task 9: CLI — Runtime and tools commands

**Files:**
- Modify: `contextgraph/cli.py`

- [ ] **Step 1: Read cli.py to find the subparser pattern**

Read the bottom of `contextgraph/cli.py` to find where subcommands are registered (look for `add_parser` calls). The existing pattern uses `argparse` subparsers with `cmd_` handler functions.

- [ ] **Step 2: Add runtime commands**

Following the existing pattern, add these command handlers:

```python
def cmd_agents_start(args: argparse.Namespace, client: Any) -> None:
    """Start agent runtime."""
    result = client.start_agent({"agent_id": args.agent_id})
    _ok(f"Agent {args.agent_id} runtime: {result.get('status', 'unknown')}")

def cmd_agents_stop(args: argparse.Namespace, client: Any) -> None:
    """Stop agent runtime."""
    result = client.stop_agent({"agent_id": args.agent_id})
    _ok(f"Agent {args.agent_id} runtime: {result.get('status', 'unknown')}")

def cmd_agents_status(args: argparse.Namespace, client: Any) -> None:
    """Check agent runtime status."""
    result = client.agent_status({"agent_id": args.agent_id})
    status = result.get("status", "unknown")
    color = GREEN if status == "running" else YELLOW if status == "stopped" else RED
    print(f"{color}Runtime status: {status}{RESET}")

def cmd_agents_chat(args: argparse.Namespace, client: Any) -> None:
    """Interactive chat with agent."""
    agent_id = args.agent_id
    _info(f"Chatting with agent {agent_id}. Type 'quit' to exit.")
    while True:
        try:
            msg = input(f"{BOLD}You:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if msg.lower() in ("quit", "exit", "q"):
            break
        if not msg:
            continue
        try:
            result = client.chat({"agent_id": agent_id, "message": msg})
            print(f"{CYAN}Agent:{RESET} {result.get('content', '')}")
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")

def cmd_tools_bundles(args: argparse.Namespace, client: Any) -> None:
    """List available tool bundles."""
    bundles = client.list_tool_bundles({})
    for b in bundles:
        name = b.get("name", "?")
        desc = b.get("description", "")
        servers = b.get("servers", [])
        server_names = ", ".join(s.get("name", "?") for s in servers)
        print(f"  {BOLD}{name}{RESET}: {desc}")
        print(f"    Servers: {_dim(server_names)}")
```

- [ ] **Step 3: Register subparsers**

Find the subparser registration section and add:

```python
# Under agents subparser:
p = agents_sub.add_parser("start", help="Start agent runtime")
p.add_argument("agent_id")
p.set_defaults(func=cmd_agents_start)

p = agents_sub.add_parser("stop", help="Stop agent runtime")
p.add_argument("agent_id")
p.set_defaults(func=cmd_agents_stop)

p = agents_sub.add_parser("status", help="Check agent runtime status")
p.add_argument("agent_id")
p.set_defaults(func=cmd_agents_status)

p = agents_sub.add_parser("chat", help="Interactive chat with agent")
p.add_argument("agent_id")
p.set_defaults(func=cmd_agents_chat)

# New tools top-level command:
tools_parser = sub.add_parser("tools", help="Tool management")
tools_sub = tools_parser.add_subparsers(dest="tools_cmd")

p = tools_sub.add_parser("bundles", help="List available tool bundles")
p.set_defaults(func=cmd_tools_bundles)
```

- [ ] **Step 4: Test manually**

Run: `python -m contextgraph.cli tools bundles`
Expected: Lists all 5 bundles with descriptions

- [ ] **Step 5: Commit**

```bash
git add contextgraph/cli.py
git commit -m "feat: add runtime lifecycle and tools CLI commands"
```

---

### Task 10: Dashboard — Agent Creation Wizard

**Files:**
- Modify: `contextgraph/api/dashboard.py`

- [ ] **Step 1: Add "Create Agent" button and route**

In `_render_app()`, add a "Create Agent" button to the top bar or agents page header. Add route handler for "create-agent" page in `_render_page()`:

```python
if page == "create-agent":
    return _render_create_agent(graph, agent)
```

- [ ] **Step 2: Implement `_render_create_agent()` — 4-step wizard**

The wizard is a single page with 4 steps controlled by JS (visibility toggle, no page reload between steps). Each step is a `<div>` shown/hidden by JS.

```python
def _render_create_agent(graph: ContextGraphService, viewer: Any) -> str:
    from contextgraph.runtime.tools import load_bundles
    bundles = load_bundles()

    bundle_cards = ""
    for name, bundle in bundles.items():
        servers = ", ".join(s["name"] for s in bundle["servers"])
        bundle_cards += f"""\
<label class="item-card" style="cursor:pointer;margin-bottom:8px;display:block">
    <input type="checkbox" name="bundles" value="{name}" style="margin-right:8px">
    <b>{name.title()}</b> — {bundle['description']}<br>
    <span style="font-size:11px;color:var(--text-muted)">{servers}</span>
</label>"""

    js = """\
<script>
let currentStep = 1;
function showStep(n) {
    for (let i = 1; i <= 4; i++) {
        document.getElementById('step-' + i).style.display = i === n ? 'block' : 'none';
        const btn = document.getElementById('step-btn-' + i);
        if (btn) btn.classList.toggle('active', i === n);
    }
    currentStep = n;
}
function nextStep() { if (currentStep < 4) showStep(currentStep + 1); }
function prevStep() { if (currentStep > 1) showStep(currentStep - 1); }
async function createAgent() {
    const name = document.getElementById('agent-name').value;
    const orgId = document.getElementById('agent-org').value;
    const roleLabel = document.getElementById('agent-role').value;
    const bundles = [...document.querySelectorAll('input[name=bundles]:checked')].map(c => c.value);
    const isolation = document.getElementById('agent-isolation').value;
    const soulMd = document.getElementById('agent-soul').value;
    const provider = document.getElementById('agent-provider').value;
    const model = document.getElementById('agent-model').value;
    const visibility = document.getElementById('agent-visibility').value;

    const key = document.cookie.split('cg_session=')[1]?.split(';')[0];
    const headers = {'Content-Type':'application/json', 'X-Agent-Key': key};

    // Step 1: Register agent
    const reg = await fetch('/v1/agents/register', {
        method: 'POST', headers,
        body: JSON.stringify({name, org_id: orgId, capabilities: []})
    }).then(r => r.json());

    const agentId = reg.agent_id;

    // Step 2: Save runtime config
    await fetch('/v1/agents/' + agentId + '/runtime-config', {
        method: 'PATCH', headers,
        body: JSON.stringify({provider, model, isolation, soul_md: soulMd, bundles, role_label: roleLabel})
    });

    // Step 3: Start runtime
    await fetch('/v1/agents/' + agentId + '/start', {method: 'POST', headers});

    // Redirect to agent detail
    window.location.href = '/dashboard/agents/' + agentId;
}
async function generateSoul() {
    const desc = document.getElementById('agent-describe').value;
    const key = document.cookie.split('cg_session=')[1]?.split(';')[0];
    const agentId = document.getElementById('agent-org').dataset.agentId || '';
    // Use a temporary approach — generate in the browser for now
    const soul = '# ' + document.getElementById('agent-name').value + '\\n\\n## Role\\n' + desc + '\\n\\n## Goals\\n- Help users effectively\\n\\n## Constraints\\n- Be accurate and helpful';
    document.getElementById('agent-soul').value = soul;
}
</script>"""

    return f"""\
<div class="page-header">
    <h2>Create Agent</h2>
</div>
<div style="display:flex;gap:8px;margin-bottom:16px;border-bottom:1px solid var(--border);padding-bottom:8px">
    <button class="btn btn-sm tab-btn active" id="step-btn-1" onclick="showStep(1)">1. Identity</button>
    <button class="btn btn-sm tab-btn" id="step-btn-2" onclick="showStep(2)">2. Tools</button>
    <button class="btn btn-sm tab-btn" id="step-btn-3" onclick="showStep(3)">3. Personality</button>
    <button class="btn btn-sm tab-btn" id="step-btn-4" onclick="showStep(4)">4. Review</button>
</div>

<div id="step-1">
    <h3 style="font-size:14px;margin-bottom:12px">Agent Identity</h3>
    <div style="display:grid;gap:12px;max-width:400px">
        <div>
            <label style="font-size:12px;color:var(--text-secondary)">Name</label>
            <input id="agent-name" type="text" placeholder="my-research-agent" style="width:100%;padding:8px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text-primary)">
        </div>
        <div>
            <label style="font-size:12px;color:var(--text-secondary)">Organization</label>
            <input id="agent-org" type="text" value="{viewer.org_id}" style="width:100%;padding:8px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text-primary)">
        </div>
        <div>
            <label style="font-size:12px;color:var(--text-secondary)">Role</label>
            <select id="agent-role" style="width:100%;padding:8px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text-primary)">
                <option value="assistant">Assistant</option>
                <option value="researcher">Researcher</option>
                <option value="developer">Developer</option>
                <option value="analyst">Analyst</option>
                <option value="custom">Custom</option>
            </select>
        </div>
    </div>
    <button class="btn" style="margin-top:16px" onclick="nextStep()">Next →</button>
</div>

<div id="step-2" style="display:none">
    <h3 style="font-size:14px;margin-bottom:12px">Tools & Capabilities</h3>
    <div style="max-width:500px">{bundle_cards}</div>
    <div style="margin-top:12px">
        <label style="font-size:12px;color:var(--text-secondary)">Isolation</label>
        <select id="agent-isolation" style="padding:8px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text-primary)">
            <option value="process">Process (default)</option>
            <option value="docker">Docker</option>
            <option value="none">None (dev only)</option>
        </select>
    </div>
    <div style="margin-top:16px">
        <button class="btn btn-sm" onclick="prevStep()">← Back</button>
        <button class="btn" onclick="nextStep()">Next →</button>
    </div>
</div>

<div id="step-3" style="display:none">
    <h3 style="font-size:14px;margin-bottom:12px">Personality</h3>
    <div style="margin-bottom:12px">
        <label style="font-size:12px;color:var(--text-secondary)">Describe your agent (optional — generates SOUL.md)</label>
        <textarea id="agent-describe" rows="3" placeholder="A research assistant that summarizes scientific papers..."
            style="width:100%;max-width:500px;padding:8px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text-primary);font-family:inherit"></textarea>
        <button class="btn btn-sm" onclick="generateSoul()" style="margin-top:4px">Generate SOUL.md</button>
    </div>
    <div>
        <label style="font-size:12px;color:var(--text-secondary)">SOUL.md</label>
        <textarea id="agent-soul" rows="10" placeholder="# Agent Name&#10;&#10;## Role&#10;...&#10;&#10;## Goals&#10;...&#10;&#10;## Constraints&#10;..."
            style="width:100%;max-width:500px;padding:8px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text-primary);font-family:monospace;font-size:12px"></textarea>
    </div>
    <div style="margin-top:16px">
        <button class="btn btn-sm" onclick="prevStep()">← Back</button>
        <button class="btn" onclick="nextStep()">Next →</button>
    </div>
</div>

<div id="step-4" style="display:none">
    <h3 style="font-size:14px;margin-bottom:12px">Review & Create</h3>
    <div style="display:grid;gap:12px;max-width:400px">
        <div>
            <label style="font-size:12px;color:var(--text-secondary)">Provider</label>
            <select id="agent-provider" style="width:100%;padding:8px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text-primary)">
                <option value="claude">Claude (default)</option>
            </select>
        </div>
        <div>
            <label style="font-size:12px;color:var(--text-secondary)">Model</label>
            <select id="agent-model" style="width:100%;padding:8px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text-primary)">
                <option value="claude-sonnet-4-6">Claude Sonnet 4.6 (fast)</option>
                <option value="claude-opus-4-6">Claude Opus 4.6 (powerful)</option>
            </select>
        </div>
        <div>
            <label style="font-size:12px;color:var(--text-secondary)">Visibility</label>
            <select id="agent-visibility" style="width:100%;padding:8px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text-primary)">
                <option value="org">Organization</option>
                <option value="private">Private</option>
                <option value="published">Published</option>
            </select>
        </div>
    </div>
    <div style="margin-top:16px">
        <button class="btn btn-sm" onclick="prevStep()">← Back</button>
        <button class="btn" style="background:var(--accent-green);color:#000" onclick="createAgent()">Create Agent</button>
    </div>
</div>
{js}"""
```

- [ ] **Step 3: Test manually**

Start the server and navigate to `/dashboard/create-agent`. Verify:
- All 4 steps navigate correctly
- Bundle cards show with checkboxes
- SOUL.md textarea works
- Create Agent button calls the correct API flow

- [ ] **Step 4: Commit**

```bash
git add contextgraph/api/dashboard.py
git commit -m "feat: add agent creation wizard to dashboard"
```

---

### Task 11: Dashboard — Chat Interface

**Files:**
- Modify: `contextgraph/api/dashboard.py`

- [ ] **Step 1: Add chat page route**

In `_render_page()`, add handler for chat page:

```python
if page == "chat" and page_id:
    return _render_chat(graph, agent, page_id)
```

- [ ] **Step 2: Implement chat widget on agent detail page**

Add a collapsible chat panel to the bottom of the agent detail page (from Task 8 of the Discovery Panel plan). Append to the end of `_render_agent_detail()` return value:

```python
chat_widget = f"""\
<div id="chat-widget" style="position:fixed;bottom:0;right:24px;width:380px;border:1px solid var(--border);border-radius:8px 8px 0 0;background:var(--bg-secondary);box-shadow:0 -2px 8px rgba(0,0,0,0.3);z-index:100">
    <div onclick="toggleChat()" style="padding:10px 16px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--border)">
        <span style="font-size:13px;font-weight:600">Chat with {escape(target.name)}</span>
        <span id="chat-toggle">▲</span>
    </div>
    <div id="chat-body" style="display:none">
        <div id="chat-messages" style="height:300px;overflow-y:auto;padding:12px;font-size:13px"></div>
        <div style="padding:8px;border-top:1px solid var(--border);display:flex;gap:8px">
            <input id="chat-input" type="text" placeholder="Type a message..."
                   style="flex:1;padding:8px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text-primary);font-size:13px"
                   onkeydown="if(event.key==='Enter')sendChatMsg()">
            <button class="btn btn-sm" onclick="sendChatMsg()">Send</button>
        </div>
        <div style="padding:4px 8px;text-align:center">
            <a href="/dashboard/chat/{agent_id}" style="font-size:11px;color:var(--text-muted)">View full chat →</a>
        </div>
    </div>
</div>
<script>
function toggleChat() {{
    const body = document.getElementById('chat-body');
    const toggle = document.getElementById('chat-toggle');
    body.style.display = body.style.display === 'none' ? 'block' : 'none';
    toggle.textContent = body.style.display === 'none' ? '▲' : '▼';
}}
function sendChatMsg() {{
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';
    const msgs = document.getElementById('chat-messages');
    msgs.innerHTML += '<div style="text-align:right;margin:4px 0"><span style="background:var(--accent-blue);color:#fff;padding:4px 10px;border-radius:12px;display:inline-block;max-width:80%">' + msg + '</span></div>';
    msgs.scrollTop = msgs.scrollHeight;

    const key = document.cookie.split('cg_session=')[1]?.split(';')[0];
    fetch('/v1/agents/{agent_id}/chat', {{
        method: 'POST',
        headers: {{'Content-Type':'application/json', 'X-Agent-Key': key}},
        body: JSON.stringify({{message: msg}})
    }}).then(r => r.json()).then(data => {{
        msgs.innerHTML += '<div style="text-align:left;margin:4px 0"><span style="background:var(--bg-tertiary);padding:4px 10px;border-radius:12px;display:inline-block;max-width:80%">' + (data.content || 'No response') + '</span></div>';
        msgs.scrollTop = msgs.scrollHeight;
    }}).catch(e => {{
        msgs.innerHTML += '<div style="color:var(--accent-red);font-size:12px;margin:4px">Error: ' + e.message + '</div>';
    }});
}}
</script>"""
```

- [ ] **Step 3: Implement full chat page**

```python
def _render_chat(graph: ContextGraphService, viewer: Any, agent_id: str) -> str:
    try:
        target = graph.get_agent(agent_id)
    except Exception:
        return '<div style="color:var(--accent-red)">Agent not found</div>'

    status = graph.get_agent_runtime_status(
        agent_id=agent_id,
        requester_agent_id=viewer.agent_id,
    )
    status_color = {"running": "green", "stopped": "orange", "error": "red"}.get(status["status"], "")
    status_dot = {"running": "🟢", "stopped": "🟡", "error": "🔴"}.get(status["status"], "⚪")

    conversations = graph.list_conversations(
        agent_id=agent_id,
        requester_agent_id=viewer.agent_id,
    )

    conv_list = ""
    for conv in conversations:
        conv_list += f"""\
<div class="item-card" style="margin-bottom:4px;padding:8px;cursor:pointer">
    <div style="font-size:12px;font-weight:600">{conv['session_id'][:12]}...</div>
    <div style="font-size:11px;color:var(--text-muted)">{conv['message_count']} messages</div>
</div>"""

    chat_js = f"""\
<script>
function sendMessage() {{
    const input = document.getElementById('full-chat-input');
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';
    const msgs = document.getElementById('full-chat-messages');
    msgs.innerHTML += '<div style="text-align:right;margin:8px 0"><span style="background:var(--accent-blue);color:#fff;padding:6px 12px;border-radius:12px;display:inline-block;max-width:70%">' + msg + '</span></div>';
    msgs.scrollTop = msgs.scrollHeight;

    const key = document.cookie.split('cg_session=')[1]?.split(';')[0];
    fetch('/v1/agents/{agent_id}/chat', {{
        method: 'POST',
        headers: {{'Content-Type':'application/json', 'X-Agent-Key': key}},
        body: JSON.stringify({{message: msg}})
    }}).then(r => r.json()).then(data => {{
        msgs.innerHTML += '<div style="text-align:left;margin:8px 0"><span style="background:var(--bg-tertiary);padding:6px 12px;border-radius:12px;display:inline-block;max-width:70%">' + (data.content || 'No response') + '</span></div>';
        if (data.tool_calls && data.tool_calls.length > 0) {{
            data.tool_calls.forEach(tc => {{
                msgs.innerHTML += '<div style="margin:4px 0;padding:4px 8px;background:var(--bg-tertiary);border-radius:4px;font-size:11px;color:var(--text-muted)">🔧 ' + tc.name + '</div>';
            }});
        }}
        msgs.scrollTop = msgs.scrollHeight;
    }}).catch(e => {{
        msgs.innerHTML += '<div style="color:var(--accent-red);margin:4px">Error: ' + e.message + '</div>';
    }});
}}
function toggleRuntime() {{
    const key = document.cookie.split('cg_session=')[1]?.split(';')[0];
    const status = document.getElementById('runtime-status').dataset.status;
    const action = status === 'running' ? 'stop' : 'start';
    fetch('/v1/agents/{agent_id}/' + action, {{
        method: 'POST',
        headers: {{'Content-Type':'application/json', 'X-Agent-Key': key}}
    }}).then(() => window.location.reload());
}}
</script>"""

    return f"""\
<div class="page-header">
    <h2 style="display:flex;align-items:center;gap:8px">
        Chat: {escape(target.name)}
        <span class="badge badge-{status_color}">{status_dot} {status['status']}</span>
        <button class="btn btn-sm" onclick="toggleRuntime()" id="runtime-status" data-status="{status['status']}">
            {'Stop' if status['status'] == 'running' else 'Start'}
        </button>
    </h2>
</div>
<div style="display:flex;gap:16px;height:calc(100vh - 200px)">
    <div style="width:200px;overflow-y:auto">
        <h4 style="font-size:12px;color:var(--text-secondary);margin-bottom:8px">Conversations</h4>
        {conv_list or '<div style="color:var(--text-muted);font-size:12px">No conversations yet</div>'}
    </div>
    <div style="flex:1;display:flex;flex-direction:column;border:1px solid var(--border);border-radius:8px;overflow:hidden">
        <div id="full-chat-messages" style="flex:1;overflow-y:auto;padding:16px"></div>
        <div style="padding:12px;border-top:1px solid var(--border);display:flex;gap:8px">
            <input id="full-chat-input" type="text" placeholder="Type a message..."
                   style="flex:1;padding:10px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:6px;color:var(--text-primary)"
                   onkeydown="if(event.key==='Enter')sendMessage()">
            <button class="btn" onclick="sendMessage()">Send</button>
        </div>
    </div>
    <div style="width:200px;overflow-y:auto">
        <h4 style="font-size:12px;color:var(--text-secondary);margin-bottom:8px">Agent Info</h4>
        <div style="font-size:12px;color:var(--text-primary)">{escape(target.name)}</div>
        <div style="font-size:11px;color:var(--text-muted)">{escape(target.org_id)}</div>
        <div style="font-size:11px;margin-top:8px">Trust: <b>{target.reputation_score:.2f}</b></div>
    </div>
</div>
{chat_js}"""
```

- [ ] **Step 4: Test manually**

Start the server and:
- Navigate to an agent detail page — verify chat widget appears
- Navigate to `/dashboard/chat/{agent_id}` — verify full chat page renders
- Start/stop runtime via button
- Send messages (requires runtime started with valid provider key)

- [ ] **Step 5: Commit**

```bash
git add contextgraph/api/dashboard.py
git commit -m "feat: add chat widget and full chat page to dashboard"
```

---

### Task 12: Verification & Cleanup

**Files:** All modified files

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests pass (existing + ~25 new tests)

- [ ] **Step 2: Run linter**

```bash
ruff check contextgraph/ sdk/ tests/
ruff format --check contextgraph/ sdk/ tests/
```

Fix any issues found.

- [ ] **Step 3: Format code**

```bash
ruff format contextgraph/ sdk/ tests/
```

- [ ] **Step 4: Verify runtime package structure**

```bash
python -c "
from contextgraph.runtime.providers import ClaudeProvider, LLMResponse, ToolCall, get_provider
from contextgraph.runtime.isolation import ProcessIsolation, DockerIsolation, get_isolation, docker_available
from contextgraph.runtime.tools import ToolManager, load_bundles
from contextgraph.runtime.engine import AgentRuntime
print('All runtime imports OK')
print(f'Bundles: {list(load_bundles().keys())}')
print(f'Docker available: {docker_available()}')
"
```

- [ ] **Step 5: Verify API endpoints registered**

```bash
python -c "
from contextgraph import ContextGraphService
s = ContextGraphService()
a = s.register_agent('test', 'acme', [])
a.runtime_config = {'provider': 'claude', 'model': 'claude-sonnet-4-6', 'isolation': 'none', 'soul_md': 'test', 'bundles': [], 'manual_tools': [], 'tool_permissions': {}}
s.repository.save_agent(a)
status = s.get_agent_runtime_status(agent_id=a.agent_id, requester_agent_id=a.agent_id)
print(f'Status: {status}')
config = s.update_runtime_config(agent_id=a.agent_id, requester_agent_id=a.agent_id, config={'bundles': ['developer']})
print(f'Config updated: {config.runtime_config.get(\"bundles\")}')
soul = s.generate_soul(agent_id=a.agent_id, requester_agent_id=a.agent_id, description='A coding assistant')
print(f'SOUL generated: {len(soul[\"soul_md\"])} chars')
s.close()
print('OK: all service methods work')
"
```

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: lint and format one-click agent creation"
```

---

## Verification Checklist

```bash
# 1. All tests pass
python -m pytest tests/ -v

# 2. Linter clean
ruff check contextgraph/ sdk/ tests/

# 3. Runtime package imports work
python -c "from contextgraph.runtime.engine import AgentRuntime; print('OK')"

# 4. Bundles load correctly
python -c "from contextgraph.runtime.tools import load_bundles; print(list(load_bundles().keys()))"

# 5. Service methods work end-to-end
python -c "
from contextgraph import ContextGraphService
s = ContextGraphService()
a = s.register_agent('e2e-test', 'acme', [])
# Runtime config
s.update_runtime_config(a.agent_id, a.agent_id, {'provider':'claude','isolation':'none','soul_md':'test','bundles':[],'manual_tools':[],'tool_permissions':{}})
# Status check
print(s.get_agent_runtime_status(a.agent_id, a.agent_id))
# SOUL generation
print(s.generate_soul(a.agent_id, a.agent_id, 'A helper bot')['soul_md'][:50])
# Conversations
print(s.list_conversations(a.agent_id, a.agent_id))
s.close()
print('All checks passed')
"
```

---

## Deferred Features (V2)

| Feature | Spec Section | Reason for Deferral |
|---------|-------------|---------------------|
| **SSE streaming for chat** | Chat SSE | Initial implementation uses synchronous POST/response. SSE streaming requires wiring `StreamingResponse` and client-side `EventSource`. Will add as enhancement. |
| **`GET /v1/tools/available` endpoint** | API Endpoints | Lists available MCP servers on the system. Requires runtime detection of installed MCP servers. V1 uses bundles.json as the source of truth. |
| **`list_available_tools()` SDK method** | SDK & CLI | Corresponds to the deferred `/v1/tools/available` endpoint. |
| **`GET /v1/agents/{id}/conversations/{session}` endpoint** | API Endpoints | Retrieve messages for a specific conversation session. Requires session-indexed memory queries. V1 lists conversations; full message retrieval deferred. |
| **Live MCP server connections** | MCP Tool System | Tool execution returns placeholder results. Actual MCP server subprocess management and `tools/list` + `tools/call` routing deferred to V2. |
| **OpenAI and Ollama providers** | LLM Provider Abstraction | Only ClaudeProvider built in V1. Adding OpenAI/Ollama providers is straightforward following the same protocol pattern. |
| **Docker container MCP servers** | Container Isolation | MCP servers run in-process for V1. Running them inside Docker containers requires additional plumbing. |
| **Alternative entry (describe agent in one sentence)** | Agent Creation Wizard | Chat-like interface for agent creation is a UX enhancement. V1 uses the 4-step wizard. |
| **Idle timeout auto-stop** | Resource Management | Auto-stop after 30min inactivity requires a background timer per runtime. Will add alongside resource management improvements. |
| **Max agents per org limit** | Resource Management | Enforcement at registration time. Simple to add but deferred to keep V1 scope focused. |
| **API key encryption at rest** | Security | Per-agent API key overrides stored encrypted. V1 uses env vars only. |
