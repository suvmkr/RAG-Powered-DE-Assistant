# SLA Policy

| Pipeline | SLA Window | Owner | P1 Threshold |
|---|---|---|---|
| user_events | 04:00 UTC | @alice | 30 min breach |
| orders_fact | 06:00 UTC | @bob | 60 min breach |
| product_catalog | Every 6h | @charlie | 2h breach |
| sessions | 05:00 UTC | @diana | 45 min breach |

## Penalties
- **SLA breach < 30min**: Log only
- **SLA breach 30-60min**: Slack alert to #data-ops
- **SLA breach > 60min**: PagerDuty + email to stakeholders
- **Data quality failure**: Immediate halt + stakeholder notification
