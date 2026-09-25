# Universal Agent HP

[![CI - Universal Agent Tests](https://github.com/kapitan00000978-sketch/Universal-Agent-HP/actions/workflows/tests.yml/badge.svg)](https://github.com/kapitan00000978-sketch/Universal-Agent-HP/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Architecture: Tri--Loop](https://img.shields.io/badge/Architecture-Tri--Loop%20Metacognition-purple.svg)](#architecture-tri-loop-metacognitive-execution)
[![Tests: 675+ Passing](https://img.shields.io/badge/tests-675%2B%20passing-brightgreen.svg)](#testing--security)

Universal Agent HP is an autonomous AI software engineering and operations system built for real-world development environments. It combines **Tri-Loop Metacognitive Reasoning**, an **Autonomous TDD Engine**, **Anthropic Model Context Protocol (MCP)** integration, **Human-in-the-Loop Guardrails**, and **Local Semantic Caching** into a verified, drift-free execution framework.

```
   ┌────────────────────────────────────────────────────────────────────────┐
   │                         UNIVERSAL AGENT HP                             │
   │                                                                        │
   │   [System 1: Fast Intuition] ──> Instant Heuristic Path (0ms)          │
   │   [System 2: Planning Engine] ──> MCTS + Bayes Reasoning + TDD Loop     │
   │   [System 3: Metacognitive]   ──> Shannon Entropy + Dynamic Synthesis  │
   │   [Active Working Memory]     ──> Pinned Operational HUD (No Drift)    │
   └────────────────────────────────────────────────────────────────────────┘
```

---

## Nimalarga Kerak? (Real-World Use Cases)

Universal Agent HP shunchaki oddiy chat-bot emas. U ishlab chiquvchilar, jamoalar va korxonalar uchun quyidagi aniq amaliy muammolarni hal qilish uchun yaratilgan:

### 1. Avtonom Kod Yozish, Testlash va Xatolarni Tuzatish (Self-Healing Bug Fixing)
* **Muammo:** Dasturchilar xatolarni qidirish, sinab ko'rish va takroriy testlarni yurgizishga soatlab vaqt sarflaydi.
* **Universal Agent yechimi:** Agent topshiriqni olgach, avval sinov testini yozadi (`pytest`), test qulashini isbotlaydi (RED), so'ngra kodni yozadi (GREEN) va xavfsizlik invariantlarini tekshiradi (REFACTOR). Agar test o'tmasa, agent o'z xatosini o'zi tahlil qilib kodni mustaqil tuzatadi.

### 2. Xavfsiz GitOps: Tarmoq Ochish va Pull Request (PR) Tayyorlash
* **Muammo:** AI agentlarining to'g'ridan-to'g'ri `main` tarmoqqa yozishi yoki xom kodni commit qilishi loyihani buzib qo'yishi mumkin.
* **Universal Agent yechimi:** Agent har bir vazifa uchun alohida `agent/feature-<nom>` tarmog'ini ochadi. Barcha testlar 100% yashil o'tmaguncha git commit qilinmaydi. Testlar o'tgach, GitHub/GitLab'da to'liq hisobot bilan avtomatik Pull Request ochadi.

### 3. Tashqi Tizimlar bilan 1-Qatorda Ulanish (MCP Integratsiyasi)
* **Muammo:** Har bir ma'lumotlar bazasi yoki servis uchun alohida API yozib chiqish murakkab.
* **Universal Agent yechimi:** Anthropic Model Context Protocol (MCP) standarti orqali dunyodagi istalgan tayyor serverni bitta buyruq bilan ulaydi:
  * `postgres`: SQL so'rovlar va jadvallar tahlili
  * `github`: Masalalar (issues) va PRlarni boshqarish
  * `slack`: Xabarlar va jamoa integratsiyasi
  * `brave_search`: Internetdan eng so'nggi ma'lumotlarni qidirish
  * `filesystem` & `sqlite`: Mahalliy fayllar va bazalar bilan xavfsiz ishlash

### 4. Halokatli Amallarni To'xtatish (Human-in-the-Loop Xavfsizlik)
* **Muammo:** Agentning tasodifan muhim fayllarni o'chirib yuborishi (`rm -rf`), `git push --force` qilishi yoki maxfiy kalitlarni o'zgartirishi xavfi.
* **Universal Agent yechimi:** `DangerousActionClassifier` xavfli amallarni zudlik bilan ushlab qoladi va to'xtaydi:
  > *«Bu fayllarni/amallarni o‘zgartirmoqchiman. Ruxsat berasizmi? [Ha / Yo‘q]»*  
  Inson tasdiqlamaguncha birorta xavfli buyruq bajarilmaydi.

### 5. LLM Token Xarajatini 30–40% Tejash (Semantic Caching)
* **Muammo:** Bitta kod bo'lagi yoki o'xshash savollar uchun har safar qimmatbaho tashqi LLM API'lariga so'rov yuborish ortiqcha xarajat keltirib chiqaradi.
* **Universal Agent yechimi:** Mahalliy SQLite (`semantic_cache.db`) bazasida kosinus vektor o'xshashligi orqali keshdan **0ms** ichida javob beradi va hisoblagichda tejab qolingan tokenlar hamda dollar miqdorini aniq ko'rsatadi.

### 6. Oldingi Xatolardan Saboq Olish (Episodik Xotira)
* **Muammo:** Agentlar bir xil kutubxona versiyasi yoki sintaksis xatosiga qayta-qayta duch kelganda qaytadan adashadi.
* **Universal Agent yechimi:** Agent avvalgi xatolarning barmoq izi (fingerprint) va ularga qo'llangan muvaffaqiyatli kod yechimini `experience_replay.db` da saqlab boradi. Xuddi shunday xato sodir bo'lganda, avvalgi yechimni eslab darhol to'g'rilaydi.

### 7. 100% Maxfiy va Mahalliy Rejim (Air-Gapped Local AI)
* **Muammo:** Kompaniyalar o'zlarining tijorat sirlari bo'lgan kodlarini ommaviy bulutli servislarga yuborishdan cho'chiydi.
* **Universal Agent yechimi:** `Ollama` yoki `LM Studio` orqali kompyuteringizdagi mahalliy modellar bilan to'liq offline ishlay oladi. Bir bayt ham ma'lumot tashqariga chiqmaydi.

---

## Hech Qanday Yolg'onsiz: Nima Qila Oladi va Nima Qila Olmaydi?

### ✅ Tizim Haqiqatda Qila Oladigan Imkoniyatlar (Kod va Testlar Bilan Tasdiqlangan):
1. **Tri-Loop Kognitiv Fikrlash:**
   * **System 1 (Tezkor Intuitsiya):** Oddiy savollar va suhbatlarni vositalarsiz (toolless) 0ms da ajratib darhol javob beradi.
   * **System 2 (ReAct & MCTS):** Murakkab dasturiy masalalarda gipotezalar daraxtini (Bayesian hypothesis tracking) tuzib, qadam-baqadam yechadi.
   * **System 3 (Shannon Entropiya Nazoratchisi):** Agar agent bir nuqtada aylanib qolsa (stagnation), buni matematik aniqlab strategiyani o'zgartiradi.
2. **Kodni Jarrohlik Usulida Yamoqlash (AST Patcher):** Qator raqamlari o'zgarib ketganda ham funksiya va klasslarni xatosiz topib almashtiradi.
3. **Statik Xavfsizlik Skanyeri (Symbolic Checker):** Cheksiz `while True` sikllari, buyruq inyeksiyalari (`shell=True`) va yopilmagan fayllarni kod yurgizilishidan oldin aniqlaydi.
4. **Haqiqiy Ko'p Sessiyali Interfeyslar:**
   * **Textual TUI:** Zamonaviy to'liq ekranli terminal interfeysi (`python run.py`).
   * **Web Dashboard:** Real vaqt rejimida SSE oqimi bilan brauzer konsoli (`python run.py --web`).
   * **CLI & Telegram:** Buyruqlar qatori va mobil boshqaruv bot.
5. **Avtomatlashtirilgan Test To'plami:** Repozitoriyda **675 dan ortiq unit va integratsiya testlari** mavjud bo'lib, har bir commit'da GitHub Actions CI orqali 100% yashil o'tishi tekshiriladi.

### ⚠️ Cheklovlar va Aniq Haqiqatlar (Honest Boundaries):
1. **Sehrli AGI emas:** Agent ishlashi uchun unga orqa fonda kuchli til modeli (LLM) kerak. Tizim mantiq, test, xotira va vositalarni boshqaradi, ammo til tushunish sifati ulangan modelga (Claude, GPT-4o, DeepSeek, Llama-3) bog'liq.
2. **Inson Ruxsatisiz Xavfli Amallar Qilinmaydi:** Agent mustaqil ravishda fayllarni o'chira olmaydi yoki majburiy push qila olmaydi — xavfsizlik filtri uni qat'iyan to'xtatadi.
3. **Kutubxona API Cheklovlari:** Agar foydalanayotgan tashqi API'laringizda (masalan, Groq yoki OpenRouter) token limiti tugasa, agent tejamkor keshdan foydalanadi yoki zaxira provayderga o'tishni taklif qiladi.

---

## Tezkor Ishga Tushirish

### 1. O'rnatish

```bash
# Repozitoriyni klonlash
git clone https://github.com/kapitan00000978-sketch/Universal-Agent-HP.git
cd Universal-Agent-HP

# Virtual muhitni yaratish va faollashtirish
python -m venv .venv
source .venv/bin/activate  # Windows uchun: .venv\Scripts\activate

# Bog'liqliklarni o'rnatish
pip install -r requirements.txt
pip install -e .
```

### 2. Konfiguratsiya

Namunaviy fayldan `.env` nusxasini oling va o'z modelingiz kalitini kiriting:

```bash
cp .env.example .env
```

Mahalliy Ollama bilan ishlatish uchun:
```env
TITAN_PROVIDER=ollama
TITAN_MODEL=llama3:latest
```

---

## 3 Xil Ishga Tushirish Usuli

### Variant 1: Zamonaviy Terminal TUI (OpenCode / Textual Uslubi)
Terminalda hech qanday qo'shimcha parametrsiz ishga tushiring:

```bash
python run.py
```
* <kbd>Shift</kbd> + <kbd>Tab</kbd>: 27 ta mutaxassis agent matritsasi
* <kbd>Ctrl</kbd> + <kbd>P</kbd>: Buyruqlar palitrasi (`/dag`, `/debate`, `/mcp`, `/pr`, `/rollback`, `/status`)
* <kbd>Ctrl</kbd> + <kbd>L</kbd>: Ekranni tozalash

### Variant 2: Web Dashboard (Brauzer Boshqaruv Paneli)
Brauzer orqali to'liq grafik vizualizatsiya va SSE voqealar oqimi bilan boshqarish:

```bash
python run.py --web
```
Brauzerda oching: `http://localhost:7860`

### Variant 3: Terminal CLI (Klassik Konsol)

```bash
universal --cli
```

---

## Arxitektura: Tri-Loop Metacognitive Execution

```mermaid
graph TD
    User([Foydalanuvchi Vazifasi]) --> Router[Multilingual Intent Router]
    Router --> Shield{Dual-Shield Guard & HITL}
    Shield -- Xavfli Amal --> HITL[«Ruxsat berasizmi? [Ha/Yo'q]»]
    Shield -- Ruxsat Berilgan --> TriLoop[Tri-Loop Fikrlash O'zagi]
    
    subgraph "Tri-Loop Metacognitive Architecture"
        TriLoop --> S1[System 1: Tezkor 0ms Intuitsiya]
        TriLoop --> S2[System 2: MCTS + ReAct + TDD Sikli]
        TriLoop --> S3[System 3: Metakognitiv Nazoratchi]
        
        S2 <--> Cache[(Semantik Kesh SQLite)]
        S2 <--> Memory[(Episodik Xotira & Working HUD)]
        S2 <--> ToolExec[MCP & Tizim Vositalari]
        
        S3 -. Entropiya & Stagnatsiya Nazorati .-> S2
        S3 -. Xato Sodir Bo'lsa: Tajribani Eslash .-> Memory
    end
    
    ToolExec --> PostCheck{AST & Pytest Verifikatsiyasi}
    PostCheck -- 100% Yashil --> GitEngine[Git Branch & PR Engine]
    GitEngine --> Output([Muvaffaqiyatli Natija])
```

---

## Testing & Security

* **Avtomatlashtirilgan testlar:** `pytest tests/ -q` buyrug'i orqali **675+ unit va integratsiya testlari** 100% yashil o'tadi.
* **Xavfsizlik:** AST darajasidagi statik inyeksiyalar nazorati, maxfiy kalitlarni himoyalash va destruktiv operatsiyalarni bloklash tizimning har bir qadamiga kiritilgan.

---

## Litsenziya

Ushbu loyiha [MIT License](LICENSE) litsenziyasi ostida taqdim etiladi.
