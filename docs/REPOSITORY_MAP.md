# Repository Map

## Root

- `README.md`
- `AGENTS.md`
- `DEVOS.md`
- `RULES.md`
- `TASKS.md`
- `PRD.md`
- `docs/` — canonical current docs
- `hermes-vps/` — current production implementation
- `UDISE_Automation_v2.7.3_2026-09-23.ipynb` — historical interactive baseline

## Production tree

```text
hermes-vps/
├── control_api/
│   ├── app.py
│   └── capabilities.py
├── udise_vps/
│   ├── cli.py
│   ├── session.py
│   ├── students.py
│   ├── snapshot.py
│   ├── general_profile.py
│   ├── ep.py
│   ├── facility.py
│   ├── completion.py
│   └── preview_report.py
├── web/app/
│   ├── page.tsx
│   ├── lib.ts
│   ├── styles.css
│   └── api/
├── tests/
├── tools/
└── brain/hermes-vps/
```

## Runtime

Ephemeral:
`$XDG_RUNTIME_DIR/udise-control/`

Durable:
`~/.hermes/state/udise-control/`

If older docs conflict with canonical docs or current source, current source + canonical docs win.
