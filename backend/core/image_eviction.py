"""
image_eviction.py — Outbound Multimodal Image Eviction Policy for Project Anara.
Parity with Hermes Agent image_eviction_policy (Nous Research).

Prevents context window exhaustion, 413 Request Entity Too Large errors,
and prompt cache busts during long vision-assisted and browser sessions.
Retires older historical screenshot/tool-result images from the outbound request payload,
replacing them with concise text markers while preserving user-uploaded images and the newest frames.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("anara.core.image_eviction")

# Maximum number of active image frames kept in the live conversational context window.
DEFAULT_MAX_ACTIVE_IMAGES: int = 3

# Byte budget ceiling for total outbound payload before aggressive eviction kicks in (24 MB)
MAX_OUTBOUND_IMAGE_BYTES: int = 24_000_000

RETIRED_IMAGE_NOTICE = "[Image omitted: historical screenshot/frame retired to preserve context token budget]"


def is_image_block(block: Any) -> bool:
    """Detects whether a message content block represents an image payload."""
    if not isinstance(block, dict):
        return False
    btype = block.get("type", "").lower()
    if btype in ("image", "image_url", "input_image"):
        return True
    if "inline_data" in block or "image_url" in block:
        return True
    return False


def estimate_block_bytes(block: Any) -> int:
    """Estimates in-memory byte size of an image block."""
    if not isinstance(block, dict):
        return 0
    # base64 data string
    if "data" in block and isinstance(block["data"], str):
        return len(block["data"])
    if "inline_data" in block and isinstance(block["inline_data"], dict):
        data = block["inline_data"].get("data", "")
        if isinstance(data, str):
            return len(data)
    if "image_url" in block:
        url_obj = block["image_url"]
        if isinstance(url_obj, dict):
            url_str = url_obj.get("url", "")
            return len(url_str)
        elif isinstance(url_obj, str):
            return len(url_obj)
    return 1024  # Default fallback estimation


def evict_historical_images(
    messages: List[Dict[str, Any]],
    max_active_images: int = DEFAULT_MAX_ACTIVE_IMAGES,
    max_bytes: int = MAX_OUTBOUND_IMAGE_BYTES,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Applies Anara Image Eviction Policy to a cloned copy of conversational messages.
    Retires older historical images from the head of the transcript, retaining only
    the newest `max_active_images` frames and staying under `max_bytes`.
    
    Returns:
        (sanitized_messages, retired_count)
    """
    if not messages:
        return messages, 0

    # 1. Collect all image references with their exact locations: (msg_idx, block_idx, byte_size, is_user)
    image_refs: List[Dict[str, Any]] = []

    for msg_idx, msg in enumerate(messages):
        role = msg.get("role", "")
        content = msg.get("content")

        if isinstance(content, list):
            for block_idx, block in enumerate(content):
                if is_image_block(block):
                    b_bytes = estimate_block_bytes(block)
                    image_refs.append({
                        "msg_idx": msg_idx,
                        "block_idx": block_idx,
                        "bytes": b_bytes,
                        "is_user_latest": (role == "user" and msg_idx == len(messages) - 1),
                    })
        elif isinstance(content, dict) and is_image_block(content):
            b_bytes = estimate_block_bytes(content)
            image_refs.append({
                "msg_idx": msg_idx,
                "block_idx": None,
                "bytes": b_bytes,
                "is_user_latest": (role == "user" and msg_idx == len(messages) - 1),
            })

    total_images = len(image_refs)
    if total_images <= max_active_images:
        # Check byte pressure
        total_bytes = sum(ref["bytes"] for ref in image_refs)
        if total_bytes <= max_bytes:
            return messages, 0

    # 2. Identify which images must be retired (oldest first, preserving the latest active window)
    # Calculate how many need to be evicted
    candidates_for_eviction = [ref for ref in image_refs if not ref["is_user_latest"]]
    excess_count = max(0, total_images - max_active_images)

    # Sort candidates by chronological age (oldest msg_idx first)
    candidates_for_eviction.sort(key=lambda r: (r["msg_idx"], r.get("block_idx") or 0))

    to_evict_indices = set()
    retired_count = 0

    # Evict by count quota
    for ref in candidates_for_eviction[:excess_count]:
        to_evict_indices.add((ref["msg_idx"], ref["block_idx"]))
        retired_count += 1

    # Check if remaining still exceed byte ceiling
    remaining_refs = [ref for ref in image_refs if (ref["msg_idx"], ref["block_idx"]) not in to_evict_indices]
    while sum(r["bytes"] for r in remaining_refs) > max_bytes and remaining_refs:
        # Evict next oldest non-latest
        evict_target = None
        for r in remaining_refs:
            if not r["is_user_latest"]:
                evict_target = r
                break
        if not evict_target:
            break
        to_evict_indices.add((evict_target["msg_idx"], evict_target["block_idx"]))
        remaining_refs.remove(evict_target)
        retired_count += 1

    if not to_evict_indices:
        return messages, 0

    # 3. Clone and replace evicted blocks with retired notices
    cloned_messages = copy.deepcopy(messages)

    for msg_idx, block_idx in to_evict_indices:
        msg = cloned_messages[msg_idx]
        content = msg.get("content")

        if block_idx is not None and isinstance(content, list):
            content[block_idx] = {
                "type": "text",
                "text": RETIRED_IMAGE_NOTICE
            }
        else:
            msg["content"] = RETIRED_IMAGE_NOTICE

    logger.info(
        f"[ImageEviction] Retired {retired_count} historical image(s) to preserve context token budget. "
        f"Active images retained: {total_images - retired_count}."
    )
    return cloned_messages, retired_count
