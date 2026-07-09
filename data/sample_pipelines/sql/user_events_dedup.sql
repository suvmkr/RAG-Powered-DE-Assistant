-- user_events_dedup.sql
-- Purpose: Final deduplication layer in BigQuery.
-- Runs daily at 02:00 UTC via Airflow.
-- Partition: event_date (DATE)
-- Clustering: user_id, event_type

CREATE OR REPLACE TABLE `project.dataset.user_events_clean_v2`
PARTITION BY event_date
CLUSTER BY user_id, event_type
AS
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, event_type, session_id, DATE(timestamp)
            ORDER BY timestamp ASC
        ) AS rn
    FROM `project.dataset.user_events_raw`
    WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
)
SELECT
    * EXCEPT(rn, _dedup_key),
    DATE(timestamp) AS event_date
FROM ranked
WHERE rn = 1;
