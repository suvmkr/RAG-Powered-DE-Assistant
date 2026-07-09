# Pipeline Runbook

## Incident Response

### P1: Pipeline Failure (data not available by SLA)
1. Check Airflow UI for failed tasks
2. Review logs: `gcloud logging read "resource.labels.dag_id=daily_warehouse_refresh"`
3. Common causes:
   - Kafka consumer lag > 1M messages → restart consumer group
   - BigQuery quota exceeded → check quota dashboard
   - Schema mismatch → run `python tools/schema_check.py --pipeline <name>`
4. Escalate to #data-engineering-oncall if unresolved in 30min

### P2: Data Quality Failure
1. Identify failing check from monitoring dashboard
2. Run: `python tools/quality_check.py --table <table> --date <date>`
3. If row count anomaly: check upstream for missing data
4. If null rate spike: check schema changes in source system

## Rollback Procedure
```bash
# Reprocess a specific date partition
python tools/reprocess.py --pipeline user_events --date 2024-01-15

# Roll back Delta table to previous version
python tools/delta_rollback.py --table orders_fact --version 42
```
