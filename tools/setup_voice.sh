#!/usr/bin/env bash
# One-time setup on a fresh machine: Telugu TTS voice + Whisper speech check (used by validate.py).
set -e
pip install --break-system-packages -q playwright coqui-tts torch torchaudio torchcodec sherpa-onnx 2>&1 | grep -v WARNING || true
if [ ! -f /opt/indictts/te/fastpitch/best_model.pth ]; then
  mkdir -p /opt/indictts && cd /opt/indictts
  curl -sS -L -o te.zip "https://github.com/AI4Bharat/Indic-TTS/releases/download/v1-checkpoints-release/te.zip"
  unzip -q -o te.zip && rm -f te.zip
fi
if [ ! -f /opt/asr/sherpa-onnx-whisper-turbo/turbo-tokens.txt ]; then
  mkdir -p /opt/asr && cd /opt/asr
  curl -sS -L -o turbo.tar.bz2 "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-turbo.tar.bz2"
  tar xjf turbo.tar.bz2 && rm -f turbo.tar.bz2
fi
if [ ! -f /opt/knnvc/prematch_g_02500000.pt ]; then
  mkdir -p /opt/knnvc && cd /opt/knnvc
  [ -d code ] || git clone -q --depth 1 https://github.com/bshall/knn-vc code
  curl -sS -L -o WavLM-Large.pt "https://github.com/bshall/knn-vc/releases/download/v0.1/WavLM-Large.pt"
  curl -sS -L -o prematch_g_02500000.pt "https://github.com/bshall/knn-vc/releases/download/v0.1/prematch_g_02500000.pt"
fi
echo "voice setup OK"
