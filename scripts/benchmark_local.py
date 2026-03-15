from __future__ import annotations

import argparse
import platform
import statistics
import sys
import time
from dataclasses import dataclass

from contextgraph import ContextGraphService
from contextgraph.config import Settings


@dataclass(slots=True)
class SampleSet:
    name: str
    values_ms: list[float]

    @property
    def avg(self) -> float:
        return statistics.fmean(self.values_ms)

    @property
    def p50(self) -> float:
        return statistics.median(self.values_ms)

    @property
    def p95(self) -> float:
        ordered = sorted(self.values_ms)
        idx = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
        return ordered[idx]

    @property
    def max(self) -> float:
        return max(self.values_ms)


def timed_ms(fn) -> float:
    started = time.perf_counter()
    fn()
    return (time.perf_counter() - started) * 1000.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark local ContextGraph hot paths.")
    parser.add_argument("--seed-memories", type=int, default=300)
    parser.add_argument("--store-iterations", type=int, default=40)
    parser.add_argument("--recall-iterations", type=int, default=80)
    parser.add_argument("--feed-iterations", type=int, default=80)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    service = ContextGraphService(app_settings=Settings(enable_payments=True, enable_claim_expiry_sweeps=False))
    try:
        research = service.register_agent(
            "research-bot",
            "acme",
            ["research", "supply-chain"],
            default_visibility="org",
        )
        operator = service.register_agent("ops-bot", "acme", ["ops"])
        market = service.register_agent("globex-market-bot", "globex", ["market"])

        service.follow(operator.agent_id, "agent", research.agent_id)
        service.follow(operator.agent_id, "org", "acme")
        service.follow(market.agent_id, "topic", "semiconductor")
        service.follow(market.agent_id, "agent", research.agent_id)

        for idx in range(args.seed_memories):
            if idx % 3 == 0:
                service.store_memory(
                    research.agent_id,
                    f"Semiconductor supplier note {idx}: TSMC lead times changed for packaging lane {idx % 7}.",
                )
            elif idx % 3 == 1:
                service.store_memory(
                    research.agent_id,
                    f"Partner memory {idx}: Acme shares constrained semiconductor packaging capacity update with Globex.",
                    visibility="shared",
                    access_list=["globex"],
                )
            else:
                service.store_memory(
                    research.agent_id,
                    f"Published premium analysis {idx}: semiconductor pricing, packaging, and order shifts.",
                    visibility="published",
                    price=0.002,
                )

        service.recall(operator.agent_id, "semiconductor lead times", limit=5)
        service.get_feed(operator.agent_id)
        service.get_feed(market.agent_id)

        store_samples = [
            timed_ms(
                lambda idx=idx: service.store_memory(
                    research.agent_id,
                    f"Benchmark store memory {idx}: semiconductor order reallocation signal for fab lane {idx % 5}.",
                )
            )
            for idx in range(args.store_iterations)
        ]

        recall_samples = [
            timed_ms(lambda: service.recall(operator.agent_id, "semiconductor lead times", limit=5))
            for _ in range(args.recall_iterations)
        ]

        feed_samples = [
            timed_ms(lambda: service.get_feed(market.agent_id, limit=20)) for _ in range(args.feed_iterations)
        ]

        sample_sets = [
            SampleSet("store_memory", store_samples),
            SampleSet("recall", recall_samples),
            SampleSet("get_feed", feed_samples),
        ]

        print("# ContextGraph local benchmark")
        print()
        print(f"- python: {sys.version.split()[0]}")
        print(f"- platform: {platform.platform()}")
        print("- backend: in-memory repository")
        print("- claim ranking: BM25 + freshness/confidence modifiers")
        print(f"- seeded memories: {args.seed_memories}")
        print()
        print("| Path | Avg (ms) | P50 (ms) | P95 (ms) | Max (ms) |")
        print("| --- | ---: | ---: | ---: | ---: |")
        for sample in sample_sets:
            print(f"| `{sample.name}` | {sample.avg:.2f} | {sample.p50:.2f} | {sample.p95:.2f} | {sample.max:.2f} |")
    finally:
        service.close()


if __name__ == "__main__":
    main()
