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

## 🆕 Agent Core kuchaytirildi (Hermes'dan ustun)

- **`titan_agent/agent.py`**: yangi `TITAN_SYSTEM_PROMPT` — **Plan-Act-Verify-Report**
  intizomi: har doim avval reja, keyin aniq harakat, natijani tekshirish va yakuniy hisobot.
- **Jonli tool katalogi**: har bir aylanishda mavjud barcha vositalar (built-in + MCP)
  avtomatik system promptga qo'shiladi (`LIVE TOOL CATALOG`) — model imkoniyatlarini aniq biladi.
- **Samaradorlik qoidalari**: keraksiz qadamlardan qochish, ma'lum natijalarni qayta
  so'ramaslik, maqsadga erishilganda darhol to'xtash — kamroq token, tezroq javob.
- **`titan_agent/web_ui/app.js`**: Puter brauzer rejimidagi system prompt ham xuddi
  backend darajasiga ko'tarildi (tool katalogi + intizom + til qoidasi).

## 🆕 PowerShell / CLI yaxshilanishlari

- **`start-titan.ps1`** (yangi): avtomatik Python tekshiruvi, `venv` yaratish, qaramliklarni
  o'rnatish, `.env` ni yaratish va Web/CLI ishga tushirish. Parametrlar: `-CLI`, `-Port`,
  `-Provider`, `-Model`, `-NoBrowser`.
- **`start.bat`** endi PowerShell skriptiga yo'naltiradi (bitta bosish bilan ishlayveradi).
- **`run.py`**: yangi `--provider` va `--model` bayroqlari — config importidan oldin
  `TITAN_PROVIDER` / `TITAN_MODEL` ni o'rnatadi (masalan: `python run.py --provider ollama --model hermes3:8b`).
- **`cli.py`**: `puter` provayderi CLI'da tanlangan bo'lsa (Puter faqat brauzerda ishlaydi),
  avtomatik ravishda mahalliy **Ollama** modellarini qidiradi va unga o'tadi; topilmasa
  foydalanuvchiga aniq yo'l-yo'riq ko'rsatadi.

## 🆕 GitHub'ga tayyorlash

- **`git init` + birinchi commit** (26 fayl, 3948 satr).
- **`.gitignore`** (yangi): `.env` (sir), `venv/`, `__pycache__/`, `*.db`, `workspace/`, `*.zip`
  va boshqa runtime/IDE fayllari chiqarib tashlanadi.
- **`LICENSE`** (yangi): MIT litsenziyasi.
- **`.github/workflows/tests.yml`** (yangi): CI — push/PR da Python 3.10/3.12 bilan
  `pytest` avtomatik ishlaydi.
- **`README.md`** qayta yozildi: badge'lar, PowerShell ko'rsatmalari, Puter bepul modellar
  yo'nalishi, loyiha tuzilishi, litsenziya.
- **`mcp_servers.json`** portativ qilindi: qattiq yo'l o'rniga `{WORKSPACE}` placeholder —
  `mcp_client.py` uni avtomatik haqiqiy yo'lga almashtiradi (har qanday mashinada ishlaydi).

## ✅ Tasdiqlangan holat

- `python -m pytest tests -q` → **13 passed**
- Server `python run.py` → ishga tushadi, Web UI `http://127.0.0.1:7860`
- MCP `filesystem` serverni (14 vosita) `{WORKSPACE}` placeholder bilan toza ulaydi
- Config: `puter / deepseek/deepseek-v4-pro`
- Chat oqimi: status → step_start → natija/xato (boshqariladigan)
- Git: `3b20010` root commit, `master` branch'ida

## 🆕 Hermes max darajasidan ham ustun — Agent Core 2.0

Hermes 405B (max tarif) faqat matn ishlab chiqara oladi — u real dunyoda **hech narsa bajara
olmaydi**: buyruq yurgiza olmaydi, natijani tekshira olmaydi, xotirasiz. Titan endi barcha
ana shu qatlamlarda butunlay ustun:

### 1. Reflection (o'z-o'zini tanqid) passi — `agent.py`
- Task tool'lar bilan bajarilgach, model yakuniy javob berishdan **OLDIN** o'z ishini
  tanqidiy tekshiradi (`REFLECTION_PROMPT`): foydalanuvchi so'rovi to'liq bajarildimi?
  Barcha da'volar tool natijalari bilan tasdiqlanganmi? Xatolar bormi?
- Reflection yetishmovchilik topsa → avtomatik **qo'shimcha tool chaqiradi** va tuzatadi,
  aks holda sayqallangan yakuniy javobni beradi.
- Bu Hermes (bir o'tishli model) qila olmaydigan haqiqiy **verification loop**.

### 2. Faol uzoq muddatli xotira tool'lari — Hermesda umuman yo'q
- `memory_save(key, value, category?)` — faktni abadiy eslab qoladi (barcha sessiyalarda).
- `memory_search(query)` — avvalgi sessiyalarda saqlangan faktlarni eslaydi.
- Agent endi foydalanuvchi ismi, afzalliklari, qarorlarini o'zi mustaqil saqlaydi va eslaydi.

### 3. Real-dunyo nazorati tool'lari
- `system_info()` — jonli OS / CPU / RAM / disk / Python / Node / Git ma'lumotlari.
- `manage_processes(action: list|kill, pattern?)` — ishlayotgan jarayonlarni ro'yxatlaydi
  yoki to'xtatadi (tasklist/taskkill yoki ps/kill).
- Frontend (Puter rejimi) system prompti ham yangi tool katalogi + reflection qoidasi bilan
  to'ldirildi.

### Jonli sinov natijalari (localhost:7860)
- `system_info` → Windows 11, 12 CPU core, 15.3 GB RAM, Python 3.12, Node v24, Git 2.55
- `manage_processes` → python jarayonlari PID bilan ro'yxatlandi
- `memory_save`/`memory_search` → "user_lang = O'zbek" saqlandi va topildi