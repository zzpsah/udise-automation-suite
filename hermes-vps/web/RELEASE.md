# Production release label

The console header and browser title use app/release.ts as the single source of truth.

- Format: YYYY.MM.DD.N (release number N increments for each production UI release on that date).
- Update version and the human-readable date in app/release.ts for every production UI update.
- Keep the UI layout and styles unchanged unless the feature request specifically requires a visual change.
- Git commit history remains the source of truth for exact code changes; the visible label is a quick at-a-glance release marker.


## v2026.10.17.4 — 17 Oct 2026
- Diagnosed Vercel timeouts to the Tailscale Funnel upstream on ports 10000 and 443. The HTTPS path routing was validated locally, but Vercel still could not reach the Funnel endpoint.

## v2026.10.17.5 — 17 Oct 2026
- Route the production web app through a Cloudflare Quick Tunnel to the Oracle Control API after confirming Vercel cannot reach the Tailscale Funnel endpoint.
- Use the same public upstream for secure browser-session fallback links.
- Operational caveat: Cloudflare Quick Tunnels have no uptime guarantee and issue a new hostname if the tunnel process is restarted; replace with a named Cloudflare Tunnel for a durable production setup.
