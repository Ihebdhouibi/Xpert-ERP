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
| 3 | Idle-unload models | _tbd_ (idle) | — | pending |
| 4 | ONNX Runtime + INT8 | _tbd_ | _tbd_ | pending |
| 5 | Slim multi-stage image | — | _tbd_ | pending |
