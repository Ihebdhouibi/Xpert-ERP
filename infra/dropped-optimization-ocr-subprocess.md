# Dropped optimization — idle-killed OCR worker process

**Status:** disabled by default (`cfg_ocr_process_isolation = False`)
**Date:** 21/06/2026 · **Branch:** `deployment`
**Code:** retained (`app/modules/ocr/process_runner.py`), can be re-enabled later.

---

## What it was (cost-optimization "Opt 3")

OCR ran in a **dedicated worker subprocess** that was **terminated after an idle
period**, with two benefits:

1. **RAM reclaimed when idle** — the OCR model's memory was returned to the OS
   between scans (the native predictor does not release memory on in-process
   `del`; only killing the process frees it).
2. **Isolation** — the heavy model lived outside the API process, and a native
   OCR crash could not take the API down.

It was implemented with a `ProcessPoolExecutor(max_workers=1)` plus an idle
watchdog (`IdleProcessRunner`).

---

## Why we dropped it (for now)

On **Windows + `uvicorn --reload`**, spawning that worker subprocess from inside
a reloader-managed server proved **unreliable**: the child could fail to
initialise and the scan came back **empty (0 lines)** with no clear error,
because the failure happened in the child before logging was usable. This made
local OCR appear broken and was hard to debug.

Rather than ship a fragile component, we run OCR **in-process** (the original,
proven path: a thread executor inside the API process). This is one variable
removed and OCR behaves deterministically again.

---

## The drop we accept

| Aspect | With subprocess (Opt 3) | In-process (now) |
|--------|-------------------------|------------------|
| Peak RAM during a scan | ~233 MB (ONNX) | ~233 MB (ONNX) — **unchanged** |
| Model RAM **between** scans | reclaimed (≈0) | **stays resident ~90–100 MB** in the API process |
| Crash isolation | yes | no (an OCR crash affects the API worker) |
| API process footprint | lean | carries the model after first scan |

**Net effect:** small. Because the default engine is now the **lightweight ONNX**
backend (~90–100 MB resident, ~233 MB transient peak — not Paddle's ~525 MB), the
model simply staying loaded in the API process is cheap. Periodic gunicorn worker
recycling (`max_requests`, from Opt 1) still bounds any long-run growth.

**Impact on hosting:** none material. The recommended **Orange `s6.xlarge.2`
(4 vCPU / 8 GB)** sizing is unaffected — 8 GB remains comfortable.

---

## How to re-enable / fix later

The runner code is kept. To bring the optimization back safely:

- Set `cfg_ocr_process_isolation = true` (env: `CFG_OCR_PROCESS_ISOLATION=true`).
- Validate specifically on the **production topology** (Linux + gunicorn workers,
  no `--reload`), where `fork` is used and the spawn fragility does not apply.
- Or replace the ad-hoc subprocess with a proper out-of-process worker
  (Celery/RQ + Redis) per the M8 plan in `projectContext/08_TECH_STACK.md`, which
  gives the same RAM/isolation benefit with a battle-tested mechanism.
