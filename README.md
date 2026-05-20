# Peerbench

Bank peer-benchmarking tool on FFIEC Call Report data. Anchor: MidFirst Bank (FDIC Cert 4063).

See [`PLAN.md`](./PLAN.md) for the full project plan and [`CLAUDE.md`](./CLAUDE.md) for repo conventions. Install and run instructions land in Phase 4.

## Web (Phase 2)

Next.js 16 dashboard lives in [`web/`](./web). To run it locally:

```bash
cd web
cp .env.local.example .env.local   # fill in NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY
npm install
npm run dev                         # http://localhost:3000
```

The dashboard reads the `ratios` table only — all formula logic lives in the
Python pipeline. Design tokens are in [`docs/design.md`](./docs/design.md)
and encoded in `web/app/globals.css`.
