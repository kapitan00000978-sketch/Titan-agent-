# TITAN AGENT — O'zgarishlar jurnali (CHANGES)

Ushbu loyiha "tugatish" ishi davomida kiritilgan barcha tuzatish va takomillashtirishlar.

## 🔴 Kritik tuzatishlar

### 1. `titan_agent/server.py` — server ishga tushmasdi
- **Muammo:** `Dict` va `Any` `typing` dan import qilinmagan → modul import paytida
  `NameError: name 'Dict' is not defined` bilan qulab, butun veb-dashboard ishlamas edi.
- **Yechim:** `from typing import Any, Dict` importi qo'shildi.
- **Yechim:** `ToolExecuteRequest.arguments` uchun mutable default `{}` → `Field(default_factory=dict)`.

### 2. `titan_agent/mcp_client.py` — Windows MCP barqarorligi
- **Muammo:** MCP server to'xtatilganda asyncio transportlari berkitilmasdi → Windows'da
  `ValueError: I/O operation on closed pipe` ResourceWarning spam'i.
- **Yechim:** `stop()` endi `_read_task` ni bekor qilib kutadi, jarayonni to'liq to'xtatadi va
  stdin/stdout/stderr trubalarini yopadi. `_listen_stdout` ham `finally` bilan toza yopiladi.
- **Yechim:** `start()` xato bo'lsa ``stop()`` orqali jarayonni tozalaydi.
- **Yechim:** `send_request` vaqt tugasa aniq xato xabari qaytaradi (avval bo'sh edi).

### 3. `mcp_servers.json` — buzilgan fetch server olib tashlandi
- **Muammo:** `@modelcontextprotocol/server-fetch` paketi npm'dan olib tashlangan (HTTP 404),
  shuning uchun MCP boshlanishda muvaffaqiyatsiz bo'lib, `fetch` server ulanmas edi.
- **Yechim:** Config'dan olib tashlandi; `filesystem` (14 vosita) barqaror ulanadi.
  Internet qidiruv Titan'ning o'z `web_search` / `scrape_webpage` asboblari orqali amalga oshadi.

### 4. `titan_agent/llm_client.py` — Puter.js provayderi qo'llab-quvvatlanadi
- **Muammo:** Frontendda "Puter.js (bepul, kalitsiz)" provayderi bor edi, lekin backend uni
  tanimasdi → sozlamani saqlashda backend OpenAI'ga "buzilgan" holda o'tib ketardi.
- **Yechim:** `puter` provayderi `_setup_credentials` da taniladi (base_url/api_key bo'sh).
- **Yechim:** `chat_completion` server tomondan `puter` chaqirilsa aniq xato beradi
  ("Puter.js faqat brauzerda ishlaydi").
- **Yechim:** HTTP 401/403 xatolariga yo'l-yo'riq izohi qo'shildi.

## 🟡 Takomillashtirishlar

### 5. `tests/test_components.py` — pytest-ga moslashtirildi
- **Muammo:** Eski test fayli pytest tomonidan topilmasdi ("no tests ran") — skript shaklida edi.
- **Yechim:** 9 ta haqiqiy pytest test funksiyasi yozildi (`python -m pytest tests -q` → **9 passed**).

### 6. Konfiguratsiya standartlari
- `.env` / `.env.example` → default `TITAN_PROVIDER=puter`, `TITAN_MODEL=deepseek/deepseek-v4-pro`
  (developer.puter.com bepul modellari; API kalit shart emas).

### 7. `README.md` yangilandi
- Puter.js bepul yo'nalishi, Ollama eslatmasi, `pytest` buyrug'i,
  fetch server izohi qo'shildi.

## 🆕 Yangi funksiya: "Barcha Bepul Puter Modellari" brauzeri

- **`index.html` + `app.js` + `style.css`**: Sozlamalarda endi "🌐 Barcha Bepul Modellar"
  tugmasi mavjud — bosilganda `puter.ai.listModels()` orqali Puter'dagi **BARCHA**
  modellar yuklanadi (500+ model: Claude, GPT, Gemini, DeepSeek, Llama, FLUX va boshq.).
- **"🆓 Bepul / Hammasi" yorliqlari**: Bepul yorlig'i faqat `:free` qo'shimchali
  variantlarni ko'rsatadi (bepul, kalitsiz, rate limit bilan). 
- **Jonli qidiruv**: model nomi, ID yoki provayder bo'yicha filtrlanadi.
- **Provider guruhlanishi**: modellar provayder nomi bilan guruhlangan.
- **Avtomatik yuklash**: Sozlamalar ochilganda yoki provayder "Puter.js" tanlanganda
  model ro'yxati avtomatik yuklanadi.
- **Maslahat**: Har qanday model ID oxiriga `:free` qo'shish orqali bepul ishlatish mumkin
  (masalan `deepseek/deepseek-v4-pro:free`). Chat oqimi tanlangan model nomini ko'rsatadi.

## ✅ Tasdiqlangan holat

- `python -m pytest tests -q` → **9 passed**
- Server `python run.py` → ishga tushadi, Web UI `http://127.0.0.1:7860`
- MCP `filesystem` serverni (14 vosita) toza ulaydi
- Config: `puter / deepseek/deepseek-v4-pro`
- Chat oqimi: status → step_start → natija/xato (boshqariladigan)