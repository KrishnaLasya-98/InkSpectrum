"""Acoustic CTC alignment of exact narration, preserving punctuation.

CPU bounded, emission-cached, no interpolated word fallback. Public model
weights are shared in the repository cache; audio remains chapter-specific.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
from lib.production_runtime import atomic_json
from tools.analysis.narration_text_syncer import _build_word_captions,_build_formatted_srt

MODEL='facebook/wav2vec2-base-960h'
NORMAL={'3':'three','5':'five','24':'twenty four','30':'thirty','80':'eighty','159.3°F':'one hundred and fifty nine point three degrees fahrenheit','70.7°C':'seventy point seven degrees celsius'}

def tokens_for(text,vocab):
    words=text.split(); tokens=[];owners=[]
    for wi,word in enumerate(words):
        raw=word.strip('.,;:()!?')
        normalized=NORMAL.get(raw,word).upper().replace('’',"'")
        if any(c.isdigit() for c in normalized):raise ValueError(f'Explicit numeric pronunciation needed: {word}')
        normalized=re.sub(r"[^A-Z' ]",'',normalized)
        if not normalized:continue
        if tokens:tokens.append(vocab['|']);owners.append(None)
        for char in normalized.replace(' ','|'):
            if char in vocab:tokens.append(vocab[char]);owners.append(wi)
    return words,np.asarray(tokens,dtype=np.int32),owners

def viterbi(logp,tokens,blank):
    states=np.full(2*len(tokens)+1,blank,np.int32);states[1::2]=tokens
    skip=np.zeros(len(states),bool);skip[2:]=(states[2:]!=blank)&(states[2:]!=states[:-2])
    previous=np.full(len(states),-np.inf,np.float32);previous[0]=0
    trace=np.zeros((len(logp),len(states)),np.uint8)
    for t,emission in enumerate(logp):
        one=np.r_[-np.inf,previous[:-1]];two=np.r_[-np.inf,-np.inf,previous[:-2]];two[~skip]=-np.inf
        trace[t]=np.stack((previous,one,two)).argmax(axis=0)
        previous=np.maximum(np.maximum(previous,one),two)+emission[states]
    state=len(states)-1 if previous[-1]>=previous[-2] else len(states)-2
    if not np.isfinite(previous[state]):raise ValueError('No finite alignment path')
    frames=[[] for _ in tokens]
    for t in range(len(logp)-1,-1,-1):
        if state%2:frames[state//2].append(t)
        state-=int(trace[t,state])
    if any(not f for f in frames):raise ValueError('Alignment omitted characters')
    return frames

def align(manifest_path:Path,out:Path,repo:Path):
    torch.set_num_threads(4);torch.set_num_interop_threads(2)
    out.mkdir(parents=True,exist_ok=True)
    processor=Wav2Vec2Processor.from_pretrained(MODEL,cache_dir=repo/'.cache/alignment',token=False,local_files_only=True)
    model=Wav2Vec2ForCTC.from_pretrained(MODEL,cache_dir=repo/'.cache/alignment',token=False,local_files_only=True).eval()
    vocab=processor.tokenizer.get_vocab();manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if not manifest.get('generation_complete'):raise ValueError('Narration generation incomplete')
    results=[];audit=[]
    for s in manifest['segments']:
        path=Path(s['audio_path']);digest=hashlib.sha256(path.read_bytes()).hexdigest();cache=out/f"{s['section_id']}-{digest[:12]}.emission.npz"
        if cache.exists():
            saved=np.load(cache);logp=saved['logp'];seconds=float(saved['seconds'])
        else:
            samples,sr=sf.read(path,dtype='float32');seconds=len(samples)/sr
            if samples.ndim>1:samples=samples.mean(axis=1)
            if sr!=16000:
                decoded=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-ar','16000','-ac','1','-f','f32le','pipe:1'],capture_output=True,check=True,timeout=60)
                samples=np.frombuffer(decoded.stdout,dtype=np.float32).copy()
            inputs=processor(samples,sampling_rate=16000,return_tensors='pt')
            with torch.inference_mode():logp=model(inputs.input_values).logits[0].log_softmax(-1).cpu().numpy()
            np.savez_compressed(cache,logp=logp,seconds=seconds)
        words,tokens,owners=tokens_for(s['text'],vocab);frames=viterbi(logp,tokens,model.config.pad_token_id);step=seconds/len(logp)
        grouped={}
        for ti,wi in enumerate(owners):
            if wi is not None:grouped.setdefault(wi,[]).extend(frames[ti])
        offset=s['start_seconds'];aligned=[]
        for wi,word in enumerate(words):
            if wi not in grouped:
                if aligned:aligned[-1]['word']+=' '+word
                continue
            spans=grouped[wi];scores=[float(logp[t,tokens[ti]]) for ti,owner in enumerate(owners) if owner==wi for t in frames[ti]]
            aligned.append({'word':word,'start_ms':round((offset+min(spans)*step)*1000),'end_ms':round((offset+(max(spans)+1)*step)*1000),'timing_basis':'ctc_forced_alignment','mean_log_probability':round(float(np.mean(scores)),4)})
        result={'section_id':s['section_id'],'text':s['text'],'start_ms':round(offset*1000),'end_ms':round((offset+seconds)*1000),'audio_path':str(path),'words':aligned,'alignment_method':'wav2vec2_ctc_viterbi'}
        results.append(result);audit.append({'section_id':s['section_id'],'audio_sha256':digest,'word_count':len(aligned),'low_score_words':[w for w in aligned if w['mean_log_probability'] < -2.5]})
        atomic_json(out/f"{s['section_id']}.aligned.json",result)
        print(f"{s['section_id']}: {len(aligned)} words aligned acoustically",flush=True)
    atomic_json(out/'narration_aligned.json',{'segments':results,'method':'wav2vec2_ctc_viterbi'})
    atomic_json(out/'word_captions.json',_build_word_captions(results))
    (out/'formatted_subtitles.srt').write_text(_build_formatted_srt(results),encoding='utf-8')
    atomic_json(out/'audit.json',audit)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    align(args.manifest,args.output,Path(__file__).resolve().parents[2])
