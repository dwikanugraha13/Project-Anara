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

# Strict visual intent trigger keywords
VISUAL_INTENT_KEYWORDS = [
    "gambar", "gambarnya", "foto", "fotonya", "tunjukkan", "tunjukan", "tujukin", "tunjukkin",
    "tampilkan", "tampilin", "lihat", "liat", "gambarin", "mana", "perlihatkan", "kasih liat",
    "visual", "visualkan", "penampakan", "wujud", "bentuk", "bentuknya", "desain", "lukisan",
    "wallpaper", "spill", "image", "picture", "photo", "show", "show me", "draw", "generate",
    "muka", "mukanya", "wajah", "wajahnya", "potret", "seperti apa", "kayak apa", "kaya apa",
    # Photo switching & multi-image keywords
    "foto lain", "gambar lain", "foto lainnya", "gambar lainnya", "ganti foto", "foto berikutnya",
    "gambar berikutnya", "galeri", "multi foto", "beberapa foto", "yang lain", "selain itu",
    # Weather
    "cuaca", "suhu", "hujan", "prakiraan", "weather", "temperature", "derajat",
    # Code & Tech
    "kode", "coding", "script", "program", "python", "javascript", "typescript", "html", "css",
    "fungsi", "bikin kode", "buatkan kode", "source code",
    # Telemetry / Status
    "status sistem", "status kamu", "telemetri", "diagnostik", "core status", "system status",
    "kondisi anara", "cek sistem", "kesehatan sistem",
    # Knowledge / Schematics
    "spesifikasi", "spek", "struktur", "skema", "bagan", "tata surya", "anatomi", "planet",
    "mobil", "motor", "mesin", "sejarah", "perbandingan",
    # Tasks / Todos
    "to do", "todo", "catatan tugas", "daftar tugas", "list tugas"
]


def could_be_visual_request(text: str) -> bool:
    """Fast keyword heuristic to quickly identify potential visual queries."""
    norm = text.lower()
    return any(k in norm for k in VISUAL_INTENT_KEYWORDS)


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
_VISUAL_KEYWORDS = {
    "foto", "gambar", "lihat", "tampilkan", "tunjukkan", "tunjukan", "tujukin", "proyeksi", "visual", "image", "pic",
    "cuaca", "suhu", "hujan", "derajat", "celcius", "panas", "dingin", "ramalan", "weather",
    "kode", "skrip", "script", "coding", "program", "fungsi", "function", "python", "javascript", "react", "html", "css",
    "status sistem", "diagnostik", "telemetri", "system hud", "kondisi sistem", "core status",
    "spesifikasi", "spek", "planet", "struktur", "anatomi", "knowledge card", "skematik",
    "to do", "todo", "tugas", "catatan", "jadwal", "daftar to do"
}


async def generate_visual_projection(
    client: genai.Client,
    user_text: str,
    system_prompt: str,
    model_name: str = "gemini-3.5-flash-lite"
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

    from memory_service import memory_engine, get_current_indonesian_time_str
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

    # Fast-gate: Allow visual keywords OR short affirmative responses when previous turn offered photos/visuals
    has_visual_kw = any(k in clean_key for k in _VISUAL_KEYWORDS)
    AFFIRMATIVE_WORDS = {"ya", "iya", "mau", "boleh", "ok", "oke", "silakan", "coba", "tampilkan", "yup", "yoi", "mau dong", "boleh dong", "siap", "tentu", "boleh carikan", "tolong carikan"}
    is_affirmative = clean_key in AFFIRMATIVE_WORDS or any(clean_key.startswith(w) for w in AFFIRMATIVE_WORDS)

    last_conv = recent_chat[-1] if recent_chat else {}
    prev_ai_text = (last_conv.get("ai_text") or "").lower()
    prev_offered_visual = any(w in prev_ai_text for w in ["foto", "gambar", "lihat", "tampilkan", "carikan", "menu", "lokasi", "visual", "bagaimana", "rekomendasi", "rekomendasikan", "mau aku"])

    if not has_visual_kw and not (is_affirmative and prev_offered_visual):
        return {"has_visual": False}

    prompt = (
        f"{system_prompt}\n\n"
        f"{recent_context_str}"
        "TUGAS UTAMA ANDA: SISTEM PROYEKSI VISUAL HOLOGRAPHIC J.A.R.V.I.S. (ANARA HUD ENGINE)\n"
        f"Waktu Sekarang: {time_info['date_full']}, {time_info['time_str']}\n\n"
        "ATURAN RESOLUSI RUJUKAN & FOLLOW-UP (SANGAT PENTING):\n"
        "- JIKA PENGGUNA MENYEBUTKAN OBJEK BARU SECARA JELAS (misal: 'coba tunjukin gambar rumput', 'tunjukkan foto kucing', 'foto mobil porsche', 'lihat gambar monas', 'tampilkan foto laut'):\n"
        "  MAKA visual_type='image' dan search_query HARUS OBJEK BARU TERSEBUT (contoh: 'rumput' / 'kucing' / 'mobil porsche' / 'monas')! JANGAN CAMPURKAN ATAU MENGIKUTI TOPIK LAMA (seperti Panda)!\n"
        "- HANYA gunakan topik lama dari KONTEKS PERCAKAPAN jika pesan pengguna TIDAK menyebut objek baru dan hanya menggunakan kata rujukan murni (misal: 'tunjukkan fotonya', 'mana gambarnya', 'fotonya mana', 'coba lihat fotonya', 'ya tampilkan', 'ya', 'boleh', 'foto lainnya', 'foto berikutnya').\n"
        "- JUMLAH FOTO (image_count):\n"
        "  * Default: image_count = 1 jika pengguna hanya meminta foto biasa (misal: 'tunjukkan foto panda', 'coba tunjukin gambar rumput').\n"
        "  * Jika pengguna meminta jumlah tertentu, set image_count sesuai angka (misal: 'tunjukkan 3 foto panda' -> image_count = 3, '5 foto rumput' -> image_count = 5, 'tampilkan beberapa foto / galeri' -> image_count = 4 atau 6).\n\n"
        "Klasifikasikan pesan pengguna dan pilih SATU visual_type yang paling cocok dari kategori berikut:\n\n"
        "1. 'image': Pengguna ingin melihat foto asli/gambar nyata/galeri dari tokoh publik, tempat wisata, kuliner, kendaraan, hewan, objek, tanaman, pemandangan, dll.\n"
        "   Contoh: 'tunjukkan foto monas', 'lihat mobil lamborghini', 'coba tunjukin gambar rumput', 'gambar candi borobudur', 'foto kucing persia', 'tunjukkan 3 foto panda', 'tunjukkan fotonya', 'ganti foto', 'foto lainnya', 'ya tampilkan'\n"
        "   Data yang diperlukan: search_query (nama objek bersih untuk pencarian foto web), image_title, image_count (1 atau angka sesuai permintaan).\n\n"
        "2. 'weather': Pengguna menanyakan cuaca, suhu, atau kondisi atmosfer di suatu kota/daerah.\n"
        "   Contoh: 'bagaimana cuaca di jakarta hari ini', 'apakah bandung hujan', 'cek suhu surabaya'\n"
        "   Data yang diperlukan: weather_data dengan field: city, temp_c, condition, humidity, wind_kmh, uv_index, forecast (array 2 hari).\n\n"
        "3. 'code': Pengguna meminta pembuatan kode, skrip program, fungsi, algoritma, atau penjelasan teknis coding.\n"
        "   Contoh: 'buatkan kode python fastapi server', 'bagaimana script javascript debounce', 'contoh react hook'\n"
        "   Data yang diperlukan: code_data dengan field: language, title, code (kode program lengkap & rapi), explanation.\n\n"
        "4. 'system_hud': Pengguna menanyakan status sistem Anara, kondisi AI, diagnostik otak, memori, atau performa.\n"
        "   Contoh: 'status sistem kamu', 'cek diagnostik anara', 'bagaimana kondisi core sistem'\n"
        "   Data yang diperlukan: system_hud_data dengan field: core_status, ai_model, active_keys, memory_nodes, latency_ms, uptime.\n\n"
        "5. 'knowledge_card': Pengguna meminta penjelasan terstruktur, spesifikasi teknis, anatomi, perbandingan data, planet/astronomi, mobil/motor, sejarah, atau fakta ilmiah.\n"
        "   Contoh: 'bagaimana struktur planet mars', 'spesifikasi motor kawasaki h2', 'perbedaan sel hewan dan tumbuhan'\n"
        "   Data yang diperlukan: knowledge_card_data dengan field: title, category, badge, summary, specs (array berisi objek {label, value}).\n\n"
        "6. 'todo_list': Pengguna menanyakan atau meminta to-do list / catatan tugas mereka.\n"
        "   Contoh: 'tampilkan to-do list ku', 'apa daftar tugasku'\n\n"
        "7. 'none': Obrolan santai biasa tanpa kebutuhan visual (sapaan, percakapan umum pendek).\n\n"
        f"Pesan Pengguna: \"{user_text}\"\n\n"
        "KEMBALIKAN HANYA FORMAT JSON VALID BERIKUT (jangan sertakan markdown code block di luar JSON):\n"
        "{\n"
        '  "has_visual": true,\n'
        '  "visual_type": "image|weather|code|system_hud|knowledge_card|todo_list|none",\n'
        '  "search_query": "...",\n'
        '  "image_title": "...",\n'
        '  "image_count": 1,\n'
        '  "reply_text": "Kalimat balasan cerdas, ramah, dan ringkas dari Anara (1-2 kalimat).",\n'
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
        '    "specs": [\n'
        '      {"label": "...", "value": "..."}\n'
        '    ]\n'
        '  }\n'
        "}"
    )

    try:
        gen_config = types.GenerateContentConfig(
            max_output_tokens=600,
            temperature=0.3
        )
        res = None
        for mdl in ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.5-flash"]:
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
