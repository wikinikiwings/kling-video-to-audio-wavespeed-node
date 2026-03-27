"""
WaveSpeed API client for Kling Video-to-Audio.

Handles: upload video, submit task, poll result, download output.
"""

import os
import time
import json
import urllib.request
import urllib.error
import tempfile


WAVESPEED_BASE = "https://api.wavespeed.ai/api/v3"
UPLOAD_ENDPOINT = f"{WAVESPEED_BASE}/media/upload/binary"
SUBMIT_ENDPOINT = f"{WAVESPEED_BASE}/kwaivgi/kling-video-to-audio"
POLL_ENDPOINT_TPL = WAVESPEED_BASE + "/predictions/{request_id}/result"

DEFAULT_POLL_INTERVAL = 10  # seconds
DEFAULT_MAX_POLLS = 120     # 120 * 10s = 20 minutes max


def _headers(api_key: str, content_type: str = "application/json") -> dict:
    h = {
        "Authorization": f"Bearer {api_key}",
    }
    if content_type:
        h["Content-Type"] = content_type
    return h


def upload_video(file_path: str, api_key: str) -> str:
    """Upload a local video file to WaveSpeed CDN, return the download URL."""
    import mimetypes

    boundary = "----ComfyUIBoundary"
    filename = os.path.basename(file_path)
    mime_type = mimetypes.guess_type(file_path)[0] or "video/mp4"

    with open(file_path, "rb") as f:
        file_data = f.read()

    # Build multipart body
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n"
        f"\r\n"
    ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        UPLOAD_ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"WaveSpeed upload failed ({e.code}): {error_body}")

    if result.get("code") != 200:
        raise RuntimeError(f"WaveSpeed upload error: {result}")

    url = result["data"]["download_url"]
    return url


def submit_video2audio(
    video_url: str,
    api_key: str,
    sound_effect_prompt: str = "",
    bgm_prompt: str = "",
    asmr_mode: bool = False,
) -> str:
    """Submit a Video-to-Audio task. Returns request_id."""
    payload = {
        "video": video_url,
        "asmr_mode": asmr_mode,
    }
    if sound_effect_prompt.strip():
        payload["sound_effect_prompt"] = sound_effect_prompt.strip()[:200]
    if bgm_prompt.strip():
        payload["bgm_prompt"] = bgm_prompt.strip()[:200]

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SUBMIT_ENDPOINT,
        data=data,
        headers=_headers(api_key),
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"WaveSpeed submit failed ({e.code}): {error_body}")

    # id may be at top level or nested in data
    request_id = result.get("id")
    if not request_id and isinstance(result.get("data"), dict):
        request_id = result["data"].get("id")
    if not request_id:
        raise RuntimeError(f"WaveSpeed submit: no task id returned. Response: {result}")

    return request_id


def poll_result(
    request_id: str,
    api_key: str,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    max_polls: int = DEFAULT_MAX_POLLS,
    progress_callback=None,
) -> str:
    """Poll until task completes. Returns the output URL."""
    url = POLL_ENDPOINT_TPL.format(request_id=request_id)

    for attempt in range(max_polls):
        if progress_callback:
            progress_callback(attempt, max_polls)

        req = urllib.request.Request(
            url,
            headers=_headers(api_key, content_type=None),
            method="GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Task not ready yet
                time.sleep(poll_interval)
                continue
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"WaveSpeed poll failed ({e.code}): {error_body}")

        # Response may be flat or wrapped in {"code":200, "data":{...}}
        if isinstance(result.get("data"), dict) and "status" in result["data"]:
            data = result["data"]
        else:
            data = result

        status = data.get("status", "")

        if status == "completed":
            outputs = data.get("outputs", [])
            if outputs:
                return outputs[0]
            raise RuntimeError(f"Task completed but no outputs found: {result}")

        if status == "failed":
            error = data.get("error") or result.get("error") or "Unknown error"
            raise RuntimeError(f"WaveSpeed task failed: {error}")

        # still pending/processing
        time.sleep(poll_interval)

    raise RuntimeError(f"WaveSpeed polling timed out after {max_polls * poll_interval}s")


def download_result(output_url: str, output_dir: str, filename_prefix: str = "kling_v2a") -> str:
    """Download the result video to output_dir. Returns the local file path."""
    os.makedirs(output_dir, exist_ok=True)

    # Determine extension from URL
    ext = ".mp4"
    if "." in output_url.split("/")[-1].split("?")[0]:
        url_ext = "." + output_url.split("/")[-1].split("?")[0].rsplit(".", 1)[-1]
        if url_ext in (".mp4", ".webm", ".mov", ".mkv"):
            ext = url_ext

    timestamp = int(time.time())
    filename = f"{filename_prefix}_{timestamp}{ext}"
    filepath = os.path.join(output_dir, filename)

    req = urllib.request.Request(output_url, method="GET")
    with urllib.request.urlopen(req, timeout=300) as resp:
        with open(filepath, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

    return filepath
