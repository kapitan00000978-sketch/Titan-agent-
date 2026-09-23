# ⚡ TITAN AGENT — Autonomous Cognitive AI Operating System (Genesis Edition)

> **Titan Agent** — An autonomous, enterprise-grade **Hierarchical Cognitive AI Platform** engineered with Genesis Darajasi (Levels 1–10) architecture. It transcends standard chat assistants by operating like a self-directed technology company: **CEO Meta-Orchestrator → 4 Department Leads → 27 Worker Specialists → Directed Acyclic Graph (DAG) Execution → Zero-Loss Sandbox Rollback → Longitudinal Drift Monitoring → Autonomous Self-Improvement**.

---

## 🌟 Key Advantages & Superpowers (Nega Titan Agent eng kuchlisi?)

1. 🏛️ **Hierarchical Corporate Organization (Ierarxik Tashkilot)**:
   - **Meta-Orchestrator (CEO)**: Global maqsad xotirasi, resurs byudjeti nazorati, jamoalararo ziddiyatlarni yechish.
   - **4 Department Team Leads**: EngineeringLead (CTO), ResearchLead (Chief Scientist), OperationsLead (DevOps/SRE), QualitySecurityLead (Audit/QA).
   - **27 Worker Specialists**: Backend, Frontend, DB, Security, Test, GitOps, Vector RAG va h.k.
2. 📊 **DAG Task Planner & Wave-based Parallel Executor**:
   - Vazifalarni bog'liqliklar grafigiga (Directed Acyclic Graph) ajratadi va mustaqil bosqichlarni parallel to'lqinlarda (`max_concurrency=4`) bajaradi. Xatolikda faqat zararlangan shoxlarni selektiv qayta rejalashtiradi.
3. 🧠 **Advanced Reasoning Engines (Chuqur Tafakkur)**:
   - **Reflexion Loop**: O'z ishini avtonom tanqidiy tahlil qilish (self-critique) va iterativ mukammallashtirish.
   - **Multi-Agent Debate**: Advocate vs Skeptic bahsi va Arbitrator (Judge) hakamligi.
   - **Tree of Thoughts (ToT)** va **Monte Carlo Tree Search (MCTS)**.
4. 🌐 **Causal Knowledge Graph Memory & AST Indexer**:
   - Butun kod bazasini Python AST orqali avtomatik tahlil qiladi.
   - Har qanday kodni o'zgartirishdan oldin **Blast Radius / Impact Analysis** hisoblab, boshqa funksiyalarga ta'sirini tekshiradi.
5. 🛡️ **Execution Sandbox & Zero-Loss Rollback**:
   - Xavfli buyruqlarni (fork bombalar, ildizni tozalash, disk formatlash) bajarishdan oldin bloklaydi.
   - SHA-256 xeshli **Filesystem Snapshot** orqali kodda xato yuz berganda barcha o'zgarishlarni darhol 0% yo'qotish bilan orqaga qaytaradi.
6. 🎯 **Capability-Based Model Router & Cognitive Budget**:
   - Topshiriq murakkabligiga qarab modelni tanlaydi (`FAST_CHEAP`, `STANDARD_CODING`, `DEEP_REASONING`).
   - Ketma-ket xatoliklarda avtomatik kuchliroq modelga eskalatsiya qiladi va USD xarajatini doimiy nazorat qiladi.
7. 📉 **Longitudinal Drift Detection**:
   - Vaqt o'tishi bilan sifat pasayishi (drift), qadamlar inflatsiyasi va muammoli toollarni erta aniqlaydi.
8. 👑 **Autonomous Self-Improvement Loop**:
   - Har bir xatolikdan saboq chiqarib, uni avtomatik ravishda yangi Playbook (`SkillRegistry`) va Bilimlar grafigiga (`KnowledgeGraph`) saqlaydi.

---

## 📋 System Requirements (Nimalar kerak?)

### Majburiy talablar:
- **Operatsion tizim**: Windows 10/11, macOS (Apple Silicon / Intel) yoki Linux (Ubuntu 20.04+).
- **Python**: Python **3.11** yoki **3.12+**.
- **Git**: Versiyalar nazorati uchun o'rnatilgan va PATH da mavjud bo'lishi kerak.
- **Xotira (RAM)**: Kamida 4 GB RAM (8 GB+ tavsiya etiladi).

### Ixtiyoriy (Qo'shimcha imkoniyatlar uchun):
- **API Kalitlari**: OpenAI, Anthropic Claude, Google Gemini, DeepSeek (istalgan birortasi yoki bir nechtasi).
- **Lokal modellar (mutlaqo bepul va internetsiz)**:
  - **Laya MLX** (Mac/PC uchun) yoki **Ollama** (`http://localhost:11434`).
- **Puter.js / OmniRoute**: Kalitsiz bepul 500+ modellardan to'g'ridan-to'g'ri foydalanish imkoniyati.
- **Docker**: Xavfsiz konteyner izolyatsiyasi uchun.

---

## 🚀 Installation Guide (O'rnatish Qo'llanmasi)

### 1-qadam: Repozitoriyni klonlash
```bash
git clone https://github.com/SIZNING_USERNAME/titan-agent.git
cd titan-agent
```

### 2-qadam: Virtual muhit (venv) yaratish va faollashtirish
**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3-qadam: Kutubxonalarni o'rnatish
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4-qadam: Muhit sozlamalarini tayyorlash (`.env`)
Loyihaning asosiy papkasidagi `.env.example` dan `.env` nusxasini oling:
```bash
# Windows:
copy .env.example .env

# Linux / macOS:
cp .env.example .env
```
`.env` faylini ochib, kerakli API kalitlaringizni kiriting:
```ini
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
DEEPSEEK_API_KEY=sk-...

# Yoki lokal Ollama/MLX:
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 🎮 Running Titan Agent (Ishga tushirish)

Titan Agent uch xil rejimda to'liq ishlaydi:

### 1. 🌐 Web Control Panel (Tavsiya etiladi)
FastAPI backend va zamonaviy Cyberpunk Dashboard interfeysi:
```bash
python run.py
```
Brauzeringiz avtomatik ochiladi: `http://localhost:8000`

### 2. 💻 Interaktiv Terminal CLI
Tezkor dasturchilar uchun jonli streaming konsol:
```bash
python run.py --cli
# Yoki to'g'ridan-to'g'ri:
python cli.py
```

Avtonom rejimlardan to'g'ridan-to'g'ri foydalanish:
```bash
# CEO Meta-Orchestrator bilan ishlash:
python cli.py --meta "Build an authenticated REST API with FastAPI and SQLite"

# DAG parallel rejalashtiruvchi bilan ishlash:
python cli.py --dag "Refactor backend database schema and add pytest coverage"

# Bahs (Debate) strategiyasi bilan ishlash:
python cli.py --strategy debate "Should we migrate from REST to GraphQL?"
```

### 3. 🤖 Telegram Bot (Masofaviy yordamchi)
Telegram orqali agentni boshqarish:
```bash
python run.py --telegram
```

---

## 🧪 Testing & Verification (Testlar)

Butun loyiha bo'yicha barcha 600 ta unit va integratsiya testlarini ishga tushirish:
```bash
python -m pytest tests -v
```
Natija: `600 passed, 1 skipped, 0 failures` (100% yashil).

---

## 📜 To'liq Qo'llanma
Barcha buyruqlar, arxitektura va 7 ta qat'iy qoida uchun [TITAN_AGENT_MANUAL.txt](TITAN_AGENT_MANUAL.txt) fayliga qarang.

---

## 📄 Litsenziya
MIT License — istalgan maqsadda erkin foydalanish mumkin.