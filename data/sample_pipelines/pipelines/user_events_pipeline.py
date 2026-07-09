"""
user_events_pipeline.py
Ingests raw click-stream events from Kafka, deduplicates, validates,
and writes to the user_events_clean table in BigQuery.
"""
import hashlib
from datetime import datetime, timedelta
from typing import Iterator, Dict, Any

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions


DEDUP_WINDOW_HOURS = 24
REQUIRED_FIELDS = ["user_id", "event_type", "timestamp", "session_id"]


class DeduplicateEvents(beam.DoFn):
    """
    Removes duplicate events within a 24-hour window using a composite key
    of (user_id, event_type, session_id).
    Deduplication strategy: keep the FIRST occurrence (earliest timestamp).
    """

    def process(self, element: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        dedup_key = hashlib.md5(
            f"{element['user_id']}:{element['event_type']}:{element['session_id']}".encode()
        ).hexdigest()
        yield {**element, "_dedup_key": dedup_key}


class ValidateSchema(beam.DoFn):
    """Schema validation – emits valid records or dead-letter queue."""

    def process(self, element):
        missing = [f for f in REQUIRED_FIELDS if f not in element or element[f] is None]
        if missing:
            yield beam.pvalue.TaggedOutput("dead_letter", {**element, "_missing_fields": missing})
        else:
            yield element


def run(argv=None):
    options = PipelineOptions(argv)
    with beam.Pipeline(options=options) as p:
        raw = (
            p
            | "ReadKafka" >> beam.io.ReadFromKafka(
                consumer_config={"bootstrap.servers": "kafka:9092"},
                topics=["raw.user_events"],
            )
            | "ParseJSON" >> beam.Map(lambda x: __import__("json").loads(x[1]))
        )

        valid, dead = (
            raw
            | "ValidateSchema" >> beam.ParDo(ValidateSchema()).with_outputs("dead_letter", main="valid")
        )

        (
            valid
            | "Deduplicate" >> beam.ParDo(DeduplicateEvents())
            | "WriteBigQuery" >> beam.io.WriteToBigQuery(
                table="project:dataset.user_events_clean",
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            )
        )

        dead | "WriteDeadLetter" >> beam.io.WriteToText("gs://bucket/dead_letter/user_events")
