"""
ComfyUI_kling_video_2_audio
===========================
Kling Video-to-Audio via WaveSpeed API.
Generates matching sound effects, BGM, and audio tracks for videos.
"""

from .nodes import KlingVideo2Audio, KlingVideo2AudioURL, KlingVideo2AudioPath

NODE_CLASS_MAPPINGS = {
    "KlingVideo2Audio": KlingVideo2Audio,
    "KlingVideo2AudioURL": KlingVideo2AudioURL,
    "KlingVideo2AudioPath": KlingVideo2AudioPath,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KlingVideo2Audio": "Kling Video to Audio (Upload)",
    "KlingVideo2AudioURL": "Kling Video to Audio (URL)",
    "KlingVideo2AudioPath": "Kling Video to Audio (Path)",
}

# Load JS extensions for upload button
WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
