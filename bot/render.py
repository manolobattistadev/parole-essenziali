"""Genera la grafica (1080x1350) e il reel (1080x1920) dell'aforisma."""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .core import FONTS

NERO = (0, 0, 0)
BIANCO = (255, 255, 255)
GRIGIO = (140, 140, 140)

FONT_TESTO = FONTS / "PlayfairDisplay.ttf"
FONT_FIRMA = FONTS / "PlayfairDisplay-Italic.ttf"

# Accordi tenui per il sottofondo sintetizzato (frequenze in Hz): nessun diritto d'autore.
ACCORDI = [
    [110.00, 164.81, 220.00, 261.63, 329.63],  # La minore
    [98.00, 146.83, 196.00, 246.94, 293.66],   # Sol maggiore
    [87.31, 130.81, 174.61, 220.00, 261.63],   # Fa maggiore
    [130.81, 196.00, 261.63, 329.63, 392.00],  # Do maggiore
    [73.42, 110.00, 146.83, 174.61, 220.00],   # Re minore
    [82.41, 123.47, 164.81, 196.00, 246.94],   # Mi minore
]


def _wrap(draw: ImageDraw.ImageDraw, testo: str, font, larghezza: int) -> list[str]:
    righe, riga = [], ""
    for parola in testo.split():
        prova = f"{riga} {parola}".strip()
        if draw.textlength(prova, font=font) <= larghezza or not riga:
            riga = prova
        else:
            righe.append(riga)
            riga = parola
    if riga:
        righe.append(riga)
    return righe


def disegna(aforisma: dict, firma: str, w: int, h: int, scala: int = 1,
            dimensione: float = 1.0) -> Image.Image:
    """Testo bianco centrato su fondo nero; la dimensione del font si adatta alla lunghezza.
    `dimensione` scala il corpo del testo (1.0 = default, 0.8 = più piccolo)."""
    W, H = w * scala, h * scala
    img = Image.new("RGB", (W, H), NERO)
    d = ImageDraw.Draw(img)

    margine = int(W * 0.13)
    box_w = W - 2 * margine
    box_h = int(min(H * 0.62, W * 1.0))
    testo = aforisma["testo"]

    size = int(84 * scala * dimensione)
    minimo = int(36 * scala * dimensione)
    while True:
        font = ImageFont.truetype(str(FONT_TESTO), size)
        righe = _wrap(d, testo, font, box_w)
        interl = int(size * 1.42)
        alt = interl * len(righe)
        if alt <= box_h or size <= minimo:
            break
        size -= 2 * scala

    autore = aforisma.get("autore")
    font_aut = ImageFont.truetype(str(FONT_FIRMA), int(size * 0.55))
    extra = int(size * 1.6) if autore else 0

    y = (H - alt - extra) // 2
    for r in righe:
        rw = d.textlength(r, font=font)
        d.text(((W - rw) / 2, y), r, font=font, fill=BIANCO)
        y += interl

    if autore:
        a = f"— {autore}"
        d.text(((W - d.textlength(a, font=font_aut)) / 2, y + int(size * 0.6)), a, font=font_aut, fill=GRIGIO)

    if firma:
        ff = ImageFont.truetype(str(FONT_FIRMA), 30 * scala)
        fw = d.textlength(firma, font=ff)
        d.text(((W - fw) / 2, H - int(H * (0.14 if H > W * 1.5 else 0.07))), firma, font=ff, fill=GRIGIO)

    return img


def immagine_post(aforisma: dict, firma: str, dest: Path, dimensione: float = 1.0) -> Path:
    img = disegna(aforisma, firma, 1080, 1350, dimensione=dimensione)
    img.save(dest, "JPEG", quality=95, subsampling=0)
    return dest


def immagine_storia(aforisma: dict, firma: str, dest: Path) -> Path:
    img = disegna(aforisma, firma, 1080, 1920)
    img.save(dest, "JPEG", quality=95, subsampling=0)
    return dest


def reel(aforisma: dict, firma: str, dest: Path, durata: float = 9, zoom: float = 1.06,
         audio: bool = True, lavoro: Path | None = None) -> Path:
    """Video 9:16: dissolvenza in entrata/uscita e lento zoom, con sottofondo sintetizzato."""
    lavoro = lavoro or dest.parent
    fps = 30
    frames = int(durata * fps)
    frame = lavoro / "reel_frame.png"
    # Disegnato a risoluzione doppia: lo zoom resta fluido senza scatti.
    disegna(aforisma, firma, 1080, 1920, scala=2).save(frame)

    vf = (
        f"zoompan=z='1+({zoom}-1)*on/{frames}':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps},"
        f"fade=t=in:st=0:d=1.6,fade=t=out:st={durata - 1.4}:d=1.4,format=yuv420p"
    )
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(fps), "-i", str(frame)]

    if audio:
        note = ACCORDI[aforisma["id"] % len(ACCORDI)]
        # Pad morbido: somma di sinusoidi con un lieve tremolo, filtrato e sfumato.
        voci = "+".join(
            f"{0.9 / (i + 1):.3f}*sin(2*PI*{f}*t)*(0.75+0.25*sin(2*PI*{0.11 + i * 0.07:.2f}*t))"
            for i, f in enumerate(note)
        )
        expr = f"0.12*({voci})"
        cmd += ["-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:c=stereo:d={durata}"]
        af = (
            f"lowpass=f=1800,aecho=0.8:0.7:120|240:0.25|0.15,"
            f"afade=t=in:st=0:d=2,afade=t=out:st={durata - 2}:d=2,volume=0.9"
        )
        cmd += ["-filter:a", af, "-c:a", "aac", "-b:a", "128k", "-ar", "44100"]

    cmd += [
        "-vf", vf, "-t", str(durata), "-c:v", "libx264", "-profile:v", "high", "-preset", "medium",
        "-crf", "18", "-r", str(fps), "-movflags", "+faststart", "-shortest", str(dest),
    ]
    subprocess.run(cmd, check=True)
    frame.unlink(missing_ok=True)
    return dest
