# =============================================================
# screens/intro_video.py (audio now respects SFX master volume)
# =============================================================

import os, pygame
import settings as S
from systems import audio as audio_sys  # <-- NEW

def _video_paths_for_class(cls_key: str):
    base = os.path.join("Assets", "Map")
    k = (cls_key or "").lower()
    vid = {"barbarian": "BarbarianV.mp4", "druid": "DruidV.mp4", "rogue": "RogueV.mp4"}.get(k)
    if not vid: return None, None
    vid = os.path.join(base, vid)
    if not os.path.exists(vid): vid = None
    if not vid: return None, None
    aud_mp3 = os.path.splitext(vid)[0] + ".mp3"
    aud_wav = os.path.splitext(vid)[0] + ".wav"
    audio_path = aud_mp3 if os.path.exists(aud_mp3) else (aud_wav if os.path.exists(aud_wav) else None)
    return vid, audio_path

def enter(gs, **_):
    # initialize video object once
    if hasattr(gs, "_video"): return
    vid_path, aud_path = _video_paths_for_class(getattr(gs, "intro_class", None))
    if not vid_path:
        print("ℹ️ No intro video found; skipping to overworld.")
        gs._video = {"backend": None, "done": True}
        return

    # try moviepy
    try:
        import moviepy.editor as mpy
        clip = mpy.VideoFileClip(vid_path)
        fps = max(1, int(round(clip.fps or 24)))

        # --- AUDIO (mastered) ---
        snd = None
        if aud_path:
            try:
                snd = pygame.mixer.Sound(aud_path)
                audio_sys.play_sound(snd)  # honors SFX master volume
            except Exception as e:
                print(f"⚠️ Could not play audio '{aud_path}': {e}")

        frame_gen = clip.iter_frames(fps=fps, dtype="uint8")
        gs._video = {
            "backend":"moviepy","clip":clip,"fps":fps,"acc":0.0,
            "frame_gen":frame_gen,"frame_surf":None,"done":False,
            "snd": snd  # store Sound so we can .stop() on teardown
        }
        print(f"▶️ Intro ready (moviepy): {os.path.basename(vid_path)} ({'with audio' if snd else 'silent'}) @ {fps} fps")
        return
    except Exception as e:
        import sys
        print(f"ℹ️ MoviePy not available/failed ({e}). Python exe: {sys.executable}. Falling back to imageio…")

    # fallback imageio
    try:
        import imageio
        reader = imageio.get_reader(vid_path)
        meta = reader.get_meta_data() or {}
        fps = int(round(meta.get("fps", 24))) if meta.get("fps") else 24

        # --- AUDIO (mastered) ---
        snd = None
        if aud_path:
            try:
                snd = pygame.mixer.Sound(aud_path)
                audio_sys.play_sound(snd)  # honors SFX master volume
            except Exception as e:
                print(f"⚠️ Could not play audio '{aud_path}': {e}")

        gs._video = {
            "backend":"imageio","reader":iter(reader),"fps":max(1,fps),
            "acc":0.0,"frame_surf":None,"done":False,"_close":reader,
            "snd": snd
        }
        print(f"▶️ Intro ready (imageio): {os.path.basename(vid_path)} ({'with audio' if snd else 'silent'}) @ {fps} fps")
    except Exception as e:
        print(f"⚠️ Failed to init video fallback: {e}")
        gs._video = {"backend":None,"done":True}

def _teardown(gs):
    v = getattr(gs, "_video", None)
    if not v: return
    try:
        # stop any audio playback for this intro
        if v.get("snd"):
            try: v["snd"].stop()
            except Exception: pass

        if v.get("backend") == "moviepy":
            if v.get("clip"): v["clip"].close()
        elif v.get("backend") == "imageio":
            closer = v.get("_close")
            if hasattr(closer, "close"): closer.close()
    except Exception:
        pass
    finally:
        try: delattr(gs, "_video")
        except Exception: pass

def handle(events, gs, dt, **_):
    v = getattr(gs, "_video", None)
    if not v or v.get("done"):
        _teardown(gs)
        return S.MODE_GAME
    for e in events:
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
            _teardown(gs)
            return S.MODE_GAME
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            _teardown(gs)
            return S.MODE_GAME
    return None

def draw(screen, gs, dt, **_):
    screen.fill((0, 0, 0))
    v = getattr(gs, "_video", None)
    if not v or v.get("done"):
        _teardown(gs)
        return
    step = 1.0 / max(1e-6, v["fps"])
    v["acc"] += dt
    while v["acc"] >= step and not v["done"]:
        v["acc"] -= step
        try:
            if v.get("backend") == "moviepy":
                frame = next(v["frame_gen"])
            else:
                frame = next(v["reader"])
            import numpy as np
            frame = np.swapaxes(frame, 0, 1)
            v["frame_surf"] = pygame.surfarray.make_surface(frame)
        except StopIteration:
            v["done"] = True
            break
        except Exception as e:
            print(f"[video] frame error: {e}")
            v["done"] = True
            break
    if v.get("frame_surf"):
        fw, fh = v["frame_surf"].get_width(), v["frame_surf"].get_height()
        sw, sh = S.WIDTH, S.HEIGHT
        scale = min(sw / fw, sh / fh)
        tw, th = max(1, int(fw * scale)), max(1, int(fh * scale))
        scaled = pygame.transform.smoothscale(v["frame_surf"], (tw, th))
        rect = scaled.get_rect(center=(sw // 2, sh // 2))
        screen.blit(scaled, rect)
