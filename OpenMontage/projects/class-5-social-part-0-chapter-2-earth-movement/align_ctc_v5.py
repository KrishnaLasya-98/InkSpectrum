"""Force-align approved audio to its exact script using local CTC Viterbi.

Uses cached emissions on reruns. Every word carries alignment provenance.
Punctuation is retained for display. No interpolation of unrecognized words.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from copy import deepcopy
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

from tools.analysis.narration_text_syncer import _build_word_captions, _build_formatted_srt

PROJECT = Path(__file__).resolve().parent
REPO = PROJECT.parents[1]
OUT = PROJECT / "artifacts/alignment-ctc-v5"
MODEL = "facebook/wav2vec2-base-960h"
NUMBER = {"2": "two", "5": "five", "24": "twenty four", "23.5°": "twenty three point five degrees", "22": "twenty two", "21": "twenty one", "23": "twenty three", "56": "fifty six", "1,670": "one thousand six hundred and seventy", "21st": "twenty first", "23rd": "twenty third", "365¼": "three hundred and sixty five and one quarter", "365": "three hundred and sixty five"}


def transcript_tokens(text, vocab):
    tokens, owners = [], []
    words = text.split()
    for wi, word in enumerate(words):
        normal = NUMBER.get(word.strip('.,;:()'), word).upper().replace('’', "'")
        if any(c.isdigit() for c in normal):
            raise ValueError(f'Numeric narration needs an explicit pronunciation: {word}')
        normal = re.sub(r"[^A-Z' ]", "", normal)
        if not normal:
            continue  # punctuation-only dash gets no guessed speech interval
        if tokens:
            tokens.append(vocab['|']); owners.append(None)
        for char in normal.replace(' ', '|'):
            if char in vocab:
                tokens.append(vocab[char]); owners.append(wi)
    return words, np.asarray(tokens, dtype=np.int32), owners


def viterbi(logp, tokens, blank):
    """Proper CTC path with blanks between repeated adjacent characters."""
    states = np.full(2 * len(tokens) + 1, blank, np.int32)
    states[1::2] = tokens
    skip = np.zeros(len(states), bool)
    skip[2:] = (states[2:] != blank) & (states[2:] != states[:-2])
    prev = np.full(len(states), -np.inf, np.float32)
    prev[0] = 0
    trace = np.zeros((len(logp), len(states)), np.uint8)
    for t, emission in enumerate(logp):
        one = np.r_[-np.inf, prev[:-1]]
        two = np.r_[-np.inf, -np.inf, prev[:-2]]
        two[~skip] = -np.inf
        choice = np.stack((prev, one, two)).argmax(axis=0)
        trace[t] = choice
        prev = np.maximum(np.maximum(prev, one), two) + emission[states]
    state = len(states) - 1 if prev[-1] >= prev[-2] else len(states) - 2
    if not np.isfinite(prev[state]):
        raise ValueError("No finite CTC path for transcript")
    frames = [[] for _ in tokens]
    for t in range(len(logp) - 1, -1, -1):
        if state % 2:
            frames[state // 2].append(t)
        state -= int(trace[t, state])
    if any(not v for v in frames):
        raise ValueError("CTC path omitted transcript characters")
    return frames


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--section')
    args = p.parse_args()
    torch.set_num_threads(4)
    torch.set_num_interop_threads(2)
    OUT.mkdir(parents=True, exist_ok=True)
    cache = REPO / '.cache/alignment'
    processor = Wav2Vec2Processor.from_pretrained(MODEL, cache_dir=cache, token=False)
    model = Wav2Vec2ForCTC.from_pretrained(MODEL, cache_dir=cache, token=False).eval()
    vocab = processor.tokenizer.get_vocab()
    manifest = json.loads((PROJECT / 'assets/audio/narration-elevenlabs-title-pause-v4/narration_manifest.json').read_text(encoding='utf-8'))
    old = json.loads((PROJECT / 'artifacts/alignment-elevenlabs-title-pause-v4/narration_aligned.json').read_text(encoding='utf-8'))
    lookup = {s['section_id']: s for s in old['segments']}
    segments = []
    audit = []
    for s in manifest['segments']:
        sid = s['section_id']
        if args.section and args.section != sid:
            continue
        audio_path = Path(s['audio_path'])
        digest = hashlib.sha256(audio_path.read_bytes()).hexdigest()
        emission_path = OUT / f'{sid}-{digest[:12]}.emission.npz'
        if emission_path.exists():
            data = np.load(emission_path)
            logp, seconds = data['logp'], float(data['seconds'])
        else:
            audio, sr = sf.read(audio_path, dtype='float32')
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            seconds = len(audio) / sr
            if sr != 16000:
                decoded = subprocess.run(['ffmpeg','-v','error','-i',str(audio_path),'-ar','16000','-ac','1','-f','f32le','pipe:1'], capture_output=True, check=True, timeout=60)
                audio = np.frombuffer(decoded.stdout, dtype=np.float32).copy()
            inputs = processor(audio, sampling_rate=16000, return_tensors='pt')
            with torch.inference_mode():
                logp = model(inputs.input_values).logits[0].log_softmax(-1).cpu().numpy()
            np.savez_compressed(emission_path, logp=logp, seconds=seconds)
        words, tokens, owners = transcript_tokens(s['text'], vocab)
        frames = viterbi(logp, tokens, model.config.pad_token_id)
        step = seconds / len(logp)
        by_word = {}
        for ti, wi in enumerate(owners):
            if wi is not None:
                by_word.setdefault(wi, []).extend(frames[ti])
        offset = float(s['start_seconds'])
        aligned_words = []
        for wi, word in enumerate(words):
            if wi not in by_word:
                # Attach punctuation to the preceding token, never fabricate timing.
                if aligned_words:
                    aligned_words[-1]['word'] += ' ' + word
                continue
            spans = by_word[wi]
            relevant = [ti for ti, owner in enumerate(owners) if owner == wi]
            scores = [float(logp[t, tokens[ti]]) for ti in relevant for t in frames[ti]]
            aligned_words.append({'word':word, 'start_ms':round((offset + min(spans)*step)*1000), 'end_ms':round((offset + (max(spans)+1)*step)*1000), 'timing_basis':'ctc_forced_alignment', 'mean_log_probability':round(float(np.mean(scores)),4)})
        result = deepcopy(lookup[sid]); result['words'] = aligned_words
        result['alignment_method'] = 'wav2vec2_ctc_viterbi'
        segments.append(result)
        audit.append({'section_id':sid, 'words':len(aligned_words), 'duration':seconds, 'low_score_words':[w for w in aligned_words if w['mean_log_probability'] < -2.5]})
        (OUT / f'{sid}.aligned.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n',encoding='utf-8')
        print(f'{sid}: {len(aligned_words)} words aligned acoustically', flush=True)
    if not args.section:
        (OUT / 'narration_aligned.json').write_text(json.dumps({'segments':segments,'method':'wav2vec2_ctc_viterbi'},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        (OUT / 'word_captions.json').write_text(json.dumps(_build_word_captions(segments),indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        (OUT / 'formatted_subtitles.srt').write_text(_build_formatted_srt(segments),encoding='utf-8')
    (OUT / ('audit-'+(args.section or 'all')+'.json')).write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
