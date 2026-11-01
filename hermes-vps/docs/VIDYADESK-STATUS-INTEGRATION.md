# UDISE+ read-only VidyaDesk status contract

The UDISE control API exposes a dedicated aggregate-only endpoint:

- `GET /api/v1/integrations/vidyadesk/status`
- Authentication: `X-Vidyadesk-Token: <dedicated server-only token>`
- Environment variable: `UDISE_VIDYADESK_READ_TOKEN`
- Fixed scope: UMV Tetahali, internal SDMS school ID `2497128`, UDISE `10160203806`

The response includes only contract version, fixed school scope, job totals, counts by known status and workflow stage, unknown-state counts, stale queued/running indicators and timestamps. It never returns job IDs, session IDs, class names, event messages, errors, student information, cookies, credentials, result paths or workbook contents. Other schools are excluded at the SQL query boundary.

The endpoint does not accept or reuse the ordinary `Authorization: Bearer` control-plane credential. A missing or incorrect dedicated token is rejected. Keep the route on the existing private VPS/tailnet path; do not expose it through Tailscale Funnel.

Activation requires adding a high-entropy `UDISE_VIDYADESK_READ_TOKEN` to the private control API EnvironmentFile and restarting the service during an approved maintenance window. This PR does not provision a token, edit service configuration, restart services or change network exposure.
