# Production release label

The console header and browser title use app/release.ts as the single source of truth.

- Format: YYYY.MM.DD.N (release number N increments for each production UI release on that date).
- Update version and the human-readable date in app/release.ts for every production UI update.
- Keep the UI layout and styles unchanged unless the feature request specifically requires a visual change.
- Git commit history remains the source of truth for exact code changes; the visible label is a quick at-a-glance release marker.
