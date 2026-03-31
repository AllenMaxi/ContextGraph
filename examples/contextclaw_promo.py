from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any


@lru_cache(maxsize=1)
def _contextclaw() -> SimpleNamespace:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "contextclaw"))
    try:
        from contextclaw.config.agent_config import AgentConfig
        from contextclaw.providers.protocol import LLMResponse, ToolCall
        from contextclaw.runner import AgentRunner
        from contextclaw.runtime import create_tools
        from contextclaw.sandbox.policy import PolicyEngine
        from contextclaw.sandbox.process import ProcessSandbox
        from contextclaw.tools.manager import ToolManager
    except ModuleNotFoundError as exc:  # pragma: no cover - example guard
        raise SystemExit(
            "The ContextClaw promo example requires the local `contextclaw` package in this repository checkout."
        ) from exc

    return SimpleNamespace(
        AgentConfig=AgentConfig,
        AgentRunner=AgentRunner,
        LLMResponse=LLMResponse,
        PolicyEngine=PolicyEngine,
        ProcessSandbox=ProcessSandbox,
        ToolCall=ToolCall,
        ToolManager=ToolManager,
        create_tools=create_tools,
    )


class ScriptedProvider:
    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)

    def complete(self, messages: list[object], tools: list[object], system: str = "") -> object:
        if self._responses:
            return self._responses.pop(0)
        return _contextclaw().LLMResponse(content="Done.")


class FakeKnowledge:
    def __init__(self) -> None:
        self.auto_recall = True
        self.agent_id = "agt_promo"
        self.stored: list[str] = []

    def recall(self, query: str) -> list[dict]:
        return [{"content": "Last launch video performed best with short feature hooks."}]

    def store(self, content: str) -> None:
        self.stored.append(content)

    def summarize_and_store(self, conversation_context: str, provider, agent_name: str) -> list[dict]:
        summary = f"{agent_name} summary: {conversation_context.splitlines()[-1]}"
        self.stored.append(summary)
        return [{"content": summary}]


def print_header(title: str) -> None:
    print(f"\n========== {title} ==========")


def print_agent_status(name: str, config: Any, *, linked: bool = False) -> None:
    print(f"$ cclaw status {name}")
    print(f"Agent: {config.name}")
    print(f"Provider: {config.provider}")
    print(f"Sandbox: {config.sandbox_type}")
    print(f"Tools: {', '.join(config.tools)}")
    print(f"ContextGraph: {'linked' if linked else 'not linked'}")
    if config.mcp_servers_path:
        print(f"MCP Registry: {config.mcp_servers_path.name}")
    if config.subagents_path:
        print(f"Subagents: {config.subagents_path.name}")
    if config.checkpoint_path:
        print(f"Checkpoint: {config.checkpoint_path.relative_to(config.workspace)}")


def write_mock_mcp_server(workspace: Path) -> Path:
    script = workspace / "mock_mcp_server.py"
    script.write_text(
        """
import json
import sys

for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    if method == "initialize":
        print(json.dumps({
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "mock", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            },
        }), flush=True)
    elif method == "tools/list":
        print(json.dumps({
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo a demo status line",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}},
                            "required": ["text"],
                        },
                    }
                ]
            },
        }), flush=True)
    elif method == "tools/call":
        text = message["params"]["arguments"]["text"]
        print(json.dumps({
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {"content": [{"type": "text", "text": text}]},
        }), flush=True)
""",
        encoding="utf-8",
    )
    return script


async def run_orchestrator_agent(base: Path) -> None:
    contextclaw = _contextclaw()
    AgentConfig = contextclaw.AgentConfig
    AgentRunner = contextclaw.AgentRunner
    LLMResponse = contextclaw.LLMResponse
    ToolCall = contextclaw.ToolCall
    create_tools = contextclaw.create_tools

    print_header("Orchestrator Agent")
    workspace = base / "promo-orchestrator"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "notes.txt").write_text(
        "ContextClaw runs agents. ContextGraph shares durable memory.\n",
        encoding="utf-8",
    )
    subagents_dir = workspace / "subagents"
    child_dir = subagents_dir / "research-sub"
    child_dir.mkdir(parents=True, exist_ok=True)
    (child_dir / "config.yaml").write_text(
        "name: research-sub\nprovider: openai\nsandbox_type: process\ntools: planning\n",
        encoding="utf-8",
    )
    (child_dir / "SOUL.md").write_text(
        "---\nname: research-sub\nrole: research\ndescription: Specialized launch research agent\n---\nResearch launch positioning with concise answers.\n",
        encoding="utf-8",
    )
    mcp_script = write_mock_mcp_server(workspace)
    (workspace / "mcp_servers.json").write_text(
        json.dumps({"servers": [{"name": "demo", "command": [sys.executable, str(mcp_script)]}]}),
        encoding="utf-8",
    )
    config = AgentConfig(
        name="promo-orchestrator",
        workspace=workspace,
        provider="openai",
        tools=["filesystem", "planning"],
        mcp_servers_path=workspace / "mcp_servers.json",
        subagents_path=subagents_dir,
        checkpoint_path=workspace / ".contextclaw" / "session.json",
    )
    parent_provider = ScriptedProvider(
        [
            LLMResponse(
                content="I will recall launch context, inspect the local note, delegate research, and confirm the MCP connection.",
                tool_calls=[
                    ToolCall(id="tc1", name="read_file", arguments={"path": "notes.txt"}),
                    ToolCall(
                        id="tc_task",
                        name="task",
                        arguments={
                            "subagent": "research-sub",
                            "prompt": "Draft one concise positioning line for the launch.",
                        },
                    ),
                    ToolCall(
                        id="tc_mcp",
                        name="mcp__demo__echo",
                        arguments={"text": "MCP registry connected"},
                    ),
                    ToolCall(
                        id="tc2",
                        name="write_todos",
                        arguments={
                            "heading": "Promo Plan",
                            "items": [
                                "Lead with the pain: agents forget context",
                                "Show ContextClaw plus ContextGraph in one story",
                            ],
                        },
                    ),
                    ToolCall(id="tc3", name="read_todos", arguments={}),
                ],
            ),
            LLMResponse(
                content=(
                    "The note says: ContextClaw runs agents. ContextGraph shares durable memory. "
                    "A delegated subagent wrote the launch line, the MCP tool confirmed registry access, "
                    "and I saved plus reloaded a two-step promo plan."
                )
            ),
        ]
    )
    child_provider = ScriptedProvider(
        [LLMResponse(content="ContextClaw runs the agents. ContextGraph shares the memory.")]
    )

    def provider_factory(subconfig: Any):
        if subconfig.name == "research-sub":
            return child_provider
        raise RuntimeError(f"Unexpected delegated agent: {subconfig.name}")

    tools = await create_tools(config)
    knowledge = FakeKnowledge()
    runner = AgentRunner(
        config=config,
        provider=parent_provider,
        tools=tools,
        knowledge=knowledge,
        provider_factory=provider_factory,
        min_call_interval=0,
    )
    print_agent_status(config.name, config, linked=True)
    print("$ cclaw chat promo-orchestrator")
    print("You: Build a promo angle for launch.")
    async for event in runner.run("Build a promo angle for launch."):
        if event.type == "knowledge_recalled":
            print("[ContextGraph] recalled: short feature hooks performed best")
        elif event.type == "tool_call":
            print(f"[tool] {event.data['name']} {event.data['arguments']}")
        elif event.type == "tool_result":
            print(f"[result] {event.data['result']}")
        elif event.type == "text":
            print(f"Assistant: {event.data['content']}")
    stored = await runner.close_session()
    if stored:
        print(f"[ContextGraph] stored {len(stored)} memory summary")
    resumed = AgentRunner(
        config=config,
        provider=ScriptedProvider([LLMResponse(content="Resume confirmed.")]),
        tools=await create_tools(config),
        knowledge=knowledge,
        provider_factory=provider_factory,
        min_call_interval=0,
    )
    print(f"[checkpoint] resumed session from {config.checkpoint_path.relative_to(config.workspace)}")
    await resumed.tools.stop_all()
    await tools.stop_all()


async def run_coder_agent(base: Path) -> None:
    contextclaw = _contextclaw()
    AgentConfig = contextclaw.AgentConfig
    AgentRunner = contextclaw.AgentRunner
    LLMResponse = contextclaw.LLMResponse
    ProcessSandbox = contextclaw.ProcessSandbox
    ToolCall = contextclaw.ToolCall
    ToolManager = contextclaw.ToolManager

    print_header("Coder Agent")
    workspace = base / "promo-coder"
    workspace.mkdir(parents=True, exist_ok=True)
    config = AgentConfig(
        name="promo-coder",
        workspace=workspace,
        provider="openai",
        tools=["shell", "planning"],
    )
    provider = ScriptedProvider(
        [
            LLMResponse(
                content="I will run a quick sandboxed smoke check.",
                tool_calls=[ToolCall(id="tc3", name="execute", arguments={"command": "printf 'smoke-test-ready\\n'"})],
            ),
            LLMResponse(content="The sandbox responded with smoke-test-ready."),
        ]
    )
    tools = ToolManager()
    tools.register_bundle("shell")
    tools.register_bundle("planning")
    sandbox = ProcessSandbox(workspace=workspace)
    runner = AgentRunner(
        config=config,
        provider=provider,
        tools=tools,
        sandbox=sandbox,
        min_call_interval=0,
    )
    print_agent_status(config.name, config)
    print("$ cclaw chat promo-coder")
    print("You: Check whether the runtime is alive.")
    async for event in runner.run("Check whether the runtime is alive."):
        if event.type == "tool_call":
            print(f"[tool] {event.data['name']} {event.data['arguments']}")
        elif event.type == "tool_result":
            print(f"[result] {event.data['result'].strip()}")
        elif event.type == "text":
            print(f"Assistant: {event.data['content']}")


async def run_memory_agent(base: Path) -> None:
    contextclaw = _contextclaw()
    AgentConfig = contextclaw.AgentConfig
    AgentRunner = contextclaw.AgentRunner
    LLMResponse = contextclaw.LLMResponse
    PolicyEngine = contextclaw.PolicyEngine
    ToolCall = contextclaw.ToolCall
    ToolManager = contextclaw.ToolManager

    print_header("Memory Agent")
    workspace = base / "promo-memory"
    workspace.mkdir(parents=True, exist_ok=True)
    config = AgentConfig(
        name="promo-memory",
        workspace=workspace,
        provider="openai",
        tools=["filesystem", "web", "shell"],
    )
    policy = PolicyEngine.from_text(
        """\
permissions:
  tools:
    auto_approve:
      - filesystem_read
      - filesystem_list
      - web_search
      - web_fetch
    blocked:
      - shell_execute
"""
    )
    provider = ScriptedProvider(
        [
            LLMResponse(
                content="I will try to run shell, but policy should stop me.",
                tool_calls=[ToolCall(id="tc4", name="execute", arguments={"command": "pwd"})],
            ),
            LLMResponse(
                content="Shell execution was blocked, which keeps this agent focused on memory and governance."
            ),
        ]
    )
    tools = ToolManager()
    tools.register_bundle("filesystem")
    tools.register_bundle("web")
    tools.register_bundle("shell")
    runner = AgentRunner(
        config=config,
        provider=provider,
        tools=tools,
        policy=policy,
        min_call_interval=0,
    )
    print_agent_status(config.name, config, linked=True)
    print("$ cclaw chat promo-memory")
    print("You: Run a shell command.")
    async for event in runner.run("Run a shell command."):
        if event.type == "tool_call":
            print(f"[tool] {event.data['name']} {event.data['arguments']}")
        elif event.type == "tool_result":
            print(f"[result] {event.data['result']}")
        elif event.type == "text":
            print(f"Assistant: {event.data['content']}")


async def main() -> None:
    print("ContextClaw promo demo")
    print("ContextClaw runs the agents. ContextGraph shares the memory.")
    with tempfile.TemporaryDirectory(prefix="contextclaw_promo_") as tmp:
        base = Path(tmp)
        print(f"workspace: {base}")
        await run_orchestrator_agent(base)
        await run_coder_agent(base)
        await run_memory_agent(base)
    print("\n========== Summary ==========")
    print("Orchestrator agent: memory, MCP tools, task delegation, and checkpoints")
    print("Coder agent: sandboxed shell execution")
    print("Memory agent: role-specific guardrails")
    print("ContextClaw + ContextGraph = agents that work together instead of forgetting every session")


if __name__ == "__main__":
    asyncio.run(main())
