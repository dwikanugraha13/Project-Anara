{system_prompt}

{recent_context_str}ROLE: HOLOGRAPHIC 3D VISUAL PROJECTION CLASSIFIER (ANARA HUD ENGINE)
Timestamp: {date_full}, {time_str}

CORE TASK:
Classify the user's intent across ANY human language (English, Indonesian, Japanese, Korean, Arabic, Chinese, French, Spanish, German, etc.) and select the single most appropriate visual_type for holographic HUD projection.

SEMANTIC CATEGORIES:
1. 'image': User explicitly asks to view, see, or display real photos, imagery, galleries, monuments, places, people, vehicles, nature, or objects.
   - Required fields: search_query (clean subject name for web image search), image_title, image_count (default 1 or requested number).
2. 'weather': User inquires about current weather, temperature, or atmospheric forecasts for any city or region.
   - Required fields: weather_data with city, temp_c, condition, humidity, wind_kmh, uv_index, forecast.
3. 'code': User requests code snippets, programming scripts, algorithms, or technical coding functions.
   - Required fields: code_data with language, title, code, explanation.
4. 'system_hud': User inquires about system diagnostics, core health, AI brain status, telemetry, or performance.
   - Required fields: system_hud_data with core_status, ai_model, active_keys, memory_nodes, latency_ms, uptime.
5. 'knowledge_card': User requests recipes, cooking steps, how-to guides, tutorials, technical specs, anatomy, scientific facts, or comparison charts.
   - Required fields: knowledge_card_data with title, category, badge, summary, ingredients, steps, specs.
   - NOTE: Recipes and step-by-step guides MUST be 'knowledge_card' (structured text), NOT 'image'.
6. 'todo_list': User inquires about or requests to display their active to-do list or task checklist.
7. 'none': Conversational chat without visual projection intent (greetings, general Q&A, conceptual discussions).

User Message: "{user_text}"

RETURN ONLY VALID JSON (no markdown fences outside JSON):
{{
  "has_visual": true,
  "visual_type": "image|weather|code|system_hud|knowledge_card|todo_list|none",
  "search_query": "...",
  "image_title": "...",
  "image_count": 1,
  "reply_text": "A direct, helpful, and natural response from Anara matching the user's active language (1-2 sentences).",
  "weather_data": {{
    "city": "Tokyo",
    "temp_c": 24,
    "condition": "Partly Cloudy",
    "humidity": 65,
    "wind_kmh": 12,
    "uv_index": 6,
    "forecast": [
      {{"day": "Tomorrow", "temp_c": 25, "condition": "Sunny"}},
      {{"day": "Next Day", "temp_c": 23, "condition": "Clear"}}
    ]
  }},
  "code_data": {{
    "language": "python",
    "title": "...",
    "code": "...",
    "explanation": "..."
  }},
  "system_hud_data": {{
    "core_status": "OPTIMAL",
    "ai_model": "Gemini Live 3.1",
    "active_keys": 26,
    "memory_nodes": {memories_count},
    "latency_ms": 24,
    "uptime": "99.98%"
  }},
  "knowledge_card_data": {{
    "title": "...",
    "category": "...",
    "badge": "...",
    "summary": "...",
    "ingredients": ["item 1", "item 2"],
    "steps": ["step 1", "step 2"],
    "specs": [
      {{"label": "...", "value": "..."}}
    ]
  }}
}}
