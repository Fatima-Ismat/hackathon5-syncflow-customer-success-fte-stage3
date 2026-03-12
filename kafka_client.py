"""
kafka_client.py
SyncFlow Customer Success Digital FTE — Stage 3

Kafka event streaming client with graceful mock fallback for local development.

Topics:
  fte.tickets.incoming      New ticket created (inbound message processed)
  fte.email.inbound         Inbound email event
  fte.email.outbound        Outbound email dispatched
  fte.whatsapp.inbound      Inbound WhatsApp message
  fte.whatsapp.outbound     Outbound WhatsApp sent
  fte.metrics               Agent metrics events
  fte.escalations           Escalation events
  fte.dead-letter           Failed events for replay

Environment:
  KAFKA_BOOTSTRAP_SERVERS   e.g. localhost:9092 or pkc-xxxx.us-east-1.aws.confluent.cloud:9092
  KAFKA_SECURITY_PROTOCOL   SASL_SSL (for Confluent Cloud) or PLAINTEXT (local)
  KAFKA_SASL_USERNAME       Confluent Cloud API key
  KAFKA_SASL_PASSWORD       Confluent Cloud API secret
  KAFKA_MOCK_MODE           "true" to force mock mode regardless of bootstrap servers
"""

import os
import json
import logging
import threading
from datetime import datetime
from typing import Optional, Callable, Dict, Any
from collections import deque

logger = logging.getLogger("syncflow.kafka")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
KAFKA_SASL_USERNAME = os.getenv("KAFKA_SASL_USERNAME", "")
KAFKA_SASL_PASSWORD = os.getenv("KAFKA_SASL_PASSWORD", "")
KAFKA_MOCK_MODE = os.getenv("KAFKA_MOCK_MODE", "true").lower() == "true"
KAFKA_CLIENT_ID = os.getenv("KAFKA_CLIENT_ID", "syncflow-fte")

TOPICS = {
    "TICKETS_INCOMING": "fte.tickets.incoming",
    "EMAIL_INBOUND":    "fte.email.inbound",
    "EMAIL_OUTBOUND":   "fte.email.outbound",
    "WA_INBOUND":       "fte.whatsapp.inbound",
    "WA_OUTBOUND":      "fte.whatsapp.outbound",
    "METRICS":          "fte.metrics",
    "ESCALATIONS":      "fte.escalations",
    "DEAD_LETTER":      "fte.dead-letter",
}

# ─────────────────────────────────────────────────────────────────────────────
# Mock In-Memory Broker
# ─────────────────────────────────────────────────────────────────────────────

class _MockBroker:
    """
    Thread-safe in-memory event bus that mimics Kafka's topic/partition model.
    Used when real Kafka is unavailable (local dev, CI, Hugging Face).
    """

    def __init__(self, max_per_topic: int = 1000):
        self._topics: Dict[str, deque] = {}
        self._subscribers: Dict[str, list] = {}
        self._lock = threading.Lock()
        self._max = max_per_topic

    def publish(self, topic: str, message: dict) -> bool:
        with self._lock:
            if topic not in self._topics:
                self._topics[topic] = deque(maxlen=self._max)
            self._topics[topic].append(message)

        # Notify subscribers
        for cb in self._subscribers.get(topic, []):
            try:
                cb(topic, message)
            except Exception as e:
                logger.warning("Mock subscriber error: %s", e)
        return True

    def subscribe(self, topic: str, callback: Callable):
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(callback)

    def get_messages(self, topic: str, n: int = 10) -> list:
        with self._lock:
            msgs = list(self._topics.get(topic, []))
            return msgs[-n:]

    def topic_count(self, topic: str) -> int:
        with self._lock:
            return len(self._topics.get(topic, []))

    def all_topics(self) -> dict:
        with self._lock:
            return {t: len(msgs) for t, msgs in self._topics.items()}


_mock_broker = _MockBroker()

# ─────────────────────────────────────────────────────────────────────────────
# Real Kafka Producer (confluent-kafka or kafka-python)
# ─────────────────────────────────────────────────────────────────────────────

_producer = None
_producer_lock = threading.Lock()


def _try_build_producer():
    """Attempt to build a real Kafka producer. Returns None if not available."""
    if KAFKA_MOCK_MODE or not KAFKA_BOOTSTRAP_SERVERS:
        return None

    # Try confluent-kafka first
    try:
        from confluent_kafka import Producer

        conf = {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "client.id": KAFKA_CLIENT_ID,
            "acks": "all",
            "retries": 3,
            "retry.backoff.ms": 500,
        }
        if KAFKA_SECURITY_PROTOCOL == "SASL_SSL":
            conf.update({
                "security.protocol": "SASL_SSL",
                "sasl.mechanism": "PLAIN",
                "sasl.username": KAFKA_SASL_USERNAME,
                "sasl.password": KAFKA_SASL_PASSWORD,
            })

        producer = Producer(conf)
        logger.info("Kafka producer initialized (confluent-kafka): %s", KAFKA_BOOTSTRAP_SERVERS)
        return ("confluent", producer)
    except ImportError:
        pass
    except Exception as e:
        logger.warning("confluent-kafka producer failed: %s", e)

    # Try kafka-python
    try:
        from kafka import KafkaProducer

        kwargs = {
            "bootstrap_servers": KAFKA_BOOTSTRAP_SERVERS.split(","),
            "client_id": KAFKA_CLIENT_ID,
            "value_serializer": lambda v: json.dumps(v).encode("utf-8"),
            "acks": "all",
            "retries": 3,
        }
        if KAFKA_SECURITY_PROTOCOL == "SASL_SSL":
            kwargs.update({
                "security_protocol": "SASL_SSL",
                "sasl_mechanism": "PLAIN",
                "sasl_plain_username": KAFKA_SASL_USERNAME,
                "sasl_plain_password": KAFKA_SASL_PASSWORD,
            })

        producer = KafkaProducer(**kwargs)
        logger.info("Kafka producer initialized (kafka-python): %s", KAFKA_BOOTSTRAP_SERVERS)
        return ("kafka-python", producer)
    except ImportError:
        pass
    except Exception as e:
        logger.warning("kafka-python producer failed: %s", e)

    return None


def get_producer():
    """Get or initialize the Kafka producer (real or mock)."""
    global _producer
    with _producer_lock:
        if _producer is None:
            _producer = _try_build_producer()
            if _producer is None:
                logger.info("Kafka running in MOCK mode (in-memory broker)")
    return _producer


def close_producer():
    """Flush and close the Kafka producer on shutdown."""
    global _producer
    with _producer_lock:
        if _producer and isinstance(_producer, tuple):
            kind, prod = _producer
            try:
                if kind == "confluent":
                    prod.flush(timeout=5)
                elif kind == "kafka-python":
                    prod.flush(timeout=5)
                    prod.close()
            except Exception as e:
                logger.warning("Producer close error: %s", e)
        _producer = None


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def publish(topic: str, payload: dict, key: Optional[str] = None) -> bool:
    """
    Publish an event to a Kafka topic.

    Falls back to the in-memory mock broker if Kafka is unavailable.

    Args:
        topic:    Kafka topic name (use TOPICS constants)
        payload:  Dict to serialize as JSON
        key:      Optional partition key (e.g. customer_ref)

    Returns:
        True on success, False on failure
    """
    # Enrich with standard metadata
    event = {
        "topic": topic,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "syncflow-fte",
        **payload,
    }

    producer = get_producer()

    if producer is None:
        # Mock mode
        _mock_broker.publish(topic, event)
        logger.debug("Kafka[mock] → %s: %s", topic, str(event)[:120])
        return True

    kind, prod = producer
    try:
        encoded = json.dumps(event).encode("utf-8")
        enc_key = key.encode("utf-8") if key else None

        if kind == "confluent":
            prod.produce(topic, value=encoded, key=enc_key)
            prod.poll(0)  # trigger delivery callbacks
        elif kind == "kafka-python":
            prod.send(topic, value=event, key=enc_key)

        logger.debug("Kafka[%s] → %s", kind, topic)
        return True

    except Exception as e:
        logger.error("Kafka publish error on %s: %s — falling back to mock", topic, e)
        _mock_broker.publish(topic, event)
        return False


def publish_ticket_event(ticket_ref: str, channel: str, customer_ref: str,
                          status: str, payload: dict) -> bool:
    """Convenience: publish a ticket lifecycle event."""
    return publish(
        topic=TOPICS["TICKETS_INCOMING"],
        payload={
            "event_type": "ticket.updated",
            "ticket_ref": ticket_ref,
            "channel": channel,
            "customer_ref": customer_ref,
            "status": status,
            **payload,
        },
        key=ticket_ref,
    )


def publish_escalation(ticket_ref: str, reason: str, queue: str,
                        customer_ref: str, priority: str) -> bool:
    """Convenience: publish an escalation event."""
    return publish(
        topic=TOPICS["ESCALATIONS"],
        payload={
            "event_type": "ticket.escalated",
            "ticket_ref": ticket_ref,
            "escalation_reason": reason,
            "escalation_queue": queue,
            "customer_ref": customer_ref,
            "priority": priority,
        },
        key=ticket_ref,
    )


def publish_metrics(channel: str, confidence: float, sentiment: str,
                     escalated: bool, processing_ms: float) -> bool:
    """Convenience: publish an agent metrics event."""
    return publish(
        topic=TOPICS["METRICS"],
        payload={
            "event_type": "agent.metrics",
            "channel": channel,
            "confidence": confidence,
            "sentiment": sentiment,
            "escalated": escalated,
            "processing_ms": processing_ms,
        },
    )


def get_mock_stats() -> dict:
    """Return in-memory broker stats (useful for /health endpoint)."""
    return {
        "mode": "mock" if get_producer() is None else "kafka",
        "topics": _mock_broker.all_topics(),
    }


def get_recent_events(topic: str, n: int = 20) -> list:
    """Get recent events from the mock broker (useful for debugging)."""
    return _mock_broker.get_messages(topic, n)
