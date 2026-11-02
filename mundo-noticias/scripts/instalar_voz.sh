#!/usr/bin/env bash
# Descarga Piper (MIT) y la voz es_ES-davefx-medium (CC0) y parchea la versión IR del modelo para Piper 2023.11.14-2.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p voz && cd voz
if [ ! -x piper/piper ]; then
  curl -fsSL -o piper.tar.gz https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz
  tar xzf piper.tar.gz && rm piper.tar.gz
fi
if [ ! -f es_ES-davefx-medium_ir8.onnx ]; then
  curl -fsSL -o v.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-es_ES-davefx-medium.tar.bz2
  tar xjf v.tar.bz2 && rm v.tar.bz2
  cp vits-piper-es_ES-davefx-medium/es_ES-davefx-medium.onnx.json es_ES-davefx-medium_ir8.onnx.json 2>/dev/null || true
  python3 - <<'PY'
b = bytearray(open('vits-piper-es_ES-davefx-medium/es_ES-davefx-medium.onnx', 'rb').read())
b[1] = 8   # IR version 9 -> 8 (lo entiende el onnxruntime de Piper)
open('es_ES-davefx-medium_ir8.onnx', 'wb').write(b)
PY
  cp -r vits-piper-es_ES-davefx-medium/espeak-ng-data espeak-ng-data
fi
echo "Voz lista."
