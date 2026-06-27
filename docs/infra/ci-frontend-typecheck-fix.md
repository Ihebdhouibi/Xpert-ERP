# CI fix: frontend type-check failure (`TS5103 ignoreDeprecations`)

**Date:** 2026-06-27
**Affected job:** `CI / Frontend (type-check + lint + build)` (`.github/workflows/ci.yml`)
**Fix commit:** `fix(frontend): repair CI type-check + lint (invalid ignoreDeprecations)`

## Symptom

Every push/PR to `develop` showed the **Frontend** CI job failing at the
**Type check** step:

```
tsconfig.json(20,27): error TS5103: Invalid value for '--ignoreDeprecations'.
Error: Process completed with exit code 2.
```

The `Lint` and `Build` steps showed as skipped/neutral — they never ran,
because the failed step stops the job.

## Root cause

`frontend/tsconfig.json` contained:

```jsonc
"ignoreDeprecations": "6.0",
```

`ignoreDeprecations` is a TypeScript escape hatch that says "I'm knowingly
using a deprecated compiler option — don't error." **Its value must be a
specific version string that the compiler recognizes.** Current TypeScript
(5.x, the repo uses 5.7.x) only accepts `"5.0"`. `"6.0"` does not exist, so
the compiler rejects the whole config with `TS5103` before it type-checks a
single file.

Two compounding facts:

1. **It had been broken since the frontend was scaffolded** (commit `73489a1`).
   The value was wrong from day one.
2. **It only fails in CI**, never in local dev. Local development uses the
   Vite dev server (`npm run dev`), which does **not** run `tsc`. CI is the
   first place `tsc --noEmit` actually executes, so it's the first place the
   bad config is caught.

Additionally, `ignoreDeprecations` was **dead config** here — none of the
options in this `tsconfig.json` are actually deprecated, so the line served
no purpose even with a valid value.

## The fix

1. **Delete the invalid line** from `frontend/tsconfig.json`. With it gone,
   `tsc` parses the config and runs normally.

2. **This unmasked 38 pre-existing type errors and 61 lint problems** that the
   aborted compile had been hiding. They had to be fixed too, or the job would
   simply fail later (type-check, then lint). All were fixed with minimal,
   behavior-preserving changes:

   - **~28 unused imports/vars/consts** removed (`TS6133`, from
     `noUnusedLocals`/`noUnusedParameters`).
   - **`DashboardPage`**: corrected the module-tile `.filter()` type guard to
     `(m): m is Exclude<typeof m, false>` so the `cond && {tile}` entries
     narrow correctly. Same tiles render.
   - **`QuotationCreatePage` / `RepairOrderCreatePage`**: replaced the
     circular `placeholderData: (prev: typeof data) => prev` (which made the
     query result reference its own inferred type — `TS7022`/`TS2502`) with
     TanStack Query v5's `keepPreviousData`. Identical runtime behavior; the
     pattern is already used elsewhere in the codebase.
   - **`VehicleEditPage`**: removed `vin` from the update payload. The backend
     `VehicleUpdateRequest` schema deliberately omits `vin` (VIN is an
     immutable identifier), so it was already being dropped server-side.
   - **`eslint.config.js`**: added `@typescript-eslint/no-unused-vars` with
     `^_` ignore pattern; typed several `catch (e: any)` / `any` sites as
     `unknown` with narrow casts (`no-explicit-any`).

## Verification

Run from `frontend/`:

```bash
npx tsc --noEmit   # exit 0
npm run lint       # exit 0 (0 problems)
npm run build      # exit 0
```

All three pass — matching the three frontend CI steps.

## Editor note

After the fix, VS Code may still show a red squiggle on `tsconfig.json`
line 20. That is a **stale TypeScript language-server diagnostic** cached from
the old line 20 (the deleted `ignoreDeprecations` line). Clear it with
Command Palette → **"TypeScript: Restart TS Server"**. The compiler reports
zero errors.

## Lesson / follow-up

The class of bug — a config error that only the CI `tsc` catches — is exactly
why a frontend pre-commit / local type-check would help. Today the encoding
pre-commit hooks (`.pre-commit-config.yaml`) cover formatting; a future
addition could run `tsc --noEmit` on the frontend before commit so this kind
of failure is caught locally rather than in CI.
