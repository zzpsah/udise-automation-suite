# Production release label

The console header and browser title use app/release.ts as the single source of truth.

- Format: YYYY.MM.DD.N (release number N increments for each production UI release on that date).
- Update version and the human-readable date in app/release.ts for every production UI update.
- Keep the UI layout and styles unchanged unless the feature request specifically requires a visual change.
- Git commit history remains the source of truth for exact code changes; the visible label is a quick at-a-glance release marker.


## v2026.10.17.4 — 17 Oct 2026
- Fix production Oracle connectivity by routing the control API through standard HTTPS (443), since Vercel requests to port 10000 were timing out.
- Add the /api/v1 and /session path proxies on the existing HTTPS endpoint without replacing its root handler or the existing Funnel ports.
- Update the Oracle public session URL to standard HTTPS so the existing-browser-session fallback opens on the correct host.
