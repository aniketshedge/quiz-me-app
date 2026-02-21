from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _month_key(timestamp: datetime) -> str:
    return timestamp.strftime("%Y-%m")


def _empty_metric_bucket() -> dict[str, Any]:
    return {"attempts": 0, "success": 0, "error": 0, "cost_usd": 0.0}


def _empty_period_snapshot() -> dict[str, Any]:
    return {
        "totals": _empty_metric_bucket(),
        "providers": {},
        "models": {},
        "tasks": {},
        "categories": {},
        "provider_task": {},
    }


def _empty_counter_snapshot() -> dict[str, Any]:
    now = _utc_now_iso()
    payload = _empty_period_snapshot()
    payload["meta"] = {
        "version": 2,
        "created_at": now,
        "updated_at": now,
    }
    payload["monthly"] = {}
    return payload


class LLMTelemetryStore:
    def __init__(self, enabled: bool, base_dir: str) -> None:
        self.enabled = enabled
        self.base_dir = Path(base_dir)
        self.events_path = self.base_dir / "llm_calls.jsonl"
        self.counters_path = self.base_dir / "llm_counters.json"
        self._lock = threading.Lock()

        if self.enabled:
            self._ensure_files()

    def _ensure_files(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if not self.events_path.exists():
            self.events_path.touch()
        if not self.counters_path.exists():
            self._write_counters(_empty_counter_snapshot())

    def _read_counters(self) -> dict[str, Any]:
        try:
            return json.loads(self.counters_path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            # Keep service running even if file is missing/corrupt.
            return _empty_counter_snapshot()

    def _write_counters(self, payload: dict[str, Any]) -> None:
        tmp_path = self.counters_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        tmp_path.replace(self.counters_path)

    @staticmethod
    def _inc(bucket: dict[str, Any], key: str) -> None:
        bucket[key] = int(bucket.get(key, 0)) + 1

    @staticmethod
    def _add_cost(bucket: dict[str, Any], cost_usd: float | None) -> None:
        if cost_usd is None:
            return
        bucket["cost_usd"] = round(float(bucket.get("cost_usd", 0.0)) + float(cost_usd), 8)

    @staticmethod
    def _metric_bucket(container: dict[str, Any], key: str) -> dict[str, Any]:
        bucket = container.setdefault(key, {})
        bucket.setdefault("attempts", 0)
        bucket.setdefault("success", 0)
        bucket.setdefault("error", 0)
        bucket.setdefault("cost_usd", 0.0)
        return bucket

    def _bump_metric(self, bucket: dict[str, Any], outcome: str, cost_usd: float | None) -> None:
        self._inc(bucket, "attempts")
        self._inc(bucket, outcome)
        self._add_cost(bucket, cost_usd)

    def _bump_snapshot(
        self,
        snapshot: dict[str, Any],
        event: dict[str, Any],
    ) -> None:
        outcome = event["outcome"]
        provider = event["provider"]
        model = event["model"]
        task = event["task"]
        category = event["category"] or "unknown"
        cost_usd = event.get("cost_usd")

        totals = self._metric_bucket(snapshot, "totals")
        self._bump_metric(totals, outcome, cost_usd)

        providers = snapshot.setdefault("providers", {})
        provider_bucket = self._metric_bucket(providers, provider)
        self._bump_metric(provider_bucket, outcome, cost_usd)

        models = snapshot.setdefault("models", {})
        model_bucket = self._metric_bucket(models, model)
        self._bump_metric(model_bucket, outcome, cost_usd)

        tasks = snapshot.setdefault("tasks", {})
        task_bucket = self._metric_bucket(tasks, task)
        self._bump_metric(task_bucket, outcome, cost_usd)

        categories = snapshot.setdefault("categories", {})
        category_bucket = self._metric_bucket(categories, category)
        self._bump_metric(category_bucket, outcome, cost_usd)

        provider_task = snapshot.setdefault("provider_task", {})
        by_provider = provider_task.setdefault(provider, {})
        pair_bucket = self._metric_bucket(by_provider, task)
        self._bump_metric(pair_bucket, outcome, cost_usd)

    def record_attempt(
        self,
        *,
        operation: str,
        task: str,
        provider: str,
        model: str,
        attempt: int,
        outcome: str,
        category: str,
        duration_ms: int,
        error_message: str | None = None,
        cost_usd: float | None = None,
    ) -> None:
        if not self.enabled:
            return

        timestamp = _utc_now()
        ts_iso = timestamp.isoformat()
        month = _month_key(timestamp)
        normalized_cost = None if cost_usd is None else float(cost_usd)

        event = {
            "ts": ts_iso,
            "month": month,
            "operation": operation,
            "task": task,
            "provider": provider,
            "model": model,
            "attempt": attempt,
            "outcome": outcome,
            "category": category,
            "duration_ms": duration_ms,
            "error_message": error_message,
            "cost_usd": normalized_cost,
        }

        with self._lock:
            self._ensure_files()
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, sort_keys=True) + "\n")

            counters = self._read_counters()
            self._bump_snapshot(counters, event)

            monthly = counters.setdefault("monthly", {})
            month_snapshot = monthly.setdefault(month, _empty_period_snapshot())
            self._bump_snapshot(month_snapshot, event)

            meta = counters.setdefault("meta", {})
            if "created_at" not in meta:
                meta["created_at"] = ts_iso
            meta["updated_at"] = ts_iso
            meta["version"] = max(2, int(meta.get("version", 2)))

            self._write_counters(counters)

    def measure_and_record(
        self,
        *,
        operation: str,
        task: str,
        provider: str,
        model: str,
        attempt: int,
        started_at: float,
        outcome: str,
        category: str,
        error_message: str | None = None,
        cost_usd: float | None = None,
    ) -> None:
        duration_ms = int((perf_counter() - started_at) * 1000)
        self.record_attempt(
            operation=operation,
            task=task,
            provider=provider,
            model=model,
            attempt=attempt,
            outcome=outcome,
            category=category,
            duration_ms=duration_ms,
            error_message=error_message,
            cost_usd=cost_usd,
        )
