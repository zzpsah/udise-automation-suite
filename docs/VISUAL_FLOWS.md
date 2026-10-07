# Visual Flow Diagrams

## Full system

```mermaid
flowchart LR
    A[User Browser] --> B[Vercel Next.js]
    B --> C[Oracle Control API]
    C --> D[Headless Chromium]
    D --> E[UDISE Auth]
    D --> F[SDMS Students Module]
    C --> G[udise_vps]
    G --> F
    G --> H[eShikshaKosh]
    C --> I[(Runtime sessions)]
    C --> J[(Job DB + Results)]
```

## Post-login school context

```mermaid
flowchart TD
    A[Authenticated] --> B[/p0/api/user]
    B --> C{regionType == 6?}
    C -->|yes| D[userRegionId = internal school ID]
    D --> E[School details API]
    E --> F[School name + UDISE code]
    F --> G[Students Module connected]
    G --> H[Session countdown]
    G --> I[Class selector]
    I --> J[Workflow selector]
```

## Write safety

```mermaid
flowchart TD
    A[Run & Save] --> B[Preview]
    B --> C[Fresh reads]
    C --> D[Eligible changes]
    D --> E[Bounded approval]
    E --> F[Fresh pre-write read]
    F --> G[POST once]
    G --> H[Fresh read-back]
    H --> I{Verified?}
    I -->|yes| J[Confirmed]
    I -->|no| K[Stop]
```

## eShikshaKosh → EP

```mermaid
flowchart LR
    A[eShikshaKosh export] --> B[Normalize source]
    C[UDISE roster/profile] --> D[Match engine]
    B --> D
    D --> E{confident match?}
    E -->|yes| F[Admission/stream/source values]
    E -->|no| G[Manual review]
    F --> H[EP preview]
    H --> I[Guarded save]
    I --> J[Fresh EP read-back]
```

## Deployment

```mermaid
flowchart LR
    G[GitHub main] --> O[Oracle clone]
    G --> V[Vercel project]
    O --> S1[udise-control-api.service]
    O --> S2[udise-web.service]
    V --> P[udise-auto.vercel.app]
```
