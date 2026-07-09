# Data Pipeline Overview

## Architecture

Our data platform processes ~500M events/day across three major pipelines:

### user_events pipeline
- **Source**: Kafka topic `raw.user_events`
- **Transform**: Deduplication (24h window), schema validation
- **Sink**: BigQuery `dataset.user_events_clean`
- **Owner**: @alice
- **SLA**: Available by 04:00 UTC daily

### orders_fact pipeline
- **Source**: Postgres CDC via Debezium
- **Transform**: PII masking (SHA-256), late-arriving data (3-day watermark)
- **Sink**: Delta Lake `warehouse.orders_fact`
- **Owner**: @bob
- **SLA**: Available by 06:00 UTC daily

### product_catalog pipeline
- **Source**: REST API (catalog service)
- **Transform**: Denormalization, price history tracking
- **Sink**: BigQuery `dataset.product_catalog`
- **Owner**: @charlie
- **SLA**: Refreshed every 6 hours

## Data Quality Framework

Each pipeline runs the following quality checks:
1. **Row count validation** – compare against previous day ± 20%
2. **Null rate checks** – critical columns must have < 0.1% nulls
3. **Freshness check** – data must not be older than SLA window
4. **Schema drift detection** – alert on new/dropped columns
