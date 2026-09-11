import json, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
PROJ = Path("OpenMontage/projects/evs-lesson-8")
ART = PROJ/"artifacts"; ASSET=PROJ/"assets/video/scenes"; PILOT=PROJ/"renders/pilot/s01-water-animals-h3.mp4"
TMP=PROJ/"renders/compose_tmp"; OUT=PROJ/"renders/final_render.mp4"; REPORT=PROJ/"renders/render_report.json"
TMP.mkdir(parents=True,exist_ok=True)
FONT="C:/Windows/Fonts/arialbd.ttf"
def sh(cmd):
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode!=0: raise RuntimeError("FAILED: "+" ".join(cmd)+chr(10)+r.stderr[-1500:])
def dur(p):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(p)],capture_output=True,text=True,check=True)
    return float(r.stdout.strip())
def clips_for(sid):
    d=ASSET/sid
    if not d.exists(): return []
    return [c for c in sorted(d.glob(sid+"-*.mp4")) if c.stat().st_size>100000]
def norm_long(src,dsec,out):
    one=TMP/(out.stem+"_one.mp4")
    sh(["ffmpeg","-y","-i",str(src),"-vf","scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=30,format=yuv420p","-c:v","libx264","-crf","20","-preset","veryfast","-pix_fmt","yuv420p","-an",str(one)])
    n=max(1,int(dsec//dur(one))+1)
    lst=TMP/(out.stem+"_loop.txt")
    lst.write_text(chr(10).join(["file '"+one.resolve().as_posix()+"'"]*n),encoding="utf-8")
    sh(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-vf","trim=duration="+str(dsec)+",setpts=PTS-STARTPTS,fps=30","-c:v","libx264","-crf","20","-preset","veryfast","-pix_fmt","yuv420p","-an",str(out)])
COLORS=[(41,98,255),(46,139,87),(0,150,150),(128,0,128),(220,120,20),(150,90,40),(110,130,30),(20,40,120),(130,30,30),(30,110,60),(200,90,150),(60,60,160),(70,160,220),(200,40,40),(190,150,20),(0,130,140)]
def card(sid,label,text,dsec,out,idx):
    img=Image.new("RGB",(1920,1080),COLORS[idx%len(COLORS)])
    dr=ImageDraw.Draw(img)
    f1=ImageFont.truetype(FONT,90); f2=ImageFont.truetype(FONT,44)
    dr.text((960,300),sid.upper(),font=f1,anchor="mm",fill="white",stroke_width=3,stroke_fill="black")
    dr.text((960,430),label,font=f2,anchor="mm",fill="white",stroke_width=2,stroke_fill="black")
    words=text.split(); lines=[]; cur=""
    for w in words:
        t=(cur+" "+w).strip()
        if dr.textlength(t,font=f2)>1500: lines.append(cur); cur=w
        else: cur=t
    lines.append(cur)
    y=600
    for ln in lines[:4]:
        dr.text((960,y),ln,font=f2,anchor="mm",fill="white",stroke_width=2,stroke_fill="black"); y+=70
    png=TMP/(sid+"_card.png"); img.save(str(png))
    sh(["ffmpeg","-y","-loop","1","-i",str(png),"-vf","scale=1920:1080,setsar=1,fps=30,trim=duration="+str(dsec)+",setpts=PTS-STARTPTS,format=yuv420p","-c:v","libx264","-crf","20","-preset","veryfast","-pix_fmt","yuv420p","-an",str(out)])
def sts(s):
    ms=int(round(s*1000)); h,r=divmod(ms,3600000); m,r=divmod(r,60000); s,ms=divmod(r,1000)
    return "%02d:%02d:%02d,%03d"%(h,m,s,ms)
script=json.loads((ART/"script.json").read_text(encoding="utf-8"))
nar=json.loads((ART/"narration_manifest.json").read_text(encoding="utf-8"))
infos=[]; paths=[]
for k,sec in enumerate(script["sections"]):
    sid=sec["id"]; label=sec["label"]; target=sec["end_seconds"]-sec["start_seconds"]
    seg=TMP/("seg_"+sid+".mp4")
    found=clips_for(sid)
    if found:
        use=found[:3]; per=target/len(use); parts=[]
        for i,c in enumerate(use):
            p=TMP/(sid+"_p%d.mp4"%i); norm_long(c,per,p); parts.append(p)
        lst=TMP/(sid+"_list.txt")
        lst.write_text(chr(10).join("file '"+p.resolve().as_posix()+"'" for p in parts),encoding="utf-8")
        sh(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(seg)])
        src="real:"+",".join(c.name for c in use)
    elif PILOT.exists():
        norm_long(PILOT,target,seg); src="pilot-h3"
    else:
        tmpc=TMP/(sid+"_cover.mp4"); card(sid,label,sec["text"],target,tmpc,k); sh(["ffmpeg","-y","-i",str(tmpc),"-c","copy",str(seg)]); src="cover"
    d=dur(seg)
    assert abs(d-target)<1.0, (sid,d,target)
    infos.append({"section":sid,"source":src,"target_s":target,"actual_s":round(d,2)})
    paths.append(seg)
    print(sid+": "+src+" %.1f/%.0f"%(d,target),flush=True)
full=TMP/"video_track.mp4"
lst=TMP/"all_list.txt"
lst.write_text(chr(10).join("file '"+p.resolve().as_posix()+"'" for p in paths),encoding="utf-8")
sh(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(full)])
print("video track: %.1fs (target 480)"%dur(full),flush=True)
total=script["total_duration_seconds"]
base=TMP/"base.wav"
sh(["ffmpeg","-y","-f","lavfi","-i","anullsrc=channel_layout=stereo:sample_rate=48000","-t",str(total),str(base)])
inputs=["ffmpeg","-y","-i",str(base)]; filters=[]; n=0
for sec in script["sections"]:
    sid=sec["id"]
    wav=next((s["audio_path"] for s in nar["segments"] if s["section_id"]==sid),None)
    fw=PROJ/wav
    if not wav or not fw.exists(): raise RuntimeError("narration missing "+sid)
    inputs+=["-i",str(fw)]; k=len(filters)+1
    filters.append("[%d:a]aformat=sample_fmts=fltp,adelay=%d:all=1[nar%d]"%(k,int(sec["start_seconds"]*1000),n)); n+=1
chain="".join("[nar%d]"%i for i in range(n))
filters.append("[0:a]"+chain+"amix=inputs=%d:normalize=0[am]"%(n+1))
mix=TMP/"mix.wav"
sh(inputs+["-filter_complex",";".join(filters),"-map","[am]","-ac","2","-ar","48000","-c:a","pcm_s16le",str(mix)])
norm=TMP/"mix_norm.wav"
sh(["ffmpeg","-y","-i",str(mix),"-af","loudnorm=I=-14:TP=-1.5:LRA=11","-ar","48000","-ac","2","-c:a","pcm_s16le",str(norm)])
nosub=OUT.with_name("final_nosub.mp4")
sh(["ffmpeg","-y","-i",str(full),"-i",str(norm),"-map","0:v","-map","1:a","-c:v","copy","-c:a","aac","-b:a","192k","-movflags","+faststart",str(nosub)])
srt=TMP/"final.srt"; lines=[]
for i,sec in enumerate(script["sections"],1):
    lines+=[str(i),sts(sec["start_seconds"])+" --> "+sts(sec["end_seconds"]),sec["text"],""]
srt.write_text(chr(10).join(lines),encoding="utf-8")
print("SRT entries: "+str(len(script["sections"])),flush=True)
print("nosub: %.1fs"%dur(nosub),flush=True)
REPORT.write_text(json.dumps({"version":"1.0","project_id":"evs-lesson-8","output":str(OUT),"duration_seconds":round(dur(nosub),2),"spec":{"resolution":"1920x1080","fps":30},"sections":infos,"subtitles":str(srt)},indent=2),encoding="utf-8")
print("STAGE1 OK",flush=True)
