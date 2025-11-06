# =============================================================
# screens/intro_video.py (robust, exe-safe, no auto-skip)
# • Keeps your original flow (moviepy -> imageio fallback)
# • Honors SFX master volume via audio_sys.play_sound
# • Uses resource_path so assets load in PyInstaller
# • Auto-detects a class video if gs.intro_class is missing
# • Flushes stale input on enter() to prevent instant skip
# =============================================================

import os, pygame
import settings as S
from systems import audio as audio_sys
from utils_resource import resource_path  # <-- exe-safe asset resolver

# Try imports up-front so we can log cleanly
try:
    import moviepy.editor as mpy
except Exception:
    mpy = None

try:
    import imageio
except Exception:
    imageio = None

try:
    import numpy as np
except Exception:
    np = None  # draw() will guard

COMMON_EXTS = (".mp4", ".mov", ".webm", ".avi", ".mkv")

def _resolve_existing(path_rel: str) -> str | None:
    """
    Resolve a relative asset path through resource_path and confirm it exists.
    """
    abs_path = resource_path(path_rel)
    return abs_path if os.path.exists(abs_path) else None

def _auto_detect_first_video() -> str | None:
    """
    If gs.intro_class is not set, try to find the first existing class video
    under Assets/Map with common extensions.
    """
    folder = os.path.join("Assets", "Map")
    for stem in ("BarbarianV", "DruidV", "RogueV"):
        for ext in COMMON_EXTS:
            p = _resolve_existing(os.path.join(folder, stem + ext))
            if p:
                return p
    return None

def _video_paths_for_class(cls_key: str | None):
    """
    Return (video_abs_path, audio_abs_path_or_None)
    Uses resource_path so it works in dev + PyInstaller.
    Falls back to auto-detect when cls_key is missing.
    """
    base = os.path.join("Assets", "Map")
    k = (cls_key or "").lower().strip()

    # Map known classes -> file stem
    stem = {"barbarian": "BarbarianV", "druid": "DruidV", "rogue": "RogueV"}.get(k)

    # If no class chosen, attempt auto-detect
    if not stem:
        vid_abs = _auto_detect_first_video()
        if not vid_abs:
            return None, None
        root, _ = os.path.splitext(vid_abs)
        aud_mp3 = root + ".mp3"
        aud_wav = root + ".wav"
        audio_abs = aud_mp3 if os.path.exists(aud_mp3) else (aud_wav if os.path.exists(aud_wav) else None)
        return vid_abs, audio_abs

    # Build preferred .mp4, but accept any known ext if .mp4 missing
    preferred = _resolve_existing(os.path.join(base, stem + ".mp4"))
    if not preferred:
        # Try other extensions
        for ext in COMMON_EXTS:
            p = _resolve_existing(os.path.join(base, stem + ext))
            if p:
                preferred = p
                break

    if not preferred:
        return None, None

    root, _ = os.path.splitext(preferred)
    aud_mp3 = root + ".mp3"
    aud_wav = root + ".wav"
    audio_abs = aud_mp3 if os.path.exists(aud_mp3) else (aud_wav if os.path.exists(aud_wav) else None)
    return preferred, audio_abs

def enter(gs, **_):
    # Already initialized?
    if hasattr(gs, "_video"):
        return

    # Prevent instant skip from stale input (e.g., you pressed Enter to reach this screen)
    try:
        pygame.event.clear()
    except Exception:
        pass

    # Ensure mixer is ready (quietly try)
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    except Exception as e:
        print(f"[intro_video] mixer init warn: {e}")

    vid_path, aud_path = _video_paths_for_class(getattr(gs, "intro_class", None))
    if not vid_path:
        print("ℹ️ No intro video found; skipping to overworld.")
        gs._video = {"backend": None, "done": True}
        return

    # --- BACKEND 1: MoviePy ---
    if mpy is not None:
        try:
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
                "backend": "moviepy",
                "clip": clip,
                "fps": fps,
                "acc": 0.0,
                "frame_gen": frame_gen,
                "frame_surf": None,
                "done": False,
                "snd": snd
            }
            print(f"▶️ Intro ready (moviepy): {os.path.basename(vid_path)} ({'with audio' if snd else 'silent'}) @ {fps} fps")
            return
        except Exception as e:
            print(f"ℹ️ MoviePy failed ({e}). Falling back to imageio…")

    # --- BACKEND 2: imageio ---
    if imageio is not None:
        try:
            reader = imageio.get_reader(vid_path)
            meta = reader.get_meta_data() or {}
            fps = int(round(meta.get("fps", 24))) if meta.get("fps") else 24

            snd = None
            if aud_path:
                try:
                    snd = pygame.mixer.Sound(aud_path)
                    audio_sys.play_sound(snd)
                except Exception as e:
                    print(f"⚠️ Could not play audio '{aud_path}': {e}")

            gs._video = {
                "backend": "imageio",
                "reader": iter(reader),
                "fps": max(1, fps),
                "acc": 0.0,
                "frame_surf": None,
                "done": False,
                "_close": reader,
                "snd": snd
            }
            print(f"▶️ Intro ready (imageio): {os.path.basename(vid_path)} ({'with audio' if snd else 'silent'}) @ {fps} fps")
            return
        except Exception as e:
            print(f"⚠️ Failed to init imageio fallback: {e}")

    # --- If both backends failed ---
    gs._video = {"backend": None, "done": True}

def _teardown(gs):
    v = getattr(gs, "_video", None)
    if not v:
        return
    try:
        # stop any audio playback for this intro
        if v.get("snd"):
            try:
                v["snd"].stop()
            except Exception:
                pass

        if v.get("backend") == "moviepy":
            if v.get("clip"):
                try:
                    v["clip"].close()
                except Exception:
                    pass
        elif v.get("backend") == "imageio":
            closer = v.get("_close")
            if hasattr(closer, "close"):
                try:
                    closer.close()
                except Exception:
                    pass
    except Exception:
        pass
    finally:
        try:
            delattr(gs, "_video")
        except Exception:
            pass

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
    if np is None:
        print("[intro_video] numpy missing; cannot render frames.")
        v["done"] = True
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

            # moviepy/imageio frames are (H, W, 3/4); pygame wants (W, H, ...)
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
        sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
        scale = min(sw / fw, sh / fh)
        tw, th = max(1, int(fw * scale)), max(1, int(fh * scale))
        scaled = pygame.transform.smoothscale(v["frame_surf"], (tw, th))
        rect = scaled.get_rect(center=(sw // 2, sh // 2))
        screen.blit(scaled, rect)
