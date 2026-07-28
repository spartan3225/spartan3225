"""AI skeleton tracking for surf videos.

Pipeline per sampled frame:
  1. Person detection (MediaPipe EfficientDet-Lite0) — surfers are small in
     wide surf footage, so full-frame pose estimation fails. We detect the
     person bbox first (with temporal fallback to the previous bbox).
  2. Pose estimation (MediaPipe Pose, 33 landmarks) on the expanded crop.
  3. Landmarks mapped back to full-frame normalized coordinates.

Also derives coach metrics: speed proxy (hip-centre displacement) and
compression (knee angle) series used for the Speed/Compression graphs.

Everything is synchronous CPU work — callers must run it in a thread
(`asyncio.to_thread`) so the event loop stays free.
"""
from __future__ import annotations

import logging
import math
import time
from pathlib import Path

logger = logging.getLogger("surfai.pose")

DETECTOR_MODEL = Path(__file__).parent / "models_ai" / "efficientdet_lite0.tflite"

SAMPLE_FPS = 8.0          # target sampled frames per second
MAX_FRAMES = 240          # hard cap (~30s at 8fps)
MAX_SECONDS = 150         # wall-clock budget for the whole extraction
CROP_EXPAND = 0.65        # bbox expansion ratio for the pose crop
DETECT_EVERY = 3          # run person detection every Nth sampled frame

# Landmark indices (MediaPipe Pose)
L_SHOULDER, R_SHOULDER = 11, 12
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28


def _angle(a, b, c) -> float:
    """Angle ABC in degrees given (x, y) points."""
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(*v1) or 1e-6
    n2 = math.hypot(*v2) or 1e-6
    cosv = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cosv))


def extract_pose_data(video_path: str) -> dict:
    """Extract skeleton + metrics from a video. Returns a JSON-able dict."""
    import cv2  # local imports: heavy libs stay out of server startup
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    started = time.time()
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video {video_path}")

    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if native_fps <= 0 or native_fps > 240:
        native_fps = 30.0
    step = max(1, round(native_fps / SAMPLE_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720

    detector = vision.ObjectDetector.create_from_options(
        vision.ObjectDetectorOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(DETECTOR_MODEL)),
            score_threshold=0.22,
            category_allowlist=["person"],
            max_results=2,
        )
    )
    pose = mp.solutions.pose.Pose(
        static_image_mode=True,
        model_complexity=1,
        min_detection_confidence=0.25,
    )

    frames: list[dict] = []
    last_bbox = None  # (x1, y1, x2, y2) in px
    frame_idx = -1
    sampled = 0

    try:
        while True:
            ok = cap.grab()
            if not ok:
                break
            frame_idx += 1
            if frame_idx % step != 0:
                continue
            if sampled >= MAX_FRAMES or (time.time() - started) > MAX_SECONDS:
                break
            ok, bgr = cap.retrieve()
            if not ok:
                continue
            sampled += 1
            t = frame_idx / native_fps
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

            # --- person detection (every Nth frame, else reuse last bbox) ---
            if last_bbox is None or (sampled - 1) % DETECT_EVERY == 0:
                try:
                    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    dets = detector.detect(mp_img).detections
                except Exception:
                    dets = []
                if dets:
                    best = max(dets, key=lambda d: d.categories[0].score)
                    b = best.bounding_box
                    last_bbox = (b.origin_x, b.origin_y,
                                 b.origin_x + b.width, b.origin_y + b.height)
            if last_bbox is None:
                continue

            x1, y1, x2, y2 = last_bbox
            bw, bh = x2 - x1, y2 - y1
            ex, ey = int(bw * CROP_EXPAND), int(bh * CROP_EXPAND)
            cx1, cy1 = max(0, x1 - ex), max(0, y1 - ey)
            cx2, cy2 = min(width, x2 + ex), min(height, y2 + ey)
            if cx2 - cx1 < 20 or cy2 - cy1 < 20:
                continue
            crop = rgb[cy1:cy2, cx1:cx2]

            res = pose.process(crop)
            if not res.pose_landmarks:
                continue
            ch, cw = crop.shape[:2]
            kp = []
            visible = 0
            for lm in res.pose_landmarks.landmark:
                fx = (cx1 + lm.x * cw) / width
                fy = (cy1 + lm.y * ch) / height
                v = lm.visibility
                if v > 0.5:
                    visible += 1
                kp.append([round(fx, 4), round(fy, 4), round(v, 2)])
            if visible < 8:
                continue  # junk detection

            # Update bbox from the pose itself (tight tracking between detects)
            xs = [p[0] * width for p in kp if p[2] > 0.4]
            ys = [p[1] * height for p in kp if p[2] > 0.4]
            if xs and ys:
                pad_x = max(10, (max(xs) - min(xs)) * 0.25)
                pad_y = max(10, (max(ys) - min(ys)) * 0.25)
                last_bbox = (
                    int(min(xs) - pad_x), int(min(ys) - pad_y),
                    int(max(xs) + pad_x), int(max(ys) + pad_y),
                )

            frames.append({"t": round(t, 3), "kp": kp})
    finally:
        cap.release()
        pose.close()
        detector.close()

    metrics = _compute_metrics(frames)
    logger.info(
        "pose extraction done: %d/%d sampled frames with pose in %.1fs (%s)",
        len(frames), sampled, time.time() - started, video_path,
    )
    return {
        "version": 1,
        "width": width,
        "height": height,
        "sample_fps": round(native_fps / step, 2),
        "frames": frames,
        "metrics": metrics,
    }


def _mid(kp, i, j):
    a, b = kp[i], kp[j]
    if a[2] < 0.3 and b[2] < 0.3:
        return None
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _compute_metrics(frames: list[dict]) -> dict:
    """Speed proxy + compression (knee angle) series, lightly smoothed."""
    speed, compression = [], []
    prev = None
    for f in frames:
        kp = f["kp"]
        hip = _mid(kp, L_HIP, R_HIP)
        if hip is None:
            prev = None
            continue
        # Speed proxy: normalized hip displacement per second
        if prev is not None:
            dt = f["t"] - prev[0]
            if 0 < dt < 1.5:
                d = math.hypot(hip[0] - prev[1][0], hip[1] - prev[1][1])
                speed.append({"t": f["t"], "v": round(d / dt, 4)})
        prev = (f["t"], hip)

        # Compression: mean knee angle (lower angle = deeper compression)
        angles = []
        for h, k, a in ((L_HIP, L_KNEE, L_ANKLE), (R_HIP, R_KNEE, R_ANKLE)):
            if kp[k][2] > 0.4 and kp[h][2] > 0.3 and kp[a][2] > 0.3:
                angles.append(_angle(kp[h][:2], kp[k][:2], kp[a][:2]))
        if angles:
            compression.append({"t": f["t"], "v": round(sum(angles) / len(angles), 1)})

    # 3-point moving average smoothing for speed
    if len(speed) >= 3:
        vals = [s["v"] for s in speed]
        for i in range(1, len(speed) - 1):
            speed[i]["v"] = round((vals[i - 1] + vals[i] + vals[i + 1]) / 3, 4)
    return {"speed": speed, "compression": compression}
