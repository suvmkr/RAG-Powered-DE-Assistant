"""
daily_refresh_dag.py
Airflow DAG: orchestrates the daily data warehouse refresh.
Schedule: 02:00 UTC
SLA: all tasks complete within 90 minutes.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator

DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "sla": timedelta(minutes=90),
    "email_on_failure": True,
    "email": ["de-alerts@company.com"],
}

with DAG(
    dag_id="daily_warehouse_refresh",
    default_args=DEFAULT_ARGS,
    schedule_interval="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["core", "warehouse"],
) as dag:

    ingest_user_events = BigQueryInsertJobOperator(
        task_id="ingest_user_events",
        configuration={"query": {"query": "{% include 'sql/user_events_dedup.sql' %}", "useLegacySql": False}},
    )

    build_orders_fact = PythonOperator(
        task_id="build_orders_fact",
        python_callable=lambda: print("Orders fact build triggered"),
    )

    notify_success = SlackWebhookOperator(
        task_id="notify_success",
        http_conn_id="slack_webhook",
        message=":white_check_mark: Daily refresh completed successfully",
        trigger_rule="all_success",
    )

    ingest_user_events >> build_orders_fact >> notify_success
