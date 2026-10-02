"""Ghep 3 hang anh de so: Veo mau · LTX t2v · LTX i2v (+ anh mau i2v)."""
import subprocess, sys, tempfile, os
from pathlib import Path
from PIL import Image, ImageDraw

GOC = Path(__file__).resolve().parent.parent
FF = str(GOC / "cong_cu" / "bin" / "ffmpeg")
RONG = 1500

def dai(mp4, n=4):
    """n khung rai deu, ghep ngang."""
    ra = tempfile.mktemp(suffix=".png")
    import json
    tong = int(subprocess.run([str(GOC/"cong_cu"/"bin"/"ffprobe"), "-v", "error", "-select_streams", "v:0",
        "-count_frames", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", mp4],
        capture_output=True, text=True).stdout.strip() or 100)
    chon = "+".join(f"eq(n\\,{int((i+0.5)*tong/n)})" for i in range(n))
    subprocess.run([FF, "-v", "error", "-y", "-i", mp4, "-vf",
                    f"select='{chon}',scale={RONG//n}:-1,tile={n}x1", "-frames:v", "1", ra], check=True)
    im = Image.open(ra).convert("RGB").copy(); os.unlink(ra); return im

hang = [("VEO (video mau cua ban)", dai(str(next((GOC/"vao").glob("People_walking*.mp4"))))),
        ("LTX T2V - tu ve tu chu", dai(str(GOC/"ra/clip/collage_t2v.mp4"))),
        ("LTX I2V - tu anh LTX sinh ra", dai(str(GOC/"ra/clip/collage_i2v.mp4")))]
nh = 30
H = sum(h.height + nh for _, h in hang)
out = Image.new("RGB", (RONG, H), "white"); d = ImageDraw.Draw(out); y = 0
for ten, im in hang:
    d.text((10, y + 9), ten, fill="black"); out.paste(im, (0, y + nh)); y += im.height + nh
dich = GOC / "logs/kiem/so/collage_veo_t2v_i2v.png"
out.save(dich); print("->", dich.relative_to(GOC), out.size)
