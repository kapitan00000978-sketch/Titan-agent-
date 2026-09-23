# TITAN AGENT — CHUQUR KOGNITIV ARXITEKTURA (GENESIS DARAJASI)
*(Phase 22+ evolyutsiyasi)*

Falsafa: Titan endi "bitta agent + 27 yordamchi" emas, balki **ierarxik tashkilot** — inson kompaniyasidagi CEO → bo'lim boshliqlari → xodimlar tuzilmasiga o'xshash. Har bir daraja o'zidan pastdagini nazorat qiladi, o'zidan yuqoridagiga hisobot beradi.

=============================================================================
## DARAJA 1 — META-ORCHESTRATOR (Chief Agent)
=============================================================================
Bitta doimiy ishlaydigan "bosh miya". Foydalanuvchidan kelgan har qanday vazifani qabul qiladi va uni QAYSI BO'LIM (team) bajarishini hal qiladi.
- **Global maqsad xotirasi** (loyihaning umumiy yo'nalishi, uzoq muddatli rejalar — bir sessiyadan boshqasiga o'tadi)
- **Resurs byudjeti nazorati** (token, vaqt, pul — qaysi bo'limga qancha ajratilsin)
- **Yakuniy qaror qabul qiluvchi** — ziddiyatli takliflar kelganda (masalan Engineering "tezroq" desa, QA "xavfsizroq" desa)

=============================================================================
## DARAJA 2 — BO'LIM BOSHLIQLARI (Team-Lead Agents)
=============================================================================
Meta-Orchestrator ostida 4 ta doimiy "bo'lim boshlig'i":
- **Engineering Lead** — coder, reviewer, test_writer, deployer, dependency_updater'ni boshqaradi
- **Research Lead** — researcher, data_validator, hallucination_checker, translator'ni boshqaradi
- **Operations Lead** — scheduler_agent, notification_agent, cost_watcher, rate_limiter_agent'ni boshqaradi
- **Quality/Security Lead** — security, tester, critic_agent, fallback_agent'ni boshqaradi

Har bir Lead o'z bo'limi ichida ishni taqsimlaydi va NATIJANI Meta-Orchestratorga qaytarishdan OLDIN o'zi tekshiradi (birinchi filtr).

=============================================================================
## DARAJA 3 — XODIM SUB-AGENTLAR (Worker Layer)
=============================================================================
Mavjud 27 ta rol (17 asosiy + 10 yangi) — o'zgarishsiz, lekin endi to'g'ridan-to'g'ri foydalanuvchiga emas, o'z Team-Lead'iga javob beradi.
Bu — chaqiruv zanjirini qisqartiradi va xato tarqalishini cheklaydi (bitta xodim xato qilsa, butun tizim emas, faqat o'sha bo'lim ta'sirlanadi).

=============================================================================
## DARAJA 4 — REASONING ENGINE (ko'p strategiyali fikrlash yadrosi)
=============================================================================
Har bir daraja o'z vazifasiga mos strategiyani tanlaydi:
- **ReAct** — oddiy, tezkor vazifalar
- **Tree-of-Thought** — bir nechta yechim yo'lini parallel sinash
- **Reflexion loop** — natijani chiqargandan keyin o'z-o'zini tanqid qilib, xato topsa qayta urinish (max 3 tsikl)
- **[YANGI] Debate** — ikki nusxadagi agent bir-biriga qarshi argument keltiradi (murakkab arxitektura qarorlari uchun — "A yondashuv yaxshimi, B yondashuvmi?")
- **[YANGI] MCTS-uslubida qidiruv** — kod optimallashtirish/refactor vazifalarida bir nechta yechimni "ball"lab, eng yaxshisini tanlash

=============================================================================
## DARAJA 5 — UZOQ MUDDATLI REJALASHTIRISH (Task Graph)
=============================================================================
Katta vazifa — DAG (Directed Acyclic Graph) shaklida bo'linadi, oddiy chiziqli ro'yxat emas:
- **Har bir tugun (node)** — bitta kichik vazifa + unga bog'liq bo'lgan boshqa tugunlar (dependencies)
- **Parallel bajarish** — bog'liq bo'lmagan tugunlar bir vaqtda ishlaydi
- **Qayta rejalashtirish** — bitta tugun muvaffaqiyatsiz bo'lsa, faqat shu tugun va undan keyingilar qayta ishlanadi, boshidan emas
- **Progress dashboard** — Web UI'da DAG vizual holatda ko'rsatiladi (qaysi tugun bajarilgan/jarayonda/kutilmoqda)

=============================================================================
## DARAJA 6 — BILIM VA XOTIRA (4 qatlamli)
=============================================================================
- **Ishchi xotira** — joriy suhbat (context trimming bilan)
- **Episodik xotira** — "nima bo'lgan edi" (mavjud core/memory)
- **Semantik/Vector** — RAG uchun ma'no bo'yicha qidiruv (Chroma/SQLite-vec)
- **[YANGI] Bilim grafigi (Knowledge Graph)** — "nima nimaga bog'liq" (masalan: "auth.py → server.py'ga bog'liq → Phase 12'da o'zgargan → shu sabab Phase 14 kechikkan"). Sabab-oqibat zanjirini saqlaydi, oddiy vector qidiruv buni bera olmaydi.

=============================================================================
## DARAJA 7 — TOOL VA QOBILIYAT GRAFIGI
=============================================================================
- **Ichki tool'lar** (fayl, shell, web) — mavjud
- **MCP mesh** — n8n, Stitch, Supabase (81 tool, allaqachon ulangan)
- **[YANGI] Dinamik tool kashfiyoti** — agent vazifaga qarab qaysi tool kerakligini avtomatik aniqlaydi (hozirgi kabi qo'lda ro'yxatdan tanlash emas)
- **[YANGI] Tool ishonchlilik reytingi** — har bir tool qancha marta muvaffaqiyatli/muvaffaqiyatsiz ishlagani kuzatiladi, ishonchsiz tool avtomatik pastroq prioritetga tushadi

=============================================================================
## DARAJA 8 — LLM PROVIDER MESH
=============================================================================
- **Provayderlar:** omni, openrouter, kimi, glm, groq, deepseek, pollinations (keysiz zaxira), puter (Web UI)
- **Fallback zanjiri** — avtomatik o'tish (mavjud reja)
- **[YANGI] Qobiliyat bo'yicha routing** — har bir model "kod uchun kuchli", "tez", "arzon", "ijodiy" kabi teglangan, vazifa turiga qarab eng mos model avtomatik tanlanadi (statik emas, dinamik)

=============================================================================
## DARAJA 9 — BAJARISH VA SANDBOX
=============================================================================
- **[YANGI] Izolyatsiyalangan bajarish muhiti** — har bir xavfli buyruq (masalan kod test qilish) alohida konteyner/sandbox'da ishlaydi, asosiy tizimga ta'sir qilmaydi
- **[YANGI] Resource limit** — CPU/RAM/vaqt chegarasi har bir bajarishga

=============================================================================
## DARAJA 10 — XAVFSIZLIK VA BOSHQARUV (Governance)
=============================================================================
- **Auth** (Bearer token)
- **HITL** — guarded actions uchun tasdiq
- **Policy Engine** — SSRF, dangerous-command
- **Audit Log** — har bir qaror kim/qachon/nima uchun

=============================================================================
## DARAJA 11 — KUZATUV VA O'Z-O'ZINI NAZORAT
=============================================================================
- **Structured logs, tracing, cost dashboard**
- **[YANGI] Drift Detection** — agent vaqt o'tishi bilan sifati pasayayotganini (masalan ko'proq xato qilayotganini) avtomatik payqaydi va ogohlantiradi

=============================================================================
## DARAJA 12 — UZLUKSIZ TAKOMILLASHTIRISH (Self-Improvement Loop)
=============================================================================
- **[YANGI] Feedback yig'ish** — har bir vazifadan keyin natija "muvaffaqiyatli/muvaffaqiyatsiz" deb belgilanadi
- **[YANGI] Eval suite** — standart test-vazifalar to'plami, har yangi Phase'dan keyin tizim shu testlardan o'tkaziladi (regressiyani ushlash uchun)
- **[YANGI] Strategiya sozlash** — qaysi reasoning strategiya (ReAct/ToT/Debate) qaysi vazifa turida yaxshiroq ishlagani statistika asosida vaqt o'tishi bilan avtomatik moslashadi

=============================================================================
## DARAJA 13 — INFRATUZILMA
=============================================================================
Docker, CI/CD, multi-OS, load test (mavjud reja — o'zgarishsiz)

=============================================================================
## DARAJA 14 — INTERFEYS
=============================================================================
Web UI, Telegram, CLI, API (mavjud — o'zgarishsiz)

=============================================================================
## NEGA BU DARAJA "JIDDIY" HISOBLANADI
=============================================================================
- Bitta xato butun tizimni yiqitmaydi (ierarxiya izolyatsiya qiladi)
- Vazifalar parallel, DAG asosida — vaqt tejaydi
- Tizim o'zini o'zi tekshiradi (Reflexion, Critic, Drift Detection)
- Xotira nafaqat "nima bo'ldi", balki "nima nimaga sabab bo'ldi"ni ham biladi (Knowledge Graph)
- Vaqt o'tishi bilan YAXSHILANADI (Self-Improvement Loop), statik qolmaydi

=============================================================================
## AMALGA OSHIRISH TARTIBI (Roadmap, Phase 22 dan boshlab)
=============================================================================
- **Phase 22** — Meta-Orchestrator + 4 Team-Lead agent         [Daraja 1-2]
- **Phase 23** — Task Graph (DAG) rejalashtiruvchi              [Daraja 5]
- **Phase 24** — Reflexion loop + Debate strategiyasi           [Daraja 4]
- **Phase 25** — Knowledge Graph xotira                          [Daraja 6]
- **Phase 26** — Dinamik tool kashfiyoti + ishonchlilik reytingi [Daraja 7]
- **Phase 27** — Qobiliyat-asosli model routing                  [Daraja 8]
- **Phase 28** — Sandbox/izolyatsiyalangan bajarish               [Daraja 9]
- **Phase 29** — Drift Detection                                  [Daraja 11]
- **Phase 30** — Self-Improvement Loop + Eval suite                [Daraja 12]

Har fazadan keyin: pytest + ruff yashil, CHANGES.md yozuvi, eval suite (Phase 30dan keyin — har fazada) o'tkaziladi.
