# Vendored OCR models (ONNX backend)

These files let the ONNX engine (`cfg_ocr_engine="onnx"`) read **French** text.
RapidOCR's own bundled recognition model is Chinese/English and mangles accents
(é, è, ô, ç), so we ship the latin PP-OCRv3 model instead.

| File | What it is |
|------|------------|
| `latin_PP-OCRv3_rec.onnx` | Latin recognition model, converted to ONNX (~9 MB) |
| `latin_dict.txt` | Character dictionary the model was trained with (185 chars) |

The ONNX engine uses these by default; override via `cfg_ocr_onnx_rec_model_path`
/ `cfg_ocr_onnx_rec_keys_path`.

## Provenance / how to reproduce

Source model: PaddleOCR PP-OCRv3 multilingual **latin** recognition (inference
format), the same model PaddleOCR auto-selects for `lang=fr`.

```bash
# 1. Download the classic inference model
curl -fSL -o latin.tar \
  https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/latin_PP-OCRv3_rec_infer.tar
tar -xf latin.tar

# 2. Convert to ONNX with the standalone (classic) paddle2onnx.
#    Use paddle2onnx==1.3.1 — the 2.x line refuses paddlepaddle 3.0.0 on Windows.
pip install paddle2onnx==1.3.1
paddle2onnx \
  --model_dir latin_PP-OCRv3_rec_infer \
  --model_filename inference.pdmodel \
  --params_filename inference.pdiparams \
  --save_file latin_PP-OCRv3_rec.onnx \
  --opset_version 14 --enable_onnx_checker True
```

`latin_dict.txt` is PaddleOCR's canonical `ppocr/utils/dict/latin_dict.txt`.

`paddle2onnx` is a **build-time, one-off** tool — it is not a runtime dependency
and is intentionally absent from the `onnx` extra in `pyproject.toml`.

## Validation

Verified against the PaddleOCR latin engine on accented strings
(`Société Générale`, `véhicule`, `Citroën`…): the ONNX output matches Paddle and
is occasionally better. Residual errors (e.g. an occasional dropped `ô`) appear
identically on **both** engines, i.e. they are model traits, not conversion
defects. See `tests/test_ocr_onnx_engine.py::test_onnx_latin_model_preserves_french_accents`.
