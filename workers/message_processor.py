"""
workers/message_processor.py
SyncFlow Customer Success Digital FTE — Stage 3

Kafka-aware message processor worker.
Consumes from fte.tickets.incoming and related topics,
runs the full 9-stage processing pipeline, and publishes results.

Can run as:
  - Standalone Kafka consumer worker: python workers/message_processor.py
  - Called inline from the API (synchronous mode)
  - Background thread (non-blocking mode)
"""

import sys
import os
import json
import logging
import threading
import time
from datetime import datetime
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logger = logging.getLogger("syncflow.processor")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

_stop_event = threading.Event()


# ─────────────────────────────────────────────────────────────────────────────
# Core Processing Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def process_inbound_event(event: dict) -> dict:
    """
    Full 9-stage processing pipeline for an inbound support event.

    Stage 1: Validate and extract channel + payload
    Stage 2: Normalize message via channel adapter
    Stage 3: Identify / create customer
    Stage 4: Run AI agent (OpenAI Agents SDK or fallback)
    Stage 5: Sentiment analysis + priority computation
    Stage 6: Create / update support ticket
    Stage 7: Escalation routing
    Stage 8: Dispatch response
    Stage 9: Publish metrics event
    """
    t0 = time.time()
    channel = event.get("channel", "web_form")
    payload = event.get("payload", event)  # support both wrapped and flat

    try:
        from workers.message_worker import process_message
        result = process_message(
            channel=channel,
            raw_payload=payload,
            conversation_history=event.get("conversation_history"),
            debug=event.get("debug", False),
        )
    except Exception as e:
        logger.error("Pipeline error on channel=%s: %s", channel, e)
        result = {
            "success": False,
            "error": str(e),
            "channel": channel,
        }

    elapsed = round((time.time() - t0) * 1000, 1)
    result["processor_ms"] = elapsed

    # Publish metrics
    try:
        from kafka_client import publish_metrics, publish_ticket_event, publish_escalation, TOPICS
        publish_metrics(
            channel=channel,
            confidence=result.get("confidence_score", 0.0),
            sentiment=result.get("sentiment", "neutral"),
            escalated=result.get("escalated", False),
            processing_ms=elapsed,
        )
        if result.get("ticket_ref"):
            publish_ticket_event(
                ticket_ref=result["ticket_ref"],
                channel=channel,
                customer_ref=result.get("customer_ref", "unknown"),
                status=result.get("ticket_status", "open"),
                payload=result,
            )
        if result.get("escalated") and result.get("ticket_ref"):
            publish_escalation(
                ticket_ref=result["ticket_ref"],
                reason=result.get("escalation_reason", "unknown"),
                queue=result.get("escalation_queue", "general-support"),
                customer_ref=result.get("customer_ref", "unknown"),
                priority=result.get("priority", "medium"),
            )
    except Exception as e:
        logger.warning("Metrics publish skipped: %s", e)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Kafka Consumer Worker
# ─────────────────────────────────────────────────────────────────────────────

def _consume_confluent(topics: list, group_id: str):
    """Consume from Kafka using confluent-kafka."""
    from confluent_kafka import Consumer, KafkaException
    import os

    conf = {
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "group.id": group_id,
        "auto.offset.reset": "earliest",
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
    consumer.subscribe(topics)
    logger.info("Kafka consumer started: topics=%s group=%s", topics, group_id)

    try:
        while not _stop_event.is_set():
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error("Kafka consumer error: %s", msg.error())
                continue

            try:
                event = json.loads(msg.value().decode("utf-8"))
                logger.info("Processing event from %s (offset=%d)", msg.topic(), msg.offset())
                result = process_inbound_event(event)
                logger.info("Event processed: ticket=%s success=%s",
                            result.get("ticket_ref", "?"), result.get("success", False))
            except Exception as e:
                logger.error("Event processing failed: %s", e)
                # Publish to dead-letter
                try:
                    from kafka_client import publish, TOPICS
                    publish(TOPICS["DEAD_LETTER"], {
                        "original_topic": msg.topic(),
                        "error": str(e),
                        "raw_value": msg.value().decode("utf-8")[:500],
                    })
                except Exception:
                    pass
    finally:
        consumer.close()
        logger.info("Kafka consumer closed")


def _consume_mock():
    """Poll the mock broker for events (dev/CI mode)."""
    from kafka_client import _mock_broker, TOPICS

    logger.info("Message processor running in MOCK mode (polling in-memory broker)")
    processed_counts = {}

    while not _stop_event.is_set():
        for topic in [TOPICS["TICKETS_INCOMING"], TOPICS["EMAIL_INBOUND"], TOPICS["WA_INBOUND"]]:
            total = _mock_broker.topic_count(topic)
            prev = processed_counts.get(topic, 0)
            if total > prev:
                new_msgs = _mock_broker.get_messages(topic, total - prev)
                for event in new_msgs:
                    try:
                        process_inbound_event(event)
                    except Exception as e:
                        logger.error("Mock processing error: %s", e)
                processed_counts[topic] = total

        time.sleep(0.5)


def run_worker(
    topics: Optional[list] = None,
    group_id: str = "syncflow-processor",
    mock_fallback: bool = True,
):
    """
    Start the message processor worker.

    Args:
        topics:         Kafka topics to consume (default: all inbound topics)
        group_id:       Kafka consumer group ID
        mock_fallback:  If True and Kafka unavailable, run in mock polling mode
    """
    if topics is None:
        from kafka_client import TOPICS
        topics = [TOPICS["TICKETS_INCOMING"], TOPICS["EMAIL_INBOUND"], TOPICS["WA_INBOUND"]]

    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
    mock_mode = os.getenv("KAFKA_MOCK_MODE", "true").lower() == "true"

    if not mock_mode and bootstrap:
        try:
            _consume_confluent(topics, group_id)
            return
        except ImportError:
            logger.warning("confluent-kafka not installed, trying mock mode")

    if mock_fallback:
        _consume_mock()
    else:
        logger.error("Kafka unavailable and mock_fallback=False — worker not started")


def start_worker_thread(**kwargs) -> threading.Thread:
    """Start the processor in a background thread."""
    t = threading.Thread(target=run_worker, kwargs=kwargs, daemon=True, name="message-processor")
    t.start()
    logger.info("Message processor thread started")
    return t


def stop_worker():
    """Signal the worker to stop."""
    _stop_event.set()


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import signal

    def _sighandler(sig, frame):
        logger.info("Shutdown signal received")
        stop_worker()

    signal.signal(signal.SIGINT, _sighandler)
    signal.signal(signal.SIGTERM, _sighandler)

    logger.info("Starting SyncFlow Message Processor Worker")
    run_worker()
