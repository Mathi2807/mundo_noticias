"""Voz neuronal sin depender de ningún navegador: Piper TTS (MIT) + voz es_ES-davefx-medium (CC0)."""
import os, subprocess, wave
import numpy as np
from .util import normalizar_tts

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPER_DIR = os.environ.get('MUNDO_PIPER', os.path.join(RAIZ, 'voz', 'piper'))
MODELO = os.environ.get('MUNDO_MODELO', os.path.join(RAIZ, 'voz', 'es_ES-davefx-medium_ir8.onnx'))
ESPEAK = os.environ.get('MUNDO_ESPEAK', os.path.join(RAIZ, 'voz', 'espeak-ng-data'))


def sintetizar(texto, salida):
    r = subprocess.run([os.path.join(PIPER_DIR, 'piper'), '--model', MODELO, '--espeak_data', ESPEAK,
                        '--sentence_silence', '0.3', '--output_file', salida],
                       input=normalizar_tts(texto).encode('utf-8'), capture_output=True)
    if r.returncode != 0 or not os.path.exists(salida):
        raise RuntimeError('Piper falló: ' + r.stderr.decode('utf-8', 'ignore')[-300:])
    return leer_wav(salida)


def leer_wav(ruta):
    with wave.open(ruta) as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    return x, sr
