# ⚡ TITAN AGENT — Hermes 3 dan ancha kuchli Avtonom AI Tizimi

> **Titan Agent** — bu Nous Research Hermes 3, DeepSeek-R1 va zamonaviy eng kuchli AI agentlar imkoniyatlarini
> o'zida birlashtirgan, to'liq mustaqil ishlay oladigan **Agentik AI Platformasi**.

U nafaqat matn yozadi, balki mustaqil fikrlaydi, kompyuteringizda buyruqlar va dasturlarni ishga tushiradi,
internetdan jonli qidiradi va **Model Context Protocol (MCP)** orqali har qanday ilova va ma'lumotlar bazasiga ulanadi.

| CI Status | Litsenziya | Python |
|---|---|---|
| [![CI - Tests](https://github.com/YOUR_USERNAME/titan-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/YOUR_USERNAME/titan-agent/actions) | MIT | 3.10+ |

---

## 🚀 Asosiy Afzalliklari (Nega Hermes 3 dan ancha kuchli?)

1. **Ko'p Modelli va Moslashuvchan (Multi-LLM Routing)**:
   - 🆓 **Puter.js — 500+ BEPUL modellar** (kalitsiz, to'g'ridan-to'g'ri brauzerda): DeepSeek V4 Pro, Claude, GPT-4o, Llama va boshqalar (`:free` varianti bilan)
   - Nous Research Hermes 3 (Llama 3.1 405B / 70B / 8B)
   - DeepSeek-R1 / V3 (Chuqur mantiqiy fikrlash)
   - OpenAI GPT-4o / Claude 3.7 Sonnet
   - Mahalliy bepul **Ollama** (internetsiz va mutlaqo maxfiy ishlash)
2. **🔌 Model Context Protocol (MCP) Integratsiyasi**:
   - `mcp_servers.json` orqali GitHub, SQLite, PostgreSQL, Filesystem, Slack, Brave Search va boshqa har qanday MCP serverlarni to'g'ridan-to'g'ri ulaydi!
3. **🛠️ Kuchli Ichki Asboblar (Built-in Tools)**:
   - **PowerShell / Terminal buyruqlari**: kompyuterni to'liq boshqarish.
   - **Fayllar tizimi**: o'qish, yaratish, tahrirlash (regex replace).
   - **Jonli Veb Qidiruv**: DuckDuckGo orqali 100% tekin va kalitsiz internetdan yangi ma'lumotlarni olish.
   - **Python Sandbox**: murakkab hisob-kitoblar va skriptlarni alohida jarayonda bajarish.
   - **Deep Search**: ko'p manbali chuqur tadqiqot dossyeri.
   - **Deep Coder**: to'liq dasturiy ta'minot sikli (fayl yozish, sintaksis tekshirish, test yurgizish).
   - **Ilovalarni ochish**: Windows dasturlarini ishga tushirish.
4. **🧠 Uzoq Muddatli Xotira (SQLite Memory)**:
   - Suhbatlar va o'rganilgan faktlarni SQLite bazasida saqlaydi va keyingi sessiyalarda ham eslab qoladi.
5. **💻 Ikkita Qulay Interfeys**:
   - **Web Dashboard**: Zamonaviy Dark Cyberpunk Glassmorphic vizual boshqaruv paneli (fikrlash, asboblar animatsiyasi, fayllar boshqaruvi, 500+ bepul model brauzeri).
   - **Terminal CLI**: Rich kutubxonasi bilan konsoldan ishlash.
6. **⚡ Yangi: Agent Core kuchaytirildi** — Plan-Act-Verify-Report intizomi, jonli tool katalogi va samaradorlik qoidalari — har bir buyruqda kamroq qadam bilan aniqroq natija.

---

## 🚀 Tezkor ishga tushirish

### 1-usul: Windows — `start.bat` (bitta bosish)
`start.bat` faylini ikki marta bosing va Web yoki CLI rejimini tanlang. Skript `venv`, qaramliklar va `.env` ni avtomatik sozlaydi.

### 2-usul: PowerShell (tavsiya etiladi)
```powershell
# Web Dashboard (default):
.\start-titan.ps1

# Terminal CLI rejimida:
.\start-titan.ps1 -CLI

# Boshqa portda:
.\start-titan.ps1 -Port 8000

# Muayyan provayder/model bilan:
.\start-titan.ps1 -Provider ollama -Model hermes3:8b
```

### 3-usul: Qo'lda
```bash
# Web Dashboardni ishga tushirish:
python run.py

# Yoki Terminal CLI rejimida ishga tushirish:
python run.py --cli

# Provayder/modelni vaqtincha almashtirish:
python run.py --provider ollama --model hermes3:8b
```

Web dashboard avtomatik ravishda brauzeringizda `http://127.0.0.1:7860` manzilida ochiladi.

> 💡 **Mutlaqo kalitsiz ishlatish:** Web Dashboardda sozlamalar (⚙️) dan **Puter.js** provayderini tanlang —
> **"🌐 Barcha Bepul Modellar"** tugmasi bilan 500+ bepul modelni ko'ring, `:free` variantini tanlang —
> DeepSeek V4 Pro / Claude / GPT-4o kabi modellar 100% bepul, API kalit talab qilmaydi va to'g'ridan-to'g'ri
> brauzeringizda ishlaydi. Yoki mahalliy **Ollama** dan foydalaning.

---

## ⚙️ Sozlamalar va API Kalitlari

Web interfeysning yuqori o'ng burchagidagi sozlamalar tugmasi orqali yoki `.env` faylida provayderni belgilashingiz mumkin.

**Klavon resurs:**
```bash
# Birinchi ishga tushirishda .env ni yaratish (agar mavjud bo'lmasa):
copy .env.example .env
```

```env
# Puter.js — bepul, kalitsiz (brauzerda ishlaydi):
TITAN_PROVIDER=puter
TITAN_MODEL=deepseek/deepseek-v4-pro

# Yoki API kalitli provayder:
TITAN_PROVIDER=openrouter
TITAN_MODEL=nousresearch/hermes-3-llama-3.1-405b:free
OPENROUTER_API_KEY=your_key_here
```

### Mahalliy Ollama bilan bepul ishlatish:
1. Kompyuteringizda Ollamani ishga tushiring: `ollama run hermes3` yoki `ollama run qwen2.5-coder`
2. Sozlamalardan Provayderni **Ollama** ga o'tkazing — hech qanday API kalit talab qilinmaydi!

> ⚠️ **Eslatma:** Puter.js faqat **brauzer (Web Dashboard)** da ishlaydi — u `puter.ai` SDK'sini
> ishga tushiradigan veb-sahifa ichida yashaydi. CLI'da Puter tanlangan bo'lsa, Titan avtomatik ravishda
> Ollama'ga o'tadi, aks holda foydalanuvchiga yo'l-yo'riq ko'rsatadi.

---

## 🔌 MCP Serverlarini qo'shish

`mcp_servers.json` fayliga istalgan MCP serveringizni qo'shishingiz mumkin. `{WORKSPACE}` va `{BASE_DIR}`
placeholder'lari avtomatik ravishda haqiqiy yo'llarga almashtiriladi — shuning uchun konfiguratsiya portativ:
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "{WORKSPACE}"]
    }
  }
}
```
Titan Agent ishga tushganda bu serverlarning barcha vositalarini avtomatik aniqlaydi va o'zining aqliy sikliga qo'shadi!

> 🔎 **Izoh:** Internetdan ma'lumot olish uchun Titan'ning o'zida `web_search` va `scrape_webpage`
> asboblari mavjud — alohida MCP fetch serveri shart emas (eski `@modelcontextprotocol/server-fetch`
> paketi npm'dan olib tashlangan).

---

## 🧪 Testlar

```bash
python -m pytest tests -q
```

GitHub Actions CI (`tests.yml`) `push` va `pull_request` da Python 3.10/3.12 bilan testlarni avtomatik yurgizadi.

---

## 🗂️ Loyiha Tuzilishi

```
titan-agent/
├── run.py                    # Asosiy kirish nuqtasi (Web/CLI)
├── cli.py                    # Terminal CLI rejimi
├── start-titan.ps1           # PowerShell ishga tushirish skripti
├── start.bat                 # Windows bitta-bosish ishga tushiruvchi
├── requirements.txt
├── mcp_servers.json          # MCP server konfiguratsiyasi
├── .env.example              # Sozlamalar shabloni (nusxalab .env qiling)
├── tests/                    # pytest testlari (9 ta)
├── titan_agent/
│   ├── agent.py              # TitanAgent — asosiy agentik sikl (Plan-Act-Verify)
│   ├── llm_client.py         # Multi-provider LLM mijoz (puter/openrouter/groq/deepseek/ollama/lmstudio/openai)
│   ├── tools.py              # Ichki asboblar (execute_command, web_search, deep_search, deep_coder...)
│   ├── mcp_client.py         # Model Context Protocol ulanish boshqaruvi
│   ├── memory.py             # SQLite uzoq muddatli xotira
│   ├── config.py             # .env dan sozlamalar
│   └── web_ui/               # Web Dashboard (index.html, app.js, style.css)
└── workspace/                # Agent ishchi katalogi (git'ga kirmaydi)
```

---

## 📜 Litsenziya

MIT License — batafsil `LICENSE` faylida.

---

## 🤝 Hissa qo'shish

1. Fork va clone qiling
2. Yangi branch yarating: `git checkout -b feature/x`
3. O'zgartirishlar kiritib, testlarni yurgizing: `python -m pytest tests -q`
4. Pull Request oching

## ⭐ Qo'llab-quvvatlash

Loyiha sizga yoqsa — ⭐ bosing! Savollar, takliflar va muammolar uchun GitHub Issues bo'limidan foydalaning.