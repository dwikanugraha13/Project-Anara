from .emotion import EmotionEngine
from .audio import (
    analyze_speech_emotion,
    estimate_audio_intensity,
    pcm16_to_base64,
    base64_to_pcm16,
    float32_to_pcm16,
    pcm16_to_float32,
    is_stt_hallucination,
    AcousticSERTracker,
    synthesize_speech_audio,
    resolve_tts_voice_model_driven,
)
from .visual import (
    generate_visual_projection,
    could_be_visual_request,
    is_visual_request_semantic,
    generate_smart_hud_card,
    fetch_real_web_images,
)
from .soul import get_soul_prompt, get_soul_raw, save_soul_raw, _find_soul_file

__all__ = [
    "EmotionEngine",
    "analyze_speech_emotion",
    "estimate_audio_intensity",
    "pcm16_to_base64",
    "base64_to_pcm16",
    "float32_to_pcm16",
    "pcm16_to_float32",
    "is_stt_hallucination",
    "AcousticSERTracker",
    "synthesize_speech_audio",
    "resolve_tts_voice_model_driven",
    "generate_visual_projection",
    "could_be_visual_request",
    "is_visual_request_semantic",
    "generate_smart_hud_card",
    "fetch_real_web_images",
    "get_soul_prompt",
    "get_soul_raw",
    "save_soul_raw",
    "_find_soul_file",
]
