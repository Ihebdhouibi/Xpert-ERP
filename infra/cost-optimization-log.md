# OCR / Deployment Cost-Optimization Log

Working log for the `deployment` branch. Each optimization is measured, tested,
and committed separately. Numbers below feed the final French client report.

Measurement host: dev workstation (Windows, CPU-only), Python 3.11.0,
`paddleocr==3.0.1`, `paddlepaddle==3.0.0`, model `PP-OCRv3` / `lang=fr`.
RAM measured via Windows `GetProcessMemoryInfo` (Working Set).

---

## Baseline (before any optimization)

### RAM — single process

| Stage | RSS |
|-------|-----|
| Base Python process | 30 MB |
| After importing paddleocr + cv2 + PIL | 225 MB |
| After PaddleOCR model load | **424 MB** |
| Peak during one `predict()` | **595 MB** |

### RAM — effective deployment ceiling

OCR runs as a FastAPI `BackgroundTask` **inside the web worker process**
(`ocr/router.py` → `background_tasks.add_task(process_ocr_job, …)`). The
Dockerfile runs `gunicorn … --workers 2`, and each worker lazily loads its own
PaddleOCR singleton on first scan.

→ **Worst-case OCR RAM ≈ 2 × 595 MB ≈ 1.1–1.2 GB**, plus base app + Postgres +
Redis + MinIO on the same host. This is what forces the 16 GB VM.

### Disk — OCR / imaging stack in the runtime image

| Package / cache | Size |
|-----------------|------|
| paddlepaddle (`paddle/`) | 368 MB |
| paddlex | 10 MB |
| paddleocr | 0.4 MB |
| opencv-python-headless (`cv2/`) | 127 MB |
| pymupdf | 47 MB |
| downloaded model cache (`~/.paddlex`, PP-OCRv3 fr) | 229 MB |
| **Total attributable to OCR/imaging** | **~780 MB** |

Plus `build-essential` + dev headers currently shipped in the single-stage
runtime image (removed in Opt 5).

---

## Results summary (filled in as each optimization lands)

| Opt | Change | RAM peak | Image / disk | Status |
|-----|--------|----------|--------------|--------|
| — | Baseline | ~1.1–1.2 GB (2 workers) | ~780 MB OCR stack | measured |
| 1 | Right-size workers / 1 model instance | ~0.6 GB peak (1× model, was 2×) | — | **done** |
| 2 | Disable aux models (doc-ori/unwarp/textline) | 595 → **525 MB** peak (−70 MB) | −46 MB models | **done** |
| 3 | Idle-killed OCR subprocess | model RAM fully reclaimed after idle; API process stays ~40 MB + app (model never loaded there) | — | **DISABLED by default** — unreliable under uvicorn --reload on Windows; see [dropped-optimization-ocr-subprocess.md](dropped-optimization-ocr-subprocess.md) |
| 4 | ONNX Runtime engine (RapidOCR) | **233 MB** peak (vs 525) | **~52 MB** wheels (vs ~780) | **done** (opt-in; default still paddle) |
| 5 | Slim multi-stage image | — | build tools out of runtime; paddle-free onnx variant | **done** (deps validated; size est. — see note) |

### Opt 5 detail — multi-stage image

- Single-stage → **multi-stage**: `build-essential` + `-dev` headers stay in the
  builder and are **not** shipped (saves ~250–400 MB of runtime layers).
- OCR backend is a build arg: `--build-arg OCR_BACKEND=onnx` (**default**) or
  `paddle` (fallback). `paddle`/`onnx`/`dev` are separate pyproject extras; `dev`
  installs the onnx backend so CI exercises the default engine.

> **Update — ONNX promoted to default.** After converting the latin PP-OCRv3 rec
> model to ONNX (vendored under `app/modules/ocr/models/`) and validating French
> accents on real documents, `cfg_ocr_engine` now defaults to `onnx` and the
> Docker image builds the onnx backend by default. PaddleOCR remains available as
> a fallback (`cfg_ocr_engine=paddle` + the `[paddle]` extra).
- Runtime now runs as a **non-root** user; `.dockerignore` keeps `.venv`/logs out
  of the context.

Estimated image sizes (from measured package footprints — a real build needs a
running Docker daemon, which was unavailable on the dev box; build on CI / the
deploy host to confirm):

| Image | Build tools in runtime | OCR stack | Est. size |
|-------|------------------------|-----------|-----------|
| Old single-stage (paddle) | yes (~300 MB) | ~780 MB | ~1.6–1.8 GB |
| New multi-stage `paddle` | no | ~780 MB | ~1.3–1.5 GB |
| New multi-stage `onnx` | no | ~52 MB | **~0.6–0.7 GB** |

### Opt 4 detail — ONNX (RapidOCR) vs Paddle, measured

| Stage | Paddle (lean) | ONNX |
|-------|---------------|------|
| After import | 225 MB | 57 MB |
| After model load | 373 MB | 92 MB |
| Peak during predict | 525 MB | **233 MB** |
| Disk: engine wheels | paddlepaddle 368 + paddlex 10 + opencv 127 ≈ 505 MB | onnxruntime 36 + rapidocr 16 ≈ **52 MB** |
| Models on disk | ~229 MB cache | bundled (~10 MB) |
| Synthetic doc (no accents) | 4/4 lines | 4/4 lines |

Engine is selectable via `cfg_ocr_engine` (`paddle` default | `onnx`). With ONNX
active, OCR is no longer the RAM driver — peak ~233 MB fits comfortably on an
8 GB VM.

### Opt 4b — French latin model for ONNX (done)

The original ONNX gap was French accents: RapidOCR's default model is ch/en and
turned `Jérôme` into `JBrBme`. Resolved by converting the latin PP-OCRv3
recognition model to ONNX and vendoring it (+ its dict) under
`app/modules/ocr/models/`; the ONNX engine now uses it by default. **Validated:
accent parity with the PaddleOCR latin engine** (`Société Générale`, `véhicule`,
`Citroën` decode correctly; residual errors match Paddle exactly → model traits,
not conversion defects). Provenance + reproduction in the models `README.md`.

**ONNX is now functionally ready for French.** Activation is a deployment choice
(needs the onnx image + `CFG_OCR_ENGINE=onnx`), not a code change.
