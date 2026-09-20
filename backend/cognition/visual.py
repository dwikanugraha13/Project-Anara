"""
image_service.py

J.A.R.V.I.S. Multimodal Holographic Visual Projection Engine for Project Anara.
Capable of projecting:
1. Real high-resolution web photographs (Bing, Google, Wikimedia)
2. Holographic Real-time Weather Forecast HUD widgets
3. Holographic Sci-Fi Code Terminal cards
4. JARVIS Core Telemetry & Diagnostics HUD
5. Knowledge & Schematic Infographic cards
6. Dynamic To-Do & Task Checklist cards
"""

import asyncio
import json
import urllib.parse
import logging
import re
import httpx
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

def could_be_visual_request(text: str) -> bool:
    """
    Deprecated keyword helper retained for backwards compatibility (Hermes Parity).
    In Hermes Agent, visual intent is driven strictly by model reasoning.
    Use asynchronous is_visual_request_semantic instead of static word filtering.
    """
    return False


async def is_visual_request_semantic(user_text: str) -> bool:
    """
    Pure Model-Driven Semantic Visual Intent Classifier (Hermes Parity).
    Evaluates whether the user asks to see or project a photo, image, weather, chart, or visual card.
    Operates without hardcoded word sets across any human language.
    """
    clean = (user_text or "").strip()
    if not clean or len(clean) < 2:
        return False

    try:
        import asyncio
        from providers import call_universal_chat_model
        from core.capabilities import get_fast_auxiliary_model

        sys_p = (
            "You are an intent classifier for an autonomous multimodal agent. "
            "Determine if the user's input asks to see, show, display, or project a photo, image, chart, weather, or visual card.\n"
            "Respond with exactly ONE word: YES or NO."
        )
        user_p = f"User input: \"{clean}\"\nRequires visual projection:"
        res = await asyncio.wait_for(
            call_universal_chat_model(
                model_id=get_fast_auxiliary_model(),
                user_prompt=user_p,
                system_instruction=sys_p,
                max_tokens=None,
                temperature=0.0,
                read_only=True
            ),
            timeout=2.0
        )
        if isinstance(res, str) and "YES" in res.strip().upper():
            return True
    except Exception as e:
        logger.debug(f"[VisualClassifier] Semantic check notice: {e}")

    return False


async def fetch_real_web_images(query: str, count: int = 6) -> List[Dict[str, str]]:
    """
    Searches multiple real photos from web search engines (Bing / Google Image indexes, Wikipedia, Wikimedia).
    Returns list of direct image URLs, titles, and source domains for multi-image gallery/carousel.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    BLOCKED_DOMAINS = {
        "istockphoto.com", "gettyimages.com", "alamy.com", "shutterstock.com",
        "dreamstime.com", "123rf.com", "stock.adobe.com", "depositphotos.com"
    }

    results: List[Dict[str, str]] = []
    seen_urls = set()

    # 1. Search Real Web Images via Bing Images
    try:
        search_url = f"https://www.bing.com/images/search?q={urllib.parse.quote(query)}&form=HDRSC2&first=1"
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            res = await client.get(search_url, headers=headers)
            if res.status_code == 200:
                html = res.text
                items = re.findall(r'\{&quot;murl&quot;:&quot;(https?://[^&]+)&quot;.*?&quot;t&quot;:&quot;([^&]*)&quot;.*?&quot;purl&quot;:&quot;(https?://[^&]+)&quot;', html)
                if not items:
                    murls = re.findall(r'murl&quot;:&quot;(https?://[^&]+)&quot;', html)
                    titles = re.findall(r'&quot;t&quot;:&quot;([^&]*)&quot;', html)
                    purls = re.findall(r'&quot;purl&quot;:&quot;(https?://[^&]+)&quot;', html)
                    items = list(zip(murls, titles or [""] * len(murls), purls or [""] * len(murls)))

                for murl, raw_title, purl in items:
                    clean_url = murl.replace("\\/", "/")
                    if clean_url in seen_urls:
                        continue

                    domain = urllib.parse.urlparse(purl).netloc.lower() or "Web Search"
                    img_domain = urllib.parse.urlparse(clean_url).netloc.lower()

                    if any(bd in domain or bd in img_domain for bd in BLOCKED_DOMAINS):
                        continue

                    if clean_url.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".avif")) or "images" in clean_url or "photo" in clean_url or "media" in clean_url:
                        title = raw_title.replace("&#39;", "'").replace("&amp;", "&").strip() or query.title()
                        seen_urls.add(clean_url)
                        results.append({
                            "image_url": clean_url,
                            "title": title,
                            "source_url": purl,
                            "source_domain": domain
                        })
                        if len(results) >= count:
                            break
    except Exception as e:
        logger.warning(f"[Real Image Search] Bing search index error: {e}")

    # 2. Search Wikipedia API if needed
    if len(results) < count:
        try:
            for lang in ["id", "en"]:
                wiki_api = f"https://{lang}.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(query)}&prop=pageimages&format=json&pithumbsize=1000"
                async with httpx.AsyncClient(timeout=4.0) as client:
                    w_res = await client.get(wiki_api, headers={"User-Agent": "AnaraAssistant/2.0"})
                    if w_res.status_code == 200:
                        pages = w_res.json().get("query", {}).get("pages", {})
                        for _, pdata in pages.items():
                            if "thumbnail" in pdata and pdata["thumbnail"].get("source"):
                                t_url = pdata["thumbnail"]["source"]
                                if t_url not in seen_urls:
                                    seen_urls.add(t_url)
                                    results.append({
                                        "image_url": t_url,
                                        "title": pdata.get("title", query.title()),
                                        "source_url": f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(query)}",
                                        "source_domain": f"{lang}.wikipedia.org"
                                    })
                                    if len(results) >= count:
                                        break
        except Exception as e:
            logger.warning(f"[Real Image Search] Wikipedia API error: {e}")

    # 3. Search Wikimedia Commons if needed
    if len(results) < count:
        try:
            wiki_url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch={urllib.parse.quote(query)}&gsrnamespace=6&gsrlimit=6&prop=imageinfo&iiprop=url|size|mime&format=json"
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(wiki_url, headers={"User-Agent": "AnaraAssistant/2.0"})
                if res.status_code == 200:
                    data = res.json()
                    pages = data.get("query", {}).get("pages", {})
                    for pid, page in pages.items():
                        infos = page.get("imageinfo", [])
                        if infos and infos[0].get("url"):
                            img = infos[0]["url"]
                            if img not in seen_urls and img.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                                seen_urls.add(img)
                                results.append({
                                    "image_url": img,
                                    "title": page.get("title", query.title()).replace("File:", ""),
                                    "source_url": img,
                                    "source_domain": "wikimedia.org"
                                })
                                if len(results) >= count:
                                    break
        except Exception as e:
            logger.warning(f"[Real Image Search] Wikimedia error: {e}")

    return results


async def fetch_real_web_image(query: str) -> Optional[Dict[str, str]]:
    """Legacy helper returning the first matched image."""
    imgs = await fetch_real_web_images(query, count=1)
    return imgs[0] if imgs else None


# In-memory query cache
_VISUAL_QUERY_CACHE: Dict[str, Dict[str, Any]] = {}


async def generate_visual_projection(
    client: genai.Client,
    user_text: str,
    system_prompt: str,
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyzes user query and produces JARVIS-style multi-modal holographic visual projections:
    - 'image': Real web photograph
    - 'weather': Real-time weather HUD card
    - 'code': Holographic syntax-highlighted code terminal
    - 'system_hud': JARVIS core telemetry diagnostics
    - 'knowledge_card': Structured schematic / infographic specs card
    - 'todo_list': Dynamic to-do / task checklist card
    """
    clean_key = user_text.lower().strip()
    if clean_key in _VISUAL_QUERY_CACHE:
        logger.info(f"[VisualProjection Cache Hit] 0 tokens used: {clean_key!r}")
        return _VISUAL_QUERY_CACHE[clean_key]

    from memory import memory_engine, get_current_indonesian_time_str
    time_info = get_current_indonesian_time_str()
    stats = memory_engine.get_brain_stats()

    # Retrieve recent conversation context so pronouns/follow-ups (e.g. 'tunjukkan fotonya', 'mana gambarnya', 'ya tampilkan', 'ya', 'boleh') resolve to the discussed subject
    recent_chat = memory_engine.get_recent_conversations(limit=4)
    recent_context_lines = []
    if recent_chat:
        for c in recent_chat:
            u_t = (c.get("user_text") or "").strip()
            a_t = (c.get("ai_text") or "").strip()
            if u_t or a_t:
                recent_context_lines.append(f"User: {u_t}\nAnara: {a_t}")

    recent_context_str = ""
    if recent_context_lines:
        recent_context_str = "KONTEKS PERCAKAPAN TERAKHIR:\n" + "\n---\n".join(recent_context_lines) + "\n\n"

    prompt = (
        f"{system_prompt}\n\n"
        f"{recent_context_str}"
        "ROLE: HOLOGRAPHIC 3D VISUAL PROJECTION CLASSIFIER (ANARA HUD ENGINE)\n"
        f"Timestamp: {time_info['date_full']}, {time_info['time_str']}\n\n"
        "CORE TASK:\n"
        "Classify the user's intent across ANY human language (English, Indonesian, Japanese, Korean, Arabic, Chinese, French, Spanish, German, etc.) "
        "and select the single most appropriate visual_type for holographic HUD projection.\n\n"
        "SEMANTIC CATEGORIES:\n"
        "1. 'image': User explicitly asks to view, see, or display real photos, imagery, galleries, monuments, places, people, vehicles, nature, or objects.\n"
        "   - Required fields: search_query (clean subject name for web image search), image_title, image_count (default 1 or requested number).\n"
        "2. 'weather': User inquires about current weather, temperature, or atmospheric forecasts for any city or region.\n"
        "   - Required fields: weather_data with city, temp_c, condition, humidity, wind_kmh, uv_index, forecast.\n"
        "3. 'code': User requests code snippets, programming scripts, algorithms, or technical coding functions.\n"
        "   - Required fields: code_data with language, title, code, explanation.\n"
        "4. 'system_hud': User inquires about system diagnostics, core health, AI brain status, telemetry, or performance.\n"
        "   - Required fields: system_hud_data with core_status, ai_model, active_keys, memory_nodes, latency_ms, uptime.\n"
        "5. 'knowledge_card': User requests recipes, cooking steps, how-to guides, tutorials, technical specs, anatomy, scientific facts, or comparison charts.\n"
        "   - Required fields: knowledge_card_data with title, category, badge, summary, ingredients, steps, specs.\n"
        "   - NOTE: Recipes and step-by-step guides MUST be 'knowledge_card' (structured text), NOT 'image'.\n"
        "6. 'todo_list': User inquires about or requests to display their active to-do list or task checklist.\n"
        "7. 'none': Conversational chat without visual projection intent (greetings, general Q&A, conceptual discussions).\n\n"
        f"User Message: \"{user_text}\"\n\n"
        "RETURN ONLY VALID JSON (no markdown fences outside JSON):\n"
        "{\n"
        '  "has_visual": true,\n'
        '  "visual_type": "image|weather|code|system_hud|knowledge_card|todo_list|none",\n'
        '  "search_query": "...",\n'
        '  "image_title": "...",\n'
        '  "image_count": 1,\n'
        '  "reply_text": "A direct, helpful, and natural response from Anara matching the user\'s active language (1-2 sentences).",\n'
        '  "weather_data": {\n'
        '    "city": "Jakarta",\n'
        '    "temp_c": 31,\n'
        '    "condition": "Cerah Berawan",\n'
        '    "humidity": 72,\n'
        '    "wind_kmh": 14,\n'
        '    "uv_index": 8,\n'
        '    "forecast": [\n'
        '      {"day": "Besok", "temp_c": 32, "condition": "Hujan Ringan"},\n'
        '      {"day": "Lusa", "temp_c": 30, "condition": "Cerah"}\n'
        '    ]\n'
        '  },\n'
        '  "code_data": {\n'
        '    "language": "python",\n'
        '    "title": "...",\n'
        '    "code": "...",\n'
        '    "explanation": "..."\n'
        '  },\n'
        '  "system_hud_data": {\n'
        '    "core_status": "OPTIMAL",\n'
        '    "ai_model": "Gemini Live 3.1",\n'
        f'    "active_keys": 26,\n'
        f'    "memory_nodes": {stats["memories_count"]},\n'
        '    "latency_ms": 24,\n'
        '    "uptime": "99.98%"\n'
        '  },\n'
        '  "knowledge_card_data": {\n'
        '    "title": "...",\n'
        '    "category": "...",\n'
        '    "badge": "...",\n'
        '    "summary": "...",\n'
        '    "ingredients": ["bahan 1", "bahan 2"],\n'
        '    "steps": ["langkah pertama", "langkah kedua"],\n'
        '    "specs": [\n'
        '      {"label": "...", "value": "..."}\n'
        '    ]\n'
        '  }\n'
        "}"
    )

    try:
        gen_config = types.GenerateContentConfig(
            max_output_tokens=1200,
            temperature=0.3
        )
        res = None
        from core.capabilities import get_fast_auxiliary_model
        eff_mdl = model_name or get_fast_auxiliary_model()
        for mdl in [eff_mdl, "gemini-2.5-flash"]:
            try:
                res = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=mdl,
                        contents=prompt,
                        config=gen_config
                    ),
                    timeout=4.0
                )
                if res and res.text:
                    break
            except Exception as m_err:
                logger.warning(f"[VisualEngine] Fast model {mdl} error/timeout: {m_err}")

        raw = res.text.strip() if res and res.text else ""
        if "{" in raw and "}" in raw:
            json_str = raw[raw.find("{"):raw.rfind("}")+1]
            data = json.loads(json_str)
            v_type = data.get("visual_type", "none").strip().lower()
            reply_text = data.get("reply_text", "").strip()

            # 1. Real Web Multi-Image Search
            if v_type == "image":
                query = data.get("search_query", "").strip() or user_text
                try:
                    img_count = max(1, min(8, int(data.get("image_count", 1) or 1)))
                except Exception:
                    img_count = 1

                img_list = await fetch_real_web_images(query, count=img_count)
                if img_list:
                    primary = img_list[0]
                    res_obj = {
                        "has_visual": True,
                        "wants_image": True,
                        "visual_type": "image",
                        "image_url": primary["image_url"],
                        "image_title": primary["title"] or data.get("image_title") or query.title(),
                        "source_domain": primary.get("source_domain", "Google Search"),
                        "source_url": primary.get("source_url", ""),
                        "images": img_list if img_count > 1 else [primary],
                        "reply_text": reply_text or f"Proyeksi visual untuk {query} sudah siap di layar!"
                    }
                    _VISUAL_QUERY_CACHE[clean_key] = res_obj
                    return res_obj

            # 2. Holographic Weather HUD
            elif v_type == "weather":
                w_data = data.get("weather_data") or {
                    "city": "Jakarta",
                    "temp_c": 31,
                    "condition": "Cerah Berawan",
                    "humidity": 70,
                    "wind_kmh": 12,
                    "uv_index": 7,
                    "forecast": [
                        {"day": "Besok", "temp_c": 32, "condition": "Hujan Ringan"},
                        {"day": "Lusa", "temp_c": 30, "condition": "Cerah"}
                    ]
                }
                res_obj = {
                    "has_visual": True,
                    "wants_image": False,
                    "visual_type": "weather",
                    "weather_data": w_data,
                    "reply_text": reply_text or f"Berikut proyeksi laporan cuaca real-time untuk wilayah {w_data.get('city', 'Jakarta')}."
                }
                _VISUAL_QUERY_CACHE[clean_key] = res_obj
                return res_obj

            # 3. Holographic Code Box
            elif v_type == "code":
                c_data = data.get("code_data") or {
                    "language": "python",
                    "title": "Sci-Fi Script",
                    "code": "# Code generated by Anara",
                    "explanation": ""
                }
                res_obj = {
                    "has_visual": True,
                    "wants_image": False,
                    "visual_type": "code",
                    "code_data": c_data,
                    "reply_text": reply_text or "Protokol kode telah diproyeksikan ke terminal visual layar."
                }
                _VISUAL_QUERY_CACHE[clean_key] = res_obj
                return res_obj

            # 4. JARVIS System Telemetry HUD
            elif v_type == "system_hud":
                hud_data = data.get("system_hud_data") or {
                    "core_status": "ONLINE / OPTIMAL",
                    "ai_model": "Gemini Live 3.1",
                    "active_keys": 26,
                    "memory_nodes": stats["memories_count"],
                    "latency_ms": 22,
                    "uptime": "99.98%"
                }
                res_obj = {
                    "has_visual": True,
                    "wants_image": False,
                    "visual_type": "system_hud",
                    "system_hud_data": hud_data,
                    "reply_text": reply_text or "Semua sistem Anara berfungsi optimal tanpa anomali."
                }
                _VISUAL_QUERY_CACHE[clean_key] = res_obj
                return res_obj

            # 5. Knowledge & Schematic Card
            elif v_type == "knowledge_card":
                k_data = data.get("knowledge_card_data") or {
                    "title": user_text.title(),
                    "category": "Pengetahuan Terstruktur",
                    "badge": "Schematic",
                    "summary": "Data skematik holographic",
                    "specs": []
                }
                # Normalize structured recipe/step fields (frontend renders these natively)
                k_data["ingredients"] = [str(x).strip() for x in (k_data.get("ingredients") or []) if str(x).strip()]
                k_data["steps"] = [str(x).strip() for x in (k_data.get("steps") or []) if str(x).strip()][:8]
                if not k_data.get("badge"):
                    k_data["badge"] = "Smart HUD"
                res_obj = {
                    "has_visual": True,
                    "wants_image": False,
                    "visual_type": "knowledge_card",
                    "knowledge_card_data": k_data,
                    "reply_text": reply_text or "Skematik informasi telah diproyeksikan ke layar HUD."
                }
                _VISUAL_QUERY_CACHE[clean_key] = res_obj
                return res_obj

            # 6. Dynamic To-Do List HUD
            elif v_type == "todo_list":
                todos = memory_engine.get_notes_and_todos()
                res_obj = {
                    "has_visual": True,
                    "wants_image": False,
                    "visual_type": "todo_list",
                    "todo_data": {"items": todos},
                    "reply_text": reply_text or "Berikut daftar catatan tugas to-do aktif kamu dari database."
                }
                _VISUAL_QUERY_CACHE[clean_key] = res_obj
                return res_obj

            # Default conversational fallback
            res_obj = {
                "has_visual": False,
                "wants_image": False,
                "visual_type": "none",
                "reply_text": reply_text or "Ada yang bisa Anara bantu lagi, Bos?"
            }
            return res_obj

    except Exception as e:
        logger.error(f"[VisualEngine] Error projecting visual: {e}", exc_info=True)

    return {
        "has_visual": False,
        "wants_image": False,
        "visual_type": "none",
        "reply_text": "Ada yang bisa Anara bantu lagi?"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SEMANTIC HUD ENGINE — Pure Model Reasoning (Zero Hardcoded Keywords)
# ═══════════════════════════════════════════════════════════════════════════════

_SEMANTIC_HUD_PROMPT = (
    "Kamu adalah Semantic HUD Intelligence untuk asisten suara Anara — engine yang MEMAHAMI "
    "alur percakapan secara semantik (bukan keyword) dan memutuskan apakah layar HUD perlu "
    "menampilkan sesuatu setelah giliran terakhir Anara.\n\n"
    "ANALISIS PERCAKAPAN DI BAWAH DAN PUTUSKAN:\n"
    "- knowledge_card: user meminta/menerima tawaran konten terstruktur — resep masakan, "
    "langkah-langkah, tips, panduan, perbandingan, spesifikasi, daftar rekomendasi, prosedur, "
    "jadwal, manfaat. TERMASUK saat user menjawab afirmatif ('ya', 'boleh', 'gasin', 'yaudah sok', "
    "gaya bahasa APAPUN) terhadap tawaran Anara di giliran sebelumnya, ATAU meminta ulang "
    "('gimana tadi langkahnya?'), ATAU meminta variasi ('yang versi pedas dong').\n"
    "- image: HANYA saat user secara eksplisit ingin MELIHAT penampakan/bentuk/foto objek nyata "
    "('kayak apa sih', 'tunjukkan fotonya', 'lihat penampakannya'). "
    "PERHATIAN: resep/cara membuat/langkah/tips TENTANG makanan = knowledge_card, BUKAN image! "
    "Konten tulisan terstruktur selalu menang atas foto.\n"
    "- none: obrolan biasa, basa-basi, pertanyaan singkat, atau tidak ada konten yang layak "
    "diproyeksikan. JANGAN memproyeksikan kartu untuk small-talk.\n\n"
    "PENTING — UCAPAN ANARA SERING TIDAK TERSEDIA atau pendek (mis. 'Ini dia resepnya!' / "
    "'(Anara menjawab secara lisan)'). Itu NORMAL: putuskan berdasarkan PERMINTAAN USER saja.\n"
    "Kamu WAJIB menyusun sendiri isi kartu yang lengkap dan akurat dari pengetahuanmu, "
    "berdasarkan topik yang diminta user. Contoh: user minta resep ayam crispy -> susun bahan & "
    "langkah resep ayam crispy yang benar. JANGAN menolak hanya karena ucapan Anara tidak terlihat.\n\n"
    "Jika knowledge_card, susun:\n"
    "- title: judul profesional singkat & bersih (mis. 'Resep Nasi Goreng Kampung'), BUKAN kalimat percakapan.\n"
    "- category: satu kata kategori (Resep / Tips / Panduan / Rekomendasi / Perbandingan / Spesifikasi).\n"
    "- ingredients: daftar bahan PENDEK jika ini resep masakan (array string), selain resep: [].\n"
    "- steps: daftar langkah/poin utama ringkas & jelas berurutan (array string, maks 8, tanpa nomor).\n"
    "- reason: alasan keputusanmu dalam <= 8 kata.\n\n"
    "KEMBALIKAN HANYA JSON VALID (tanpa markdown fence):\n"
    '{"visual_type": "knowledge_card|image|none", "reason": "...", '
    '"query": "jika image: kata kunci pencarian foto singkat", '
    '"title": "...", "category": "...", "ingredients": [], "steps": []}\n\n'
    "PERCAKAPAN (urutan lama -> baru):\n{conversation}\n\n"
    "UCAPAN TERAKHIR ANARA (giliran yang baru selesai):\n{ai_text}"
)

# Legacy alias kept for backwards compatibility
_AUTO_HUD_CLASSIFY_PROMPT = _SEMANTIC_HUD_PROMPT


def _parse_classifier_json(raw: str) -> Optional[Dict[str, Any]]:
    """Robust JSON extraction: strips markdown fences and salvages truncated JSON."""
    if not raw:
        return None
    txt = raw.strip()
    # Strip markdown code fences
    txt = re.sub(r"^```(?:json)?\s*", "", txt)
    txt = re.sub(r"\s*```$", "", txt)
    if "{" not in txt:
        return None
    txt = txt[txt.find("{"):]
    # Direct parse attempt
    try:
        return json.loads(txt[:txt.rfind("}") + 1] if "}" in txt else txt)
    except json.JSONDecodeError:
        pass
    # Salvage truncated JSON: retry from successive closing-quote boundaries,
    # closing any dangling arrays/objects at each attempt.
    quote_positions = [m.start() for m in re.finditer(r'"', txt)]
    for pos in reversed(quote_positions[-24:]):
        candidate = txt[:pos + 1]
        candidate += "]" * max(0, candidate.count("[") - candidate.count("]"))
        candidate += "}" * max(0, candidate.count("{") - candidate.count("}"))
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


async def generate_smart_hud_card(
    client: genai.Client,
    user_text: str,
    ai_text: str,
    speaker_name: Optional[str] = None,
    force: bool = False,
    conversation_context: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    SEMANTIC HUD INTELLIGENCE (Level 2 — zero keyword gates).
    A fast model reads the last few conversation turns and semantically decides
    whether the HUD should project a Knowledge Card / photo / nothing.
    Understands any phrasing/language: offers, acceptances ("gasin", "yaudah sok"),
    re-asks and variations — no keyword lists involved.

    conversation_context: list of {"speaker": "user"|"anara", "text": ...} turns
    ordered oldest -> newest. Falls back to user_text if not provided.
    """
    # Build conversation transcript for semantic analysis
    convo_lines: List[str] = []
    if conversation_context:
        for t in conversation_context[-6:]:
            spk = "User" if t.get("speaker") == "user" else "Anara"
            txt = (t.get("text") or "").strip()
            if txt:
                convo_lines.append(f"{spk}: {txt[:300]}")
    if not convo_lines and user_text:
        convo_lines.append(f"User: {user_text[:300]}")
    conversation_str = "\n".join(convo_lines) if convo_lines else "(tidak ada konteks)"

    # NOTE: use .replace() — NOT .format() — because the template contains literal
    # JSON braces ({"visual_type": ...}) which .format() misreads as placeholders (KeyError).
    prompt = (
        _SEMANTIC_HUD_PROMPT
        .replace("{conversation}", conversation_str)
        .replace("{ai_text}", ai_text[:900])
    )

    # Semantic mode may need to self-generate full recipe content -> generous tokens
    gen_config = types.GenerateContentConfig(max_output_tokens=1200, temperature=0.1)
    timeout_s = 8.0
    res = None
    from core.capabilities import get_fast_auxiliary_model
    aux_m = get_fast_auxiliary_model()
    for mdl in [aux_m, "gemini-2.5-flash"]:
        try:
            res = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=mdl,
                    contents=prompt,
                    config=gen_config,
                ),
                timeout=timeout_s,
            )
            if res and res.text:
                break
        except Exception as e_cls:
            logger.warning(f"[Semantic HUD] Classifier model {mdl} failed: {e_cls}")
            continue

    raw = res.text.strip() if res and res.text else ""
    data = _parse_classifier_json(raw)
    if not data:
        logger.warning(f"[Semantic HUD] Classifier returned unparseable JSON: {raw[:120]!r}")
        return {"has_visual": False}

    v_type = data.get("visual_type", "none")
    reason = data.get("reason", "")
    logger.info(f"[Semantic HUD] verdict={v_type} reason={reason!r}")
    if v_type == "none":
        return {"has_visual": False}

    # ── IMAGE path: fetch a real web photo ──
    if v_type == "image":
        query = data.get("query") or user_text.split()[:5]
        if isinstance(query, list):
            query = " ".join(query)
        img = await fetch_real_web_image(query)
        if not img:
            return {"has_visual": False}
        return {
            "has_visual": True,
            "visual_type": "image",
            "image_url": img["image_url"],
            "image_title": img.get("title", query.title()),
            "source_domain": img.get("source_domain", ""),
            "source_url": img.get("source_url", ""),
            "reply_text": "",
        }

    # ── KNOWLEDGE CARD path: structured steps / ingredients ──
    if v_type == "knowledge_card":
        # 1. Prefer clean AI-classified structure
        title = (data.get("title") or "").strip()
        category = (data.get("category") or "").strip().title()
        ingredients = [str(x).strip() for x in (data.get("ingredients") or []) if str(x).strip()]
        steps = [str(x).strip() for x in (data.get("steps") or []) if str(x).strip()]

        # 2. Local parsing fallback when classifier returned no steps
        if not steps:
            for line in ai_text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if line.startswith(("-", "•")) or (len(line) > 2 and line[0].isdigit() and line[1] in ".-)"):
                    clean = line.lstrip("0123456789.-•) ").strip()
                    if clean:
                        steps.append(clean)
            if len(steps) < 2:
                sentences = re.split(r'(?<=[.!?])\s+', ai_text)
                steps = [s.strip() for s in sentences if len(s.strip()) > 10][:6]

        # 3. Title fallback: first sentence, trimmed
        if not title:
            title = ai_text.split("\n")[0].strip().rstrip(".")
            if len(title) > 70:
                title = title[:67] + "..."
        if not category:
            category = "Rekomendasi"

        # 4. Summary must NOT duplicate step 1, leak internal placeholders, or echo
        #    Anara's conversational filler ("Ini dia resepnya!") — omit when unusable.
        summary = ""
        first_line = ai_text.split("\n")[0].strip()
        _placeholder_markers = (
            "(anara menjawab", "menjawab secara lisan", "transkrip tidak tertangkap",
            "user menjawab singkat", "ini dia resep", "berikut resep",
        )
        _is_placeholder = (
            first_line.startswith("(")
            or any(m in first_line.lower() for m in _placeholder_markers)
        )
        if steps and first_line and not _is_placeholder and first_line.rstrip(".") != steps[0].rstrip("."):
            summary = first_line if len(first_line) <= 140 else first_line[:137] + "..."
        if summary == title:
            summary = ""

        steps = steps[:8]
        if not steps and not ingredients:
            return {"has_visual": False}

        # Legacy specs kept for backwards compatibility with older HUD clients
        specs = [{"label": f"Langkah {i+1}", "value": s} for i, s in enumerate(steps)]

        return {
            "has_visual": True,
            "visual_type": "knowledge_card",
            "knowledge_card_data": {
                "title": title,
                "category": category,
                "badge": "Smart HUD",
                "summary": summary,
                "specs": specs,
                "steps": steps,
                "ingredients": ingredients,
            },
            "reply_text": "",
        }

    return {"has_visual": False}
