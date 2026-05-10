"""Generate synthetic test assets for KinetiX demo."""

from pathlib import Path
import numpy as np
import struct, wave, math

from moviepy import ColorClip, ImageClip as MImageClip

ASSETS = Path(__file__).resolve().parent.parent / "test_assets"


def gen_color_video(filename: str, color: tuple, duration: float = 3.0, fps: int = 30, size=(640, 360)):
    """Create a solid-color video clip."""
    clip = ColorClip(size=size, color=color, duration=duration)
    out = ASSETS / filename
    out.parent.mkdir(parents=True, exist_ok=True)
    clip.write_videofile(str(out), fps=fps, codec="libx264", audio=False)
    print(f"  → {out}")


def gen_image(filename: str, color: tuple, size=(200, 200)):
    """Create a solid-color PNG image."""
    from PIL import Image
    img = Image.new("RGB", size, color)
    out = ASSETS / filename
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out))
    print(f"  → {out}")


def gen_sine_wav(filename: str, duration: float = 10.0, freq: float = 440.0, sample_rate: int = 44100):
    """Create a simple sine-wave WAV file."""
    n_samples = int(duration * sample_rate)
    samples = []
    for i in range(n_samples):
        val = int(16000 * math.sin(2 * math.pi * freq * i / sample_rate))
        samples.append(struct.pack('<h', max(-32768, min(32767, val))))

    out = ASSETS / filename
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(samples))
    print(f"  → {out}")


if __name__ == "__main__":
    ASSETS.mkdir(parents=True, exist_ok=True)

    print("Generating test assets...")
    gen_color_video("video1.mp4", color=(40, 120, 200), duration=4.0)   # blue
    gen_color_video("video2.mp4", color=(200, 60, 60), duration=3.0)    # red
    gen_image("logo.png", color=(255, 200, 0), size=(150, 150))          # yellow square
    gen_sine_wav("bgm.wav", duration=12.0, freq=440.0)

    print("\nDone! Test assets in:", ASSETS)
