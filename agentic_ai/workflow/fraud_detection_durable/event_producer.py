"""
Layer 1: Ambient Event Producer & Anomaly Detection.

Generates simulated customer telemetry events and applies fast rule-based
anomaly detection. When an anomaly is detected, it auto-submits an alert
to the backend's /api/workflow/start endpoint, triggering the Layer 2
durable investigation workflow.

This module runs as an asyncio background task inside the FastAPI backend.
It does NOT use LLMs — rules are pure Python for speed and cost efficiency.

Events are broadcast via SSE (Server-Sent Events) to the React UI's
Live Feed panel.
"""

import asyncio
import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Customer Profiles (baseline behavior for anomaly detection)
# ============================================================================

COUNTRIES = ["USA", "Canada", "UK", "Germany", "France", "Japan", "Australia", "Brazil", "India", "Russia"]
NORMAL_COUNTRIES = {
    1: ["USA", "Canada"],
    2: ["USA", "UK"],
    3: ["Germany", "France"],
    4: ["Japan", "Australia"],
    5: ["USA", "India"],
}

CUSTOMER_PROFILES = {
    1: {"name": "Alice Johnson", "avg_transaction": 85.0, "avg_daily_data_gb": 1.2, "subscription_id": 5},
    2: {"name": "Bob Smith", "avg_transaction": 120.0, "avg_daily_data_gb": 2.5, "subscription_id": 8},
    3: {"name": "Carlos Rivera", "avg_transaction": 200.0, "avg_daily_data_gb": 0.8, "subscription_id": 12},
    4: {"name": "Diana Chen", "avg_transaction": 55.0, "avg_daily_data_gb": 3.0, "subscription_id": 3},
    5: {"name": "Ethan Patel", "avg_transaction": 150.0, "avg_daily_data_gb": 1.8, "subscription_id": 7},
}

EVENT_TYPES = ["login", "transaction", "data_usage", "api_call", "auth_failure"]


# ============================================================================
# Data structures
# ============================================================================

@dataclass
class TelemetryEvent:
    """A single telemetry event from the simulated environment."""
    id: str
    timestamp: str
    customer_id: int
    customer_name: str
    event_type: str
    details: dict
    is_anomaly: bool = False
    anomaly_rule: str = ""
    alert_triggered: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "event_type": self.event_type,
            "details": self.details,
            "is_anomaly": self.is_anomaly,
            "anomaly_rule": self.anomaly_rule,
            "alert_triggered": self.alert_triggered,
        }


# ============================================================================
# Event Producer
# ============================================================================

class EventProducer:
    """Generates telemetry events and detects anomalies using fast rules.

    Maintains per-customer sliding windows for rule evaluation.
    Broadcasts events to registered SSE subscribers.
    """

    def __init__(
        self,
        interval_seconds: float = 3.0,
        anomaly_probability: float = 0.08,
    ):
        self.interval = interval_seconds
        self.anomaly_probability = anomaly_probability
        self._running = False
        self._event_counter = 0
        self._subscribers: list[asyncio.Queue] = []

        # Per-customer state for rule evaluation
        self._recent_logins: dict[int, deque] = {
            cid: deque(maxlen=10) for cid in CUSTOMER_PROFILES
        }
        self._recent_transactions: dict[int, deque] = {
            cid: deque(maxlen=20) for cid in CUSTOMER_PROFILES
        }
        self._recent_auth_failures: dict[int, deque] = {
            cid: deque(maxlen=10) for cid in CUSTOMER_PROFILES
        }

        # Track which alerts we've fired to avoid duplicates
        self._active_alerts: set[str] = set()

        # Callback for auto-submitting alerts
        self._alert_callback: Any = None

    def set_alert_callback(self, callback):
        """Set the async callback for when an anomaly triggers an alert."""
        self._alert_callback = callback

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to the event stream. Returns a queue to read events from."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from the event stream."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def _broadcast(self, event: TelemetryEvent):
        """Send event to all SSE subscribers."""
        dead_queues = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                dead_queues.append(queue)
        for q in dead_queues:
            self._subscribers.remove(q)

    # ========================================================================
    # Event Generation
    # ========================================================================

    def _generate_normal_event(self, customer_id: int) -> TelemetryEvent:
        """Generate a normal (non-anomalous) telemetry event."""
        profile = CUSTOMER_PROFILES[customer_id]
        event_type = random.choice(EVENT_TYPES)
        self._event_counter += 1
        now = datetime.now()

        if event_type == "login":
            country = random.choice(NORMAL_COUNTRIES[customer_id])
            details = {"country": country, "ip": f"192.168.{random.randint(1,255)}.{random.randint(1,255)}", "success": True}
        elif event_type == "transaction":
            amount = round(random.gauss(profile["avg_transaction"], profile["avg_transaction"] * 0.3), 2)
            amount = max(5.0, amount)  # No negative/tiny amounts
            details = {"amount": amount, "currency": "USD", "merchant": random.choice(["Amazon", "Walmart", "Target", "BestBuy", "Costco"])}
        elif event_type == "data_usage":
            gb = round(random.gauss(profile["avg_daily_data_gb"], profile["avg_daily_data_gb"] * 0.2), 2)
            gb = max(0.1, gb)
            details = {"gb_used": gb, "subscription_id": profile["subscription_id"]}
        elif event_type == "api_call":
            details = {"endpoint": random.choice(["/api/account", "/api/billing", "/api/usage", "/api/profile"]), "status_code": 200, "latency_ms": random.randint(50, 300)}
        else:  # auth_failure
            details = {"method": "password", "reason": "typo", "ip": f"10.0.{random.randint(1,255)}.{random.randint(1,255)}"}

        return TelemetryEvent(
            id=f"EVT-{self._event_counter:06d}",
            timestamp=now.isoformat(),
            customer_id=customer_id,
            customer_name=profile["name"],
            event_type=event_type,
            details=details,
        )

    def _generate_anomalous_event(self, customer_id: int) -> TelemetryEvent:
        """Generate an event that should trigger an anomaly rule."""
        profile = CUSTOMER_PROFILES[customer_id]
        self._event_counter += 1
        now = datetime.now()

        anomaly_type = random.choice(["multi_country_login", "spending_spike", "data_spike", "rapid_auth_failures"])

        if anomaly_type == "multi_country_login":
            # Login from unusual country
            unusual = [c for c in COUNTRIES if c not in NORMAL_COUNTRIES[customer_id]]
            country = random.choice(unusual)
            details = {"country": country, "ip": f"203.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}", "success": True}
            return TelemetryEvent(
                id=f"EVT-{self._event_counter:06d}",
                timestamp=now.isoformat(),
                customer_id=customer_id,
                customer_name=profile["name"],
                event_type="login",
                details=details,
            )

        elif anomaly_type == "spending_spike":
            # Transaction 4-8× the average
            multiplier = random.uniform(4.0, 8.0)
            amount = round(profile["avg_transaction"] * multiplier, 2)
            details = {"amount": amount, "currency": "USD", "merchant": random.choice(["LuxuryGoods.com", "HighEnd Electronics", "Crypto Exchange"])}
            return TelemetryEvent(
                id=f"EVT-{self._event_counter:06d}",
                timestamp=now.isoformat(),
                customer_id=customer_id,
                customer_name=profile["name"],
                event_type="transaction",
                details=details,
            )

        elif anomaly_type == "data_spike":
            # Data usage 5-10× the average
            multiplier = random.uniform(5.0, 10.0)
            gb = round(profile["avg_daily_data_gb"] * multiplier, 2)
            details = {"gb_used": gb, "subscription_id": profile["subscription_id"]}
            return TelemetryEvent(
                id=f"EVT-{self._event_counter:06d}",
                timestamp=now.isoformat(),
                customer_id=customer_id,
                customer_name=profile["name"],
                event_type="data_usage",
                details=details,
            )

        else:  # rapid_auth_failures
            details = {"method": "password", "reason": "invalid_credentials", "ip": f"185.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"}
            return TelemetryEvent(
                id=f"EVT-{self._event_counter:06d}",
                timestamp=now.isoformat(),
                customer_id=customer_id,
                customer_name=profile["name"],
                event_type="auth_failure",
                details=details,
            )

    # ========================================================================
    # Anomaly Detection Rules (fast Python, no LLM)
    # ========================================================================

    def _evaluate_rules(self, event: TelemetryEvent) -> tuple[bool, str]:
        """Evaluate anomaly detection rules against an event.

        Returns (is_anomaly, rule_name).
        """
        cid = event.customer_id
        profile = CUSTOMER_PROFILES[cid]

        # Rule 1: Multi-country login within 2 hours
        if event.event_type == "login" and event.details.get("success"):
            country = event.details.get("country", "")
            recent = self._recent_logins[cid]
            for prev in recent:
                prev_country = prev.get("country", "")
                prev_time = prev.get("time", 0)
                if prev_country and prev_country != country:
                    if time.time() - prev_time < 7200:  # 2 hours
                        return True, "multi_country_login"
            # Record this login
            recent.append({"country": country, "time": time.time()})

        # Rule 2: Transaction amount > 3× customer average
        if event.event_type == "transaction":
            amount = event.details.get("amount", 0)
            if amount > profile["avg_transaction"] * 3:
                return True, "spending_spike"
            self._recent_transactions[cid].append({"amount": amount, "time": time.time()})

        # Rule 3: Data usage > 4× daily average
        if event.event_type == "data_usage":
            gb = event.details.get("gb_used", 0)
            if gb > profile["avg_daily_data_gb"] * 4:
                return True, "data_usage_spike"

        # Rule 4: 3+ auth failures in 5 minutes
        if event.event_type == "auth_failure":
            recent_failures = self._recent_auth_failures[cid]
            recent_failures.append({"time": time.time()})
            # Count failures in last 5 minutes
            cutoff = time.time() - 300
            recent_count = sum(1 for f in recent_failures if f["time"] > cutoff)
            if recent_count >= 3:
                return True, "rapid_auth_failures"

        return False, ""

    def _make_alert_description(self, event: TelemetryEvent) -> str:
        """Build a human-readable alert description from an anomalous event."""
        if event.anomaly_rule == "multi_country_login":
            country = event.details.get("country", "unknown")
            recent = self._recent_logins[event.customer_id]
            prev_countries = [r["country"] for r in recent if r["country"] != country]
            prev = prev_countries[-1] if prev_countries else "unknown"
            return f"Login from {country} detected for customer {event.customer_id} ({event.customer_name}). Previous login was from {prev} within 2 hours. Possible credential compromise or account sharing."
        elif event.anomaly_rule == "spending_spike":
            amount = event.details.get("amount", 0)
            avg = CUSTOMER_PROFILES[event.customer_id]["avg_transaction"]
            return f"Transaction of ${amount:.2f} detected for customer {event.customer_id} ({event.customer_name}). This is {amount/avg:.1f}× their average of ${avg:.2f}. Possible unauthorized purchase."
        elif event.anomaly_rule == "data_usage_spike":
            gb = event.details.get("gb_used", 0)
            avg = CUSTOMER_PROFILES[event.customer_id]["avg_daily_data_gb"]
            return f"Data usage of {gb:.1f} GB detected for customer {event.customer_id} ({event.customer_name}). This is {gb/avg:.1f}× their daily average of {avg:.1f} GB. Possible data exfiltration or compromised device."
        elif event.anomaly_rule == "rapid_auth_failures":
            return f"Multiple authentication failures detected for customer {event.customer_id} ({event.customer_name}). 3+ failed attempts in 5 minutes from suspicious IP. Possible brute-force attack."
        return f"Anomaly detected for customer {event.customer_id}: {event.anomaly_rule}"

    # ========================================================================
    # Main Loop
    # ========================================================================

    async def run(self):
        """Main event production loop. Runs until stopped."""
        self._running = True
        logger.info(f"🔄 Event producer started (interval={self.interval}s, anomaly_prob={self.anomaly_probability})")

        # Generate a few normal events first before any anomalies
        warmup_count = 5
        event_count = 0

        while self._running:
            try:
                customer_id = random.choice(list(CUSTOMER_PROFILES.keys()))
                event_count += 1

                # After warmup, sometimes generate anomalous events
                if event_count > warmup_count and random.random() < self.anomaly_probability:
                    event = self._generate_anomalous_event(customer_id)
                else:
                    event = self._generate_normal_event(customer_id)

                # Run anomaly rules
                is_anomaly, rule = self._evaluate_rules(event)
                if is_anomaly:
                    event.is_anomaly = True
                    event.anomaly_rule = rule

                    # De-duplicate: don't fire the same rule for the same customer within 60s
                    dedup_key = f"{customer_id}-{rule}"
                    if dedup_key not in self._active_alerts:
                        self._active_alerts.add(dedup_key)
                        event.alert_triggered = True

                        logger.warning(
                            f"⚠️ ANOMALY DETECTED: {rule} for customer {customer_id} "
                            f"({CUSTOMER_PROFILES[customer_id]['name']}) — triggering investigation"
                        )

                        # Auto-submit alert to Layer 2
                        if self._alert_callback:
                            alert_type = rule
                            description = self._make_alert_description(event)
                            severity = "high" if rule in ("multi_country_login", "rapid_auth_failures") else "medium"

                            try:
                                await self._alert_callback(
                                    alert_id=f"AUTO-{event.id}",
                                    customer_id=customer_id,
                                    alert_type=alert_type,
                                    description=description,
                                    severity=severity,
                                )
                            except Exception as e:
                                logger.error(f"Failed to submit alert: {e}")

                        # Clear dedup after 60 seconds
                        asyncio.get_event_loop().call_later(
                            60.0, lambda k=dedup_key: self._active_alerts.discard(k)
                        )

                # Broadcast to SSE subscribers
                await self._broadcast(event)

                # Wait for next event
                jitter = random.uniform(-0.5, 0.5)
                await asyncio.sleep(max(0.5, self.interval + jitter))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event producer error: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info("Event producer stopped")

    def stop(self):
        """Stop the event production loop."""
        self._running = False
