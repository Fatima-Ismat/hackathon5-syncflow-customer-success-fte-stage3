"""
workers/metrics_collector.py
SyncFlow Customer Success Digital FTE — Stage 3

Kafka consumer worker that collects agent metrics events and aggregates them.
Reads from fte.metrics and fte.escalations topics.

Can run standalone or alongside message_processor.py.
"""

import sys
import os
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logger = logging.getLogger("syncflow.metrics_collector")

_stop_event = threading.Event()

# In-memory metrics accumulator (ring buffer per channel)
_metrics_store: Dict[str, List[dict]] = defaultdict(list)
_escalation_store: List[dict] = []
_store_lock = threading.Lock()
_MAX_EVENTS = 5000


# ─────────────────────────────────────────────────────────────────────────────
# Event Handlers
# ─────────────────────────────────────────────────────────────────────────────

def handle_metrics_event(event: dict):
    """Process a metrics event from the fte.metrics topic."""
    channel = event.get("channel", "unknown")
    with _store_lock:
        _metrics_store[channel].append(event)
        # Trim to max size
        if len(_metrics_store[channel]) > _MAX_EVENTS:
            _metrics_store[channel] = _metrics_store[channel][-_MAX_EVENTS:]
    logger.debug("Metrics event stored: channel=%s sentiment=%s escalated=%s",
                 channel, event.get("sentiment"), event.get("escalated"))


def handle_escalation_event(event: dict):
    """Process an escalation event from the fte.escalations topic."""
    with _store_lock:
        _escalation_store.append(event)
        if len(_escalation_store) > _MAX_EVENTS:
            _escalation_store[:] = _escalation_store[-_MAX_EVENTS:]
    logger.info("Escalation event: ticket=%s reason=%s queue=%s",
                event.get("ticket_ref"), event.get("escalation_reason"), event.get("escalation_queue"))


# ─────────────────────────────────────────────────────────────────────────────
# Aggregation
# ─────────────────────────────────────────────────────────────────────────────

def get_aggregated_metrics(hours: int = 24) -> dict:
    """
    Aggregate metrics from collected events.

    Returns summary including:
    - Total events by channel
    - Escalation rate
    - Average confidence
    - Sentiment breakdown
    - Processing time percentiles
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    since_iso = since.isoformat() + "Z"

    with _store_lock:
        all_events = []
        channel_breakdown = {}

        for channel, events in _metrics_store.items():
            recent = [e for e in events if e.get("timestamp", "") >= since_iso]
            if not recent:
                continue
            confidences = [e.get("confidence", 0) for e in recent if e.get("confidence")]
            sentiments = [e.get("sentiment", "neutral") for e in recent]
            escalated = sum(1 for e in recent if e.get("escalated"))
            processing = [e.get("processing_ms", 0) for e in recent if e.get("processing_ms")]

            channel_breakdown[channel] = {
                "total": len(recent),
                "escalated": escalated,
                "escalation_rate": round(escalated / max(len(recent), 1), 3),
                "avg_confidence": round(sum(confidences) / max(len(confidences), 1), 3),
                "avg_processing_ms": round(sum(processing) / max(len(processing), 1), 1),
                "sentiment_breakdown": _count_sentiments(sentiments),
            }
            all_events.extend(recent)

        escalations_recent = [
            e for e in _escalation_store
            if e.get("timestamp", "") >= since_iso
        ]

    total = len(all_events)
    if total == 0:
        return {
            "window_hours": hours,
            "total_events": 0,
            "channels": {},
            "escalations": [],
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }

    all_confidences = [e.get("confidence", 0) for e in all_events if e.get("confidence")]
    all_sentiments = [e.get("sentiment", "neutral") for e in all_events]
    all_escalated = sum(1 for e in all_events if e.get("escalated"))

    return {
        "window_hours": hours,
        "total_events": total,
        "escalation_rate": round(all_escalated / max(total, 1), 3),
        "avg_confidence": round(sum(all_confidences) / max(len(all_confidences), 1), 3),
        "sentiment_breakdown": _count_sentiments(all_sentiments),
        "channels": channel_breakdown,
        "recent_escalations": escalations_recent[-10:],
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def _count_sentiments(sentiments: list) -> dict:
    counts = defaultdict(int)
    for s in sentiments:
        counts[s or "neutral"] += 1
    total = max(len(sentiments), 1)
    return {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in counts.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Kafka Consumer
# ─────────────────────────────────────────────────────────────────────────────

def _run_kafka_consumer():
    from confluent_kafka import Consumer
    from kafka_client import TOPICS
    import os

    conf = {
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "group.id": "syncflow-metrics-collector",
        "auto.offset.reset": "latest",
        "enable.auto.commit": True,
    }
    security = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
    if security == "SASL_SSL":
        conf.update({
            "security.protocol": "SASL_SSL",
            "sasl.mechanism": "PLAIN",
            "sasl.username": os.getenv("KAFKA_SASL_USERNAME", ""),
            "sasl.password": os.getenv("KAFKA_SASL_PASSWORD", ""),
        })

    consumer = Consumer(conf)
    consumer.subscribe([TOPICS["METRICS"], TOPICS["ESCALATIONS"]])
    logger.info("Metrics collector consumer started")

    try:
        while not _stop_event.is_set():
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                continue
            try:
                event = json.loads(msg.value().decode("utf-8"))
                topic = msg.topic()
                if topic == TOPICS["METRICS"]:
                    handle_metrics_event(event)
                elif topic == TOPICS["ESCALATIONS"]:
                    handle_escalation_event(event)
            except Exception as e:
                logger.error("Metrics consumer error: %s", e)
    finally:
        consumer.close()


def _run_mock_consumer():
    """Subscribe to mock broker events."""
    from kafka_client import _mock_broker, TOPICS

    _mock_broker.subscribe(TOPICS["METRICS"], lambda t, e: handle_metrics_event(e))
    _mock_broker.subscribe(TOPICS["ESCALATIONS"], lambda t, e: handle_escalation_event(e))
    logger.info("Metrics collector running in mock mode")

    while not _stop_event.is_set():
        time.sleep(1.0)


def run_collector():
    """Start the metrics collector worker."""
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
    mock_mode = os.getenv("KAFKA_MOCK_MODE", "true").lower() == "true"

    if not mock_mode and bootstrap:
        try:
            _run_kafka_consumer()
            return
        except (ImportError, Exception) as e:
            logger.warning("Kafka collector fallback to mock: %s", e)

    _run_mock_consumer()


def start_collector_thread() -> threading.Thread:
    """Start metrics collector in a background thread."""
    t = threading.Thread(target=run_collector, daemon=True, name="metrics-collector")
    t.start()
    logger.info("Metrics collector thread started")
    return t


def stop_collector():
    _stop_event.set()


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import signal

    def _sig(sig, frame):
        stop_collector()

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    logger.info("Starting SyncFlow Metrics Collector")
    run_collector()
