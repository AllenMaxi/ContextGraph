from __future__ import annotations

from contextgraph.config import Settings
from contextgraph.demo import seed_dashboard_demo
from contextgraph.service import ContextGraphService
from contextgraph.web import create_app


def main() -> None:
    host = "127.0.0.1"
    port = 8000
    base_url = f"http://{host}:{port}"
    service = ContextGraphService(app_settings=Settings(enable_payments=True, enable_claim_expiry_sweeps=False))

    demo = seed_dashboard_demo(service, base_url=base_url)

    print("ContextGraph dashboard demo is ready.")
    print(f"Open: {demo.base_url}/console")
    print()
    print("Use these API keys in the console login screen:")
    print(f"- procurement-bot (same-org feed): {demo.procurement_api_key}")
    print(f"- globex-market-bot (shared + locked feed): {demo.globex_api_key}")
    print(f"- research-bot (source agent): {demo.research_api_key}")
    print()
    print("Recommended recording order:")
    for step in demo.recording_steps:
        print(f"- {step}")
    print()
    print("Seeded memory IDs:")
    print(f"- internal same-org: {demo.internal_memory_id}")
    print(f"- shared with globex: {demo.shared_memory_id}")
    print(f"- published free: {demo.published_memory_id}")
    print(f"- published paid: {demo.paid_memory_id}")
    print()
    print("Press Ctrl+C to stop the server.")

    try:
        import uvicorn
    except ModuleNotFoundError:
        print()
        print('Install server extras first: pip install -e ".[server,dev]"')
        service.close()
        return

    app = create_app(service)
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
