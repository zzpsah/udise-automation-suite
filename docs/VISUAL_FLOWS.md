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

## Write safety — durable Preview → Write

```mermaid
flowchart TD
    A[Run & Save] --> B[Preview Job]
    B --> C[Fresh reads]
    C --> D[Eligible changes]
    D --> E[One typed approval / bounded limit]
    E --> F[Create Write Child Job]
    F --> G[Fresh pre-write read]
    G --> H[POST once per approved record]
    H --> I[Fresh read-back]
    I --> J{Persisted?}
    J -->|yes| K[Confirmed result]
    J -->|no| L[Stop / Manual Review]
    X[Browser refresh / disconnect] -. does not cancel .-> F
```

The write child is server-durable and independent of browser polling. Read-only stages never create a write child.

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

## Facility Profile — protected values

```mermaid
flowchart TD
    A[Fresh Facility read] --> B{Existing saved value?}
    B -->|Yes| C[KEEP unchanged]
    C --> D{Dependent Yes?}
    D -->|Yes| E[Protect + manual review]
    B -->|Blank / unanswered| F[Generate permitted default]
    F --> G[Preview]
    E --> G
    G --> H[Bounded approval]
    H --> I[Fresh pre-write read]
    I --> J[Write only approved blank fields]
    J --> K[Fresh read-back]
```

Existing **Yes** values and other saved values are never overwritten.

## Remember UDISE credential

```mermaid
sequenceDiagram
    participant U as Operator Browser
    participant UI as UDISE UI
    participant C as Chrome Credential Store
    U->>UI: Enable Remember UDISE password
    UI->>C: PasswordCredential / navigator.credentials.store
    C-->>UI: Browser-managed credential result
    U->>UI: Return to login
    UI->>C: navigator.credentials.get
    C-->>UI: Credential when browser permits
    UI->>UI: Fill username/password
```

The application does not intentionally persist the password server-side.

## Deployment

```mermaid
flowchart LR
    G[GitHub main] --> O[Oracle clone]
    G --> V[Vercel Git project]
    O --> S1[udise-control-api.service]
    O --> S2[udise-web.service]
    V --> P[udise-auto.vercel.app]
    P --> Q[Production build verification]
```mermaid
flowchart LR
    G[GitHub main] --> O[Oracle clone]
    G --> V[Vercel project]
    O --> S1[udise-control-api.service]
    O --> S2[udise-web.service]
    V --> P[udise-auto.vercel.app]
```
