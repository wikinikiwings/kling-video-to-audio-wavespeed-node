"""
ComfyUI node: Kling Video-to-Audio via WaveSpeed API.

Takes a video file, sends it to WaveSpeed's Kling V2A endpoint,
returns the video with generated audio.
"""

import os
import re
import shutil
import hashlib

import folder_paths

from .api_client import upload_video, submit_video2audio, poll_result, download_result


video_extensions = ['webm', 'mp4', 'mkv', 'gif', 'mov']


def _get_video_files():
    """List video files in ComfyUI input directory."""
    input_dir = folder_paths.get_input_directory()
    files = []
    for f in os.listdir(input_dir):
        if os.path.isfile(os.path.join(input_dir, f)):
            ext = f.rsplit('.', 1)[-1].lower() if '.' in f else ''
            if ext in video_extensions:
                files.append(f)
    return sorted(files)


def _calculate_file_hash(filepath):
    """Hash file for IS_CHANGED detection."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _resolve_api_key(wavespeed_api_key: str) -> str:
    """Resolve API key from widget or environment variable."""
    api_key = wavespeed_api_key.strip() if wavespeed_api_key else ""
    if not api_key:
        api_key = os.environ.get("WAVESPEED_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "WaveSpeed API key not found. Either:\n"
            "  1) Paste it in the wavespeed_api_key field, or\n"
            "  2) Set WAVESPEED_API_KEY environment variable"
        )
    return api_key


def _save_to_output(source_path: str, prefix: str = "kling_v2a"):
    """
    Copy the result video into ComfyUI's output directory.
    Returns (full_path, filename, subfolder).
    """
    output_dir = folder_paths.get_output_directory()
    full_output_folder, filename, _, subfolder, _ = folder_paths.get_save_image_path(
        prefix, output_dir
    )
    ext = os.path.splitext(source_path)[1] or ".mp4"
    counter = 1
    matcher = re.compile(rf"{re.escape(filename)}_(\d+)\..+", re.IGNORECASE)
    if os.path.isdir(full_output_folder):
        for existing in os.listdir(full_output_folder):
            m = matcher.fullmatch(existing)
            if m:
                counter = max(counter, int(m.group(1)) + 1)

    out_filename = f"{filename}_{counter:05}{ext}"
    out_path = os.path.join(full_output_folder, out_filename)
    shutil.copy2(source_path, out_path)
    return out_path, out_filename, subfolder


def _check_video_duration(filepath, max_seconds=20):
    """Check video duration. Raises ValueError if too long."""
    try:
        import subprocess
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            if duration > max_seconds:
                raise ValueError(
                    f"Video is {duration:.1f}s long — maximum allowed is {max_seconds}s.\n"
                    f"Please trim the video and try again."
                )
            print(f"[Kling V2A] Video duration: {duration:.1f}s (max {max_seconds}s) ✓")
    except FileNotFoundError:
        # ffprobe not available — skip check, WaveSpeed will reject if too long
        print("[Kling V2A] ffprobe not found, skipping duration check")
    except ValueError:
        raise  # re-raise our own ValueError
    except Exception as e:
        print(f"[Kling V2A] Duration check skipped: {e}")


def _run_v2a(video_filepath, api_key, sound_effect_prompt, bgm_prompt, asmr_mode):
    """Core V2A logic shared by both nodes."""
    # Check duration
    _check_video_duration(video_filepath)

    # Upload
    print(f"[Kling V2A] Uploading video: {video_filepath}")
    video_url = upload_video(video_filepath, api_key)
    print(f"[Kling V2A] Uploaded → {video_url}")

    # Submit
    print(f"[Kling V2A] Submitting task...")
    request_id = submit_video2audio(
        video_url=video_url,
        api_key=api_key,
        sound_effect_prompt=sound_effect_prompt,
        bgm_prompt=bgm_prompt,
        asmr_mode=asmr_mode,
    )
    print(f"[Kling V2A] Task submitted: {request_id}")

    # Poll
    def _progress(attempt, total):
        if attempt % 3 == 0:
            print(f"[Kling V2A] Polling... ({attempt}/{total})")

    print(f"[Kling V2A] Waiting for result...")
    output_url = poll_result(
        request_id=request_id,
        api_key=api_key,
        progress_callback=_progress,
    )
    print(f"[Kling V2A] Result ready: {output_url}")

    # Download to temp
    temp_dir = folder_paths.get_temp_directory()
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = download_result(output_url, temp_dir, filename_prefix="kling_v2a_tmp")

    # Copy to output
    out_path, out_filename, subfolder = _save_to_output(temp_path)
    print(f"[Kling V2A] Saved to output: {out_path}")

    # Clean temp
    try:
        os.remove(temp_path)
    except OSError:
        pass

    return out_path, out_filename, subfolder


class KlingVideo2Audio:
    """
    Generate matching sound effects and audio for a video
    using Kling AI (via WaveSpeed API).

    Upload a video via ComfyUI's built-in upload button,
    write prompts for SFX/BGM, and run.
    Output: path to video with generated audio.
    """

    CATEGORY = "video/audio"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video": (sorted(_get_video_files()),
                          {"tooltip": "Select a video or use Upload Video button below."}),
                "sound_effect_prompt": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Text prompt for sound effects (max 200 chars).",
                }),
                "bgm_prompt": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Text prompt for background music (max 200 chars).",
                }),
            },
            "optional": {
                "asmr_mode": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Enable ASMR mode for enhanced detailed sound effects.",
                }),
                "api_key": ("STRING", {
                    "forceInput": True,
                    "tooltip": "Optional: connect a custom WaveSpeed API key. If not connected, uses WAVESPEED_API_KEY env var.",
                }),
            },
        }

    def execute(
        self,
        video: str,
        sound_effect_prompt: str = "",
        bgm_prompt: str = "",
        asmr_mode: bool = False,
        api_key: str = "",
    ):
        # Resolve file path — try annotated first, then direct input dir
        video_path = folder_paths.get_annotated_filepath(video)
        if not video_path or not os.path.isfile(video_path):
            video_path = os.path.join(folder_paths.get_input_directory(), video)
        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"Video file not found: {video}")

        api_key = _resolve_api_key(api_key)

        out_path, out_filename, subfolder = _run_v2a(
            video_path, api_key, sound_effect_prompt, bgm_prompt, asmr_mode
        )

        return (out_path,)

    @classmethod
    def IS_CHANGED(cls, video, **kwargs):
        try:
            video_path = folder_paths.get_annotated_filepath(video)
            if os.path.isfile(video_path):
                return _calculate_file_hash(video_path)
        except Exception:
            pass
        # Also check directly in input directory
        input_path = os.path.join(folder_paths.get_input_directory(), video)
        if os.path.isfile(input_path):
            return _calculate_file_hash(input_path)
        return video

    @classmethod
    def VALIDATE_INPUTS(cls, video, **kwargs):
        # Check annotated path first, then direct input path
        try:
            if folder_paths.exists_annotated_filepath(video):
                return True
        except Exception:
            pass
        input_path = os.path.join(folder_paths.get_input_directory(), video)
        if os.path.isfile(input_path):
            return True
        return f"Video file not found: {video}"


class KlingVideo2AudioURL:
    """
    Same as KlingVideo2Audio, but accepts a video URL instead of a local file.
    Skips the upload step — useful if video is already hosted online.
    """

    CATEGORY = "video/audio"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_url": ("STRING", {
                    "default": "",
                    "tooltip": "Public URL to the input video (mp4, max 20s).",
                }),
                "sound_effect_prompt": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Text prompt for sound effects (max 200 chars).",
                }),
                "bgm_prompt": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Text prompt for background music (max 200 chars).",
                }),
            },
            "optional": {
                "asmr_mode": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Enable ASMR mode for enhanced detailed sound effects.",
                }),
                "api_key": ("STRING", {
                    "forceInput": True,
                    "tooltip": "Optional: connect a custom WaveSpeed API key. If not connected, uses WAVESPEED_API_KEY env var.",
                }),
            },
        }

    def execute(
        self,
        video_url: str,
        sound_effect_prompt: str = "",
        bgm_prompt: str = "",
        asmr_mode: bool = False,
        api_key: str = "",
    ):
        video_url = video_url.strip()
        if not video_url:
            raise ValueError("video_url is empty.")

        api_key = _resolve_api_key(api_key)

        # Submit directly (no upload needed)
        print(f"[Kling V2A URL] Submitting task with URL: {video_url[:80]}...")
        request_id = submit_video2audio(
            video_url=video_url,
            api_key=api_key,
            sound_effect_prompt=sound_effect_prompt,
            bgm_prompt=bgm_prompt,
            asmr_mode=asmr_mode,
        )
        print(f"[Kling V2A URL] Task submitted: {request_id}")

        def _progress(attempt, total):
            if attempt % 3 == 0:
                print(f"[Kling V2A URL] Polling... ({attempt}/{total})")

        output_url = poll_result(
            request_id=request_id,
            api_key=api_key,
            progress_callback=_progress,
        )
        print(f"[Kling V2A URL] Result ready: {output_url}")

        temp_dir = folder_paths.get_temp_directory()
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = download_result(output_url, temp_dir, filename_prefix="kling_v2a_tmp")

        out_path, out_filename, subfolder = _save_to_output(temp_path)
        print(f"[Kling V2A URL] Saved to output: {out_path}")

        try:
            os.remove(temp_path)
        except OSError:
            pass

        return (out_path,)


class KlingVideo2AudioPath:
    """
    Same as KlingVideo2Audio, but accepts a video path as STRING input.
    Useful for chaining with other nodes that output file paths.
    """

    CATEGORY = "video/audio"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_path": ("STRING", {
                    "default": "",
                    "tooltip": "Path to video file (mp4). Connect from another node.",
                }),
                "sound_effect_prompt": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Text prompt for sound effects (max 200 chars).",
                }),
                "bgm_prompt": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Text prompt for background music (max 200 chars).",
                }),
            },
            "optional": {
                "asmr_mode": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Enable ASMR mode for enhanced detailed sound effects.",
                }),
                "api_key": ("STRING", {
                    "forceInput": True,
                    "tooltip": "Optional: connect a custom WaveSpeed API key. If not connected, uses WAVESPEED_API_KEY env var.",
                }),
            },
        }

    def execute(
        self,
        video_path: str,
        sound_effect_prompt: str = "",
        bgm_prompt: str = "",
        asmr_mode: bool = False,
        api_key: str = "",
    ):
        video_path = video_path.strip().strip('"').strip("'")
        if not video_path:
            raise ValueError("video_path is empty.")
        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        api_key = _resolve_api_key(api_key)

        out_path, out_filename, subfolder = _run_v2a(
            video_path, api_key, sound_effect_prompt, bgm_prompt, asmr_mode
        )

        return (out_path,)
