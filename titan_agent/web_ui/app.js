// Titan Agent Web UI Client Logic

const messagesStream = document.getElementById("messages-stream");
const chatForm = document.getElementById("chat-form");
const userPromptInput = document.getElementById("user-prompt");
const submitBtn = document.getElementById("submit-btn");
const welcomeCard = document.getElementById("welcome-card");
const statusBadge = document.getElementById("agent-status-badge");
const currentProviderSpan = document.getElementById("current-provider");
const currentModelSpan = document.getElementById("current-model");

// Settings modal elements
const settingsModal = document.getElementById("settings-modal");
const openSettingsBtn = document.getElementById("open-settings-btn");
const closeSettingsBtn = document.getElementById("close-settings-btn");
const saveSettingsBtn = document.getElementById("save-settings-btn");
const providerSelect = document.getElementById("provider-select");
const modelInput = document.getElementById("model-input");
const apiKeyInput = document.getElementById("api-key-input");
const baseUrlInput = document.getElementById("base-url-input");

let isStreaming = false;
let currentMode = "fast"; // "fast" | "deep" | "deep_search"

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  fetchConfig();
  fetchMcpTools();
  fetchWorkspaceFiles();
  setupEventListeners();
});

// ---------- Model name helpers ----------
// The underlying variant ID (e.g. "...:free") is what the API needs for free usage,
// but the UI should never reveal it. We strip it for display and re-append on send.
function displayModel(id) {
  return id ? id.replace(/:free$/, "") : id;
}
function resolvePuterModel(raw) {
  const v = (raw || "").trim();
  if (!v) return "deepseek/deepseek-v4-pro:free";
  if (/:(free|flex|priority)$/.test(v)) return v;
  return v + ":free";
}

function setupEventListeners() {
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const prompt = userPromptInput.value.trim();
    if (!prompt || isStreaming) return;
    sendMessage(prompt);
  });

  userPromptInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });

  // Mode selector (Fast / Deep Thinking / Deep Search)
  document.querySelectorAll(".mode-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      currentMode = btn.dataset.mode;
      document.querySelectorAll(".mode-btn").forEach(b => b.classList.remove("mode-active"));
      btn.classList.add("mode-active");
    });
  });

  // Settings
  openSettingsBtn.addEventListener("click", () => {
    settingsModal.classList.add("open");
    scanLocalModels();
    // When Puter provider is selected, auto-load models
    if (providerSelect.value === "puter") {
      loadPuterModels(false);
    }
  });
  closeSettingsBtn.addEventListener("click", () => settingsModal.classList.remove("open"));
  saveSettingsBtn.addEventListener("click", saveConfig);
  document.getElementById("scan-local-btn").addEventListener("click", scanLocalModels);

  // Puter Quick Model Chips
  document.querySelectorAll(".model-chip").forEach(btn => {
    btn.addEventListener("click", () => {
      providerSelect.value = "puter";
      modelInput.value = displayModel(btn.dataset.model);
      apiKeyInput.value = "";
    });
  });

  // When provider changes: open the model browser automatically for Puter
  providerSelect.addEventListener("change", () => {
    if (providerSelect.value === "puter") {
      loadPuterModels(false);
    }
  });

  // Puter Model Browser — load all models via listModels()
  const loadPuterBtn = document.getElementById("load-puter-models-btn");
  const modelSearch = document.getElementById("puter-model-search");
  if (modelSearch) {
    modelSearch.addEventListener("input", () => renderPuterModels());
  }
  document.querySelectorAll(".puter-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".puter-tab").forEach(t => t.classList.remove("puter-tab-active"));
      tab.classList.add("puter-tab-active");
      renderPuterModels();
    });
  });
  if (loadPuterBtn) {
    loadPuterBtn.addEventListener("click", () => loadPuterModels(true));
  }
}

// ---- Puter model browser ----
let allPuterModels = [];
let puterActiveTab = "free"; // "free" | "all"

function normalizePuterModel(m) {
  // listModels() returns an array of objects; some SDK versions may return strings
  if (typeof m === "string") return { id: m, provider: "", name: m };
  return {
    id: (m && m.id) || "",
    provider: (m && m.provider) || "",
    name: (m && m.name) || "",
    context: (m && m.context) || 0,
    max_tokens: (m && m.max_tokens) || 0
  };
}

async function loadPuterModels(force) {
  const loadPuterBtn = document.getElementById("load-puter-models-btn");
  const browserEl = document.getElementById("puter-model-browser");
  const listEl = document.getElementById("puter-model-list");
  if (!loadPuterBtn || !browserEl || !listEl) return;

  if (loadPuterBtn.disabled) return; // load already in progress
  loadPuterBtn.disabled = true;
  loadPuterBtn.textContent = "Loading...";
  listEl.innerHTML = '<div style="padding:12px; font-size:12px; color:var(--text-muted);">Fetching models...</div>';
  browserEl.style.display = "block";

  try {
    if (typeof puter === "undefined" || !puter.ai || !puter.ai.listModels) {
      throw new Error("Puter.js is not loaded. Check your internet connection or reopen the page.");
    }
    const models = await puter.ai.listModels();
    allPuterModels = (Array.isArray(models) ? models : []).map(normalizePuterModel).filter(m => m.id);
    if (allPuterModels.length === 0) {
      listEl.innerHTML = '<div style="padding:12px; font-size:12px; color:var(--text-muted);">No models found.</div>';
      return;
    }
    renderPuterModels();
  } catch (err) {
    listEl.innerHTML = `<div style="padding:12px; font-size:12px; color:var(--accent-rose);">Error: ${escapeHtml(err.message)}</div>`;
  } finally {
    loadPuterBtn.disabled = false;
    loadPuterBtn.textContent = "🌐 All Models";
  }
}

function renderPuterModels() {
  const listEl = document.getElementById("puter-model-list");
  const searchEl = document.getElementById("puter-model-search");
  if (!listEl) return;

  const q = (searchEl ? searchEl.value : "").toLowerCase().trim();
  const activeTab = [...document.querySelectorAll(".puter-tab")].find(t => t.classList.contains("puter-tab-active"));
  puterActiveTab = activeTab ? activeTab.dataset.tab : "free";

  let filtered = allPuterModels;
  if (puterActiveTab === "free") {
    filtered = filtered.filter(m => m.id.endsWith(":free"));
  }
  if (q) {
    filtered = filtered.filter(m =>
      m.id.toLowerCase().includes(q) ||
      (m.provider || "").toLowerCase().includes(q) ||
      (m.name || "").toLowerCase().includes(q)
    );
  }

  if (filtered.length === 0) {
    listEl.innerHTML = '<div style="padding:12px; font-size:12px; color:var(--text-muted);">No models match your search. Try another query or switch tabs.</div>';
    return;
  }

  // Group by provider
  const groups = {};
  for (const m of filtered) {
    const prov = m.provider || "others";
    (groups[prov] = groups[prov] || []).push(m);
  }

  let html = `<div style="padding:6px 10px; font-size:11px; color:var(--text-muted); border-bottom:1px solid var(--border-color);">Total: ${filtered.length} models</div>`;

  for (const [prov, models] of Object.entries(groups)) {
    html += `<div style="padding:8px 10px 2px; font-size:11px; font-weight:700; letter-spacing:0.6px; text-transform:uppercase; color:var(--accent-cyan);">${escapeHtml(prov)} (${models.length})</div>`;
    for (const m of models) {
      const displayId = displayModel(m.id);
      const ctx = m.context ? ` • ${Math.round(m.context / 1000)}k context` : "";
      html += `
        <button type="button" class="puter-model-chip" data-model="${escapeHtml(m.id)}" title="${escapeHtml(displayId)}${ctx}" style="display:flex; align-items:center; gap:8px; width:100%; text-align:left; padding:7px 10px; background:rgba(255,255,255,0.03); border:1px solid transparent; border-radius:6px; cursor:pointer; font-size:12px; color:var(--text-primary);">
          <span style="color:var(--text-muted);">🤖</span>
          <span style="font-family:var(--font-mono); flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(displayId)}</span>
          <span style="font-size:10px; color:var(--text-muted); white-space:nowrap;">${ctx}</span>
        </button>`;
    }
  }
  listEl.innerHTML = html;

  // Selecting a chip applies the full variant internally but shows the clean name
  listEl.querySelectorAll(".puter-model-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      providerSelect.value = "puter";
      modelInput.value = displayModel(chip.dataset.model);
      apiKeyInput.value = "";
      modelInput.style.borderColor = "var(--accent-emerald)";
    });
  });
}

async function scanLocalModels() {
  const chipsContainer = document.getElementById("local-models-chips");
  chipsContainer.innerHTML = '<span style="font-size:11px; color:var(--accent-cyan);">Scanning...</span>';
  try {
    const res = await fetch("/api/local-models");
    const data = await res.json();
    chipsContainer.innerHTML = "";

    const ollamaModels = data.ollama || [];
    const lmModels = data.lmstudio || [];

    if (ollamaModels.length === 0 && lmModels.length === 0) {
      chipsContainer.innerHTML = '<span style="font-size:11px; color:var(--text-muted);">(No local models found yet)</span>';
      return;
    }

    ollamaModels.forEach(m => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "tiny-btn";
      chip.style.borderColor = "var(--accent-cyan)";
      chip.style.color = "var(--accent-cyan)";
      chip.textContent = `🦙 Ollama: ${m}`;
      chip.onclick = () => {
        providerSelect.value = "ollama";
        modelInput.value = m;
        apiKeyInput.value = "";
      };
      chipsContainer.appendChild(chip);
    });

    lmModels.forEach(m => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "tiny-btn";
      chip.style.borderColor = "var(--accent-violet)";
      chip.style.color = "var(--accent-violet)";
      chip.textContent = `⚡ LM: ${m}`;
      chip.onclick = () => {
        providerSelect.value = "lmstudio";
        modelInput.value = m;
      };
      chipsContainer.appendChild(chip);
    });
  } catch (err) {
    chipsContainer.innerHTML = '<span style="font-size:11px; color:var(--text-muted);">(Could not check)</span>';
  }
}

function sendQuickPrompt(text) {
  userPromptInput.value = text;
  sendMessage(text);
}

async function fetchConfig() {
  try {
    const res = await fetch("/api/config");
    const data = await res.json();
    currentProviderSpan.textContent = data.provider.toUpperCase();
    currentModelSpan.textContent = displayModel(data.model);
    providerSelect.value = data.provider;
    modelInput.value = displayModel(data.model);
    if (data.base_url) baseUrlInput.value = data.base_url;
  } catch (err) {
    console.error("Config fetch error:", err);
  }
}

async function saveConfig() {
  const payload = {
    provider: providerSelect.value,
    model: providerSelect.value === "puter" ? resolvePuterModel(modelInput.value) : modelInput.value.trim(),
    api_key: apiKeyInput.value.trim(),
    base_url: baseUrlInput.value.trim()
  };
  try {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      settingsModal.classList.remove("open");
      fetchConfig();
    }
  } catch (err) {
    alert("Error saving settings: " + err);
  }
}

async function fetchMcpTools() {
  try {
    const res = await fetch("/api/mcp/tools");
    const data = await res.json();
    const servers = data.servers || {};
    const serverKeys = Object.keys(servers);
    const mcpCountElem = document.getElementById("mcp-count");
    if (mcpCountElem) {
      const toolCount = serverKeys.reduce((sum, k) => sum + (servers[k].tools_count || 0), 0);
      const plural = serverKeys.length === 1 ? "" : "s";
      mcpCountElem.textContent = `${serverKeys.length} MCP server${plural} connected (${toolCount} tools)`;
    }
  } catch (e) {
    console.warn("MCP tools fetch failed", e);
  }
}

async function fetchWorkspaceFiles() {
  try {
    const res = await fetch("/api/workspace/files");
    const data = await res.json();
    const tree = document.getElementById("files-tree");
    if (!data.files || data.files.length === 0) {
      tree.innerHTML = '<div class="empty-hint">(Empty)</div>';
      return;
    }
    tree.innerHTML = data.files.map(f => `
      <div class="file-row">
        <span>📄</span>
        <span class="file-name" title="${f.rel_path}">${f.name}</span>
        <span style="margin-left:auto; color:var(--text-muted); font-size:10px;">${f.size} B</span>
      </div>
    `).join("");
  } catch (e) {
    console.warn("Files fetch error", e);
  }
}

function appendUserMessage(text) {
  if (welcomeCard) welcomeCard.style.display = "none";
  const row = document.createElement("div");
  row.className = "message-row user";
  row.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
  messagesStream.appendChild(row);
  scrollToBottom();
}

function createAgentCard() {
  const row = document.createElement("div");
  row.className = "message-row agent";

  const card = document.createElement("div");
  card.className = "agent-response-card";

  const statusLine = document.createElement("div");
  statusLine.className = "status-line";
  statusLine.style.fontSize = "12px";
  statusLine.style.color = "var(--accent-cyan)";
  statusLine.innerHTML = "⚡ Titan is working...";
  card.appendChild(statusLine);

  row.appendChild(card);
  messagesStream.appendChild(row);
  scrollToBottom();

  return { row, card, statusLine };
}

async function sendMessage(prompt) {
  if (isStreaming) return;
  isStreaming = true;
  userPromptInput.value = "";
  submitBtn.disabled = true;
  statusBadge.textContent = "Working...";

  appendUserMessage(prompt);
  const { card, statusLine } = createAgentCard();

  let currentThoughtAccordion = null;
  let finalAnswerDiv = null;

  // If provider is Puter.js, run direct client-side Puter AI
  if (providerSelect.value === "puter") {
    await sendPuterMessage(prompt, card, statusLine);
    isStreaming = false;
    submitBtn.disabled = false;
    statusBadge.textContent = "System Ready";
    statusLine.style.display = "none";
    fetchWorkspaceFiles();
    scrollToBottom();
    return;
  }

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: prompt, session_id: "web_session", mode: currentMode })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop(); // keep partial

      for (const block of lines) {
        if (!block.startsWith("data: ")) continue;
        const jsonStr = block.replace("data: ", "").trim();
        if (!jsonStr) continue;

        try {
          const event = JSON.parse(jsonStr);
          handleAgentEvent(event, card, statusLine, {
            getThought: () => currentThoughtAccordion,
            setThought: (el) => { currentThoughtAccordion = el; },
            getAnswer: () => finalAnswerDiv,
            setAnswer: (el) => { finalAnswerDiv = el; }
          });
        } catch (err) {
          console.error("Event parse error:", err, jsonStr);
        }
      }
      scrollToBottom();
    }
  } catch (err) {
    statusLine.innerHTML = `<span style="color:var(--accent-rose)">An error occurred: ${err.message}</span>`;
  } finally {
    isStreaming = false;
    submitBtn.disabled = false;
    statusBadge.textContent = "System Ready";
    statusLine.style.display = "none";
    fetchWorkspaceFiles();
    scrollToBottom();
  }
}

async function sendPuterMessage(prompt, card, statusLine) {
  let modelName = displayModel(resolvePuterModel(modelInput.value.trim() || "deepseek/deepseek-v4-pro"));
  statusLine.innerHTML = `⚡ Connecting directly to ${escapeHtml(modelName)}...`;
  try {
    if (typeof puter === "undefined" || !puter.ai) {
      throw new Error("Puter.js is not loaded. Check your internet connection.");
    }

    let answerDiv = document.createElement("div");
    answerDiv.className = "answer-content";
    card.insertBefore(answerDiv, statusLine);

    let modeNote = "";
    if (currentMode === "deep") {
      modeNote = "\n\n### DEEP THINKING MODE (engaged):\n" +
        "- Decompose the problem into explicit sub-problems and reason about each one in detail.\n" +
        "- Consider alternative approaches, edge cases, and failure modes before committing.\n" +
        "- After every step, ask yourself: is there anything unverified, ambiguous, or missing?\n" +
        "- Do not settle for a shallow answer: dig until the result is provably correct and complete.";
    } else if (currentMode === "deep_search") {
      modeNote = "\n\n### DEEP SEARCH MODE (engaged):\n" +
        "- Start with the deep_search tool to build a comprehensive multi-source dossier on the topic.\n" +
        "- Cross-check claims across multiple sources; prefer verifiable, recently updated information.\n" +
        "- Scrape primary pages when a snippet is insufficient (scrape_webpage tool).\n" +
        "- Structure the final answer with sections and cite the sources you actually retrieved.\n" +
        "- If evidence is thin or conflicting, say so explicitly instead of guessing.";
    }

    const messages = [
      {
        role: "system",
        content: "You are TITAN AGENT — an ultra-powerful autonomous AI reasoning and execution engine running in a web dashboard.\n\n" +
          "### PLAN-ACT-VERIFY-REPORT + REFLECT:\n" +
          "1. PLAN: briefly outline your strategy inside <thought>...</thought> before using tools.\n" +
          "2. ACT: use tools via <tool_call>{\"name\": \"tool_name\", \"arguments\": {...}}</tool_call>. Batch independent calls and run them together.\n" +
          "3. VERIFY: if a tool errors, read the message, fix arguments, retry with an alternative approach — never give up after one failure.\n" +
          "4. REFLECT: after tools run, critically review your own work — did you satisfy the whole request? fix gaps before answering.\n" +
          "5. REPORT: finish with a well-structured markdown final answer in the user's language.\n\n" +
          "### TOOL CATALOG (execute via /api/tools/execute):\n" +
          "- execute_command(command, cwd?) — run PowerShell commands on the host OS\n" +
          "- read_file(path), write_file(path, content), edit_file(path, target_text, replacement_text), list_directory(path?) — filesystem\n" +
          "- web_search(query, max_results?) — live DuckDuckGo search\n" +
          "- scrape_webpage(url) — fetch readable text from a URL\n" +
          "- python_eval(code) — run Python in a subprocess\n" +
          "- deep_search(topic) — multi-hop web research dossier\n" +
          "- deep_coder(task_name, files, test_code?) — full software engineering cycle with test verification\n" +
          "- launch_application(app_or_command) — open a Windows app\n" +
          "- system_info() — live OS / CPU / RAM / disk / Python facts\n" +
          "- manage_processes(action: list|kill, pattern?) — list or kill OS processes\n" +
          "- memory_save(key, value, category?) / memory_search(query) — persistent long-term memory\n" +
          "- mcp_* — tools from connected MCP servers\n\n" +
          "### EFFICIENCY: never re-run a tool for already-known output; if the goal is reached, stop and answer immediately; don't add decorative steps.\n" +
          "### PARALLEL: when several independent tool calls are needed, batch them in one turn so they execute simultaneously." +
          modeNote + "\n\n" +
          "### LANGUAGE: respond in the user's language. Be professional, direct, and precise."
      },
      { role: "user", content: prompt }
    ];

    statusLine.innerHTML = `⚡ ${escapeHtml(modelName)} is generating a response...`;
    const fullModelId = resolvePuterModel(modelInput.value.trim() || "deepseek/deepseek-v4-pro");
    const response = await puter.ai.chat(messages, { model: fullModelId, stream: true });

    let fullText = "";
    for await (const part of response) {
      if (part && part.text) {
        fullText += part.text;
        answerDiv.innerHTML = marked.parse(fullText);
        scrollToBottom();
      }
    }

    // Check for tool calls
    const toolMatches = [...fullText.matchAll(/<tool_call>\s*(.*?)\s*<\/tool_call>/gis)];
    if (toolMatches.length > 0) {
      statusLine.innerHTML = `🔧 Executing ${toolMatches.length} tool${toolMatches.length === 1 ? "" : "s"} in parallel...`;
      statusLine.style.display = "block";

      // Build all tool cards first, then run every tool in parallel
      const jobs = toolMatches.map((match) => {
        try {
          const parsed = JSON.parse(match[1]);
          const tName = parsed.name;
          const tArgs = parsed.arguments || parsed.parameters || {};

          const toolCard = document.createElement("div");
          toolCard.className = "tool-step-card";
          toolCard.innerHTML = `
            <div class="tool-header-line">
              <span class="tool-badge-name">🔧 ${escapeHtml(tName)}</span>
              <span style="color:var(--accent-amber)">Running...</span>
            </div>
            <div class="tool-args-preview">${escapeHtml(JSON.stringify(tArgs))}</div>
          `;
          card.insertBefore(toolCard, statusLine);

          return { tName, tArgs, toolCard };
        } catch (err) {
          console.warn("Tool parse error:", err);
          return null;
        }
      }).filter(Boolean);

      // Execute all tools simultaneously
      await Promise.all(jobs.map(async (job) => {
        try {
          const execRes = await fetch("/api/tools/execute", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tool_name: job.tName, arguments: job.tArgs })
          });
          const execData = await execRes.json();
          const resBox = document.createElement("div");
          resBox.className = "tool-result-box";
          resBox.textContent = execData.result || "Done";
          job.toolCard.querySelector(".tool-header-line").lastChild.textContent = "✓ Done";
          Object.assign(job.toolCard.querySelector(".tool-header-line").lastChild.style, { color: "var(--accent-emerald)" });
          job.toolCard.appendChild(resBox);
        } catch (err) {
          const resBox = document.createElement("div");
          resBox.className = "tool-result-box";
          resBox.textContent = "Error: " + err.message;
          job.toolCard.appendChild(resBox);
        }
      }));
    }
  } catch (err) {
    statusLine.innerHTML = `<span style="color:var(--accent-rose)">Puter.js error: ${err.message}</span>`;
  }
}

function handleAgentEvent(event, card, statusLine, state) {
  if (event.type === "status") {
    statusLine.innerHTML = `⚡ ${escapeHtml(event.data)}`;
  }
  else if (event.type === "thought") {
    let acc = state.getThought();
    if (!acc) {
      acc = document.createElement("div");
      acc.className = "thought-accordion";
      acc.innerHTML = `
        <div class="thought-header">
          <span>🧠 Reasoning (CoT)</span>
          <span class="acc-toggle">▼</span>
        </div>
        <div class="thought-body"></div>
      `;
      const header = acc.querySelector(".thought-header");
      const body = acc.querySelector(".thought-body");
      header.addEventListener("click", () => {
        body.style.display = body.style.display === "none" ? "block" : "none";
      });
      card.insertBefore(acc, statusLine);
      state.setThought(acc);
    }
    const body = acc.querySelector(".thought-body");
    body.textContent += event.data + "\n";
  }
  else if (event.type === "tool_call") {
    const toolCard = document.createElement("div");
    toolCard.className = "tool-step-card";
    const tName = event.data.name;
    const tArgs = JSON.stringify(event.data.arguments || {});
    toolCard.id = `tool-${tName}-${Date.now()}`;
    toolCard.innerHTML = `
      <div class="tool-header-line">
        <span class="tool-badge-name">🔧 ${escapeHtml(tName)}</span>
        <span class="tool-status-tag" style="color:var(--accent-amber)">Running...</span>
      </div>
      <div class="tool-args-preview">${escapeHtml(tArgs)}</div>
    `;
    card.insertBefore(toolCard, statusLine);
  }
  else if (event.type === "tool_result") {
    const resCard = document.createElement("div");
    resCard.className = "tool-step-card";
    const resText = typeof event.data.result === "string" ? event.data.result : JSON.stringify(event.data.result);
    resCard.innerHTML = `
      <div class="tool-header-line">
        <span class="tool-badge-name" style="color:var(--accent-emerald)">✓ ${escapeHtml(event.data.name)} result</span>
      </div>
      <div class="tool-result-box">${escapeHtml(resText.slice(0, 1000))}${resText.length > 1000 ? "\n...(truncated)" : ""}</div>
    `;
    card.insertBefore(resCard, statusLine);
  }
  else if (event.type === "final_answer") {
    let ans = state.getAnswer();
    if (!ans) {
      ans = document.createElement("div");
      ans.className = "answer-content";
      card.insertBefore(ans, statusLine);
      state.setAnswer(ans);
    }
    ans.innerHTML = marked.parse(event.data);
  }
  else if (event.type === "error") {
    const errDiv = document.createElement("div");
    errDiv.style.color = "var(--accent-rose)";
    errDiv.style.padding = "10px";
    errDiv.style.background = "rgba(244, 63, 94, 0.1)";
    errDiv.style.borderRadius = "8px";
    errDiv.innerHTML = `<strong>Error:</strong> ${escapeHtml(event.data)}`;
    card.insertBefore(errDiv, statusLine);
  }
}

function scrollToBottom() {
  messagesStream.scrollTop = messagesStream.scrollHeight;
}

function escapeHtml(text) {
  if (!text) return "";
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}