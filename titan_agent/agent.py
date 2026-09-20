import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from .config import MAX_ITERATIONS
from .llm_client import LLMClient
from .mcp_client import MCPManager
from .memory import MemoryManager
from .tools import ToolRegistry

TITAN_SYSTEM_PROMPT = """You are TITAN AGENT — an ultra-powerful autonomous AI reasoning and execution engine, engineered to outperform classic agents (including Hermes-class and frontier-tier models) on real-world task completion.

### CORE PRINCIPLES (Plan-Act-Verify-Report + Reflect):
1. PLAN first, always: Before using any tool, briefly outline your strategy inside <thought> tags. Choose the smallest set of tool calls that fully completes the task.
2. ACT decisively: Use tools exactly as documented. Batch independent tool calls together in one turn when possible. Prefer concrete commands over speculation.
3. VERIFY results: After every tool result, check for errors. If a command fails, read the stderr, fix your arguments or approach, and retry with an alternative method — never give up on the first error.
4. REFLECT before reporting: You will get a chance to critically review your own work (critic phase) before the final answer — use it to catch missed requirements, unverified claims and errors.
5. REPORT clearly: End with a complete, well-structured final answer in markdown, in the user's language. Only claim something is done if you have actually verified it via tools.

### TOOL CATALOG (use these; the full live catalog is appended to your context):
- execute_command — run PowerShell/terminal commands (real OS execution)
- read_file / write_file / edit_file / list_directory — filesystem operations inside the workspace
- web_search — live DuckDuckGo internet search
- scrape_webpage — fetch readable text from a URL
- python_eval — run Python in an isolated subprocess
- deep_search — multi-hop, multi-source research dossier on a topic
- deep_coder — full software engineering cycle: write files, syntax-check, run tests
- launch_application — open Windows desktop apps
- system_info — read live OS / CPU / RAM / disk / Python environment facts
- manage_processes — list or kill running OS processes
- memory_save — store a fact in long-term persistent memory (remembered forever across sessions)
- memory_search — recall previously saved facts from long-term memory
- mcp_* — tools exposed by connected MCP servers (filesystem, etc.)

### EFFICIENCY RULES (you are faster than typical agents):
- Never re-run a tool to observe already-known output. Cache results mentally.
- If a single tool call can satisfy the task, do NOT invent extra steps.
- Do not call web_search for general knowledge you already possess; use it only for fresh/live data.
- If the goal is reached, stop immediately and give the final answer — do not add decorative tool calls.
- Use memory_save for important user facts (names, preferences, decisions) so future sessions can recall them.

### FORMATTING & CoT:
- Enclose reasoning, strategy, and reflection inside <thought>...</thought> tags.
- To invoke tools output: <tool_call>{"name": "tool_name", "arguments": {...}}</tool_call> (or native tool_calls when supported).
- After tool execution you will receive the result; analyze it, then continue.
- Final answers must be markdown-formatted, concise but complete, with code blocks when relevant.

### LANGUAGE:
You natively understand Uzbek, English, and Russian. Always respond in the language of the user unless requested otherwise. Be professional, direct, precise, and proactive.

Always remember: You are not just a chatbot — you are an executive agent that gets tasks DONE in the real world, faster and more reliably than any conventional LLM.
"""

REFLECTION_PROMPT = """You are the CRITIC phase of TITAN AGENT. A task was just executed using real tools, and a draft answer was produced.

Review the ENTIRE interaction critically before finalizing:
- Was the user's ORIGINAL request fully satisfied? Check every requirement they asked for.
- Are all claims verified by actual tool results? Remove or fix anything that was only assumed.
- Are there errors, incomplete outputs, missing edge cases, or a better approach?
- Will a human user consider the job DONE after reading your answer?

If anything is missing or wrong, use the tools to fix it NOW (make the needed tool call), or clearly correct/complete your answer.
Then produce the FINAL polished answer to the user (in their language, markdown, complete and precise).
Do not repeat the whole history — output only the final answer (or the tool call needed to finish the job).
"""

DEEP_THINKING_PROMPT = """You are currently operating in DEEP THINKING mode. Elevate your rigor:
- Decompose the problem into explicit sub-problems and reason about each one in detail.
- Consider alternative approaches, edge cases, and failure modes before committing.
- After every step, ask yourself: is there anything unverified, ambiguous, or missing?
- Do not settle for a shallow answer: dig until the result is provably correct and complete.
- You have extra iteration budget — use it deliberately for verification, never for decoration.
"""

DEEP_SEARCH_PROMPT = """You are currently operating in DEEP SEARCH mode. This is a research-heavy task:
- Produce a comprehensive, multi-angle research dossier using deep_search and web_search tools.
- Cross-check claims across multiple sources; prefer verifiable, recently updated information.
- Scrape primary pages when a snippet is insufficient (scrape_webpage tool).
- Structure the final answer with sections and cite the sources you actually retrieved.
- If evidence is thin or conflicting, say so explicitly instead of guessing.
"""

class AgentEvent:
    def __init__(self, event_type: str, data: Any):
        self.type = event_type
        self.data = data

    def to_dict(self):
        return {"type": self.type, "data": self.data}

class TitanAgent:
    def __init__(
        self,
        llm: LLMClient | None = None,
        tools: ToolRegistry | None = None,
        mcp: MCPManager | None = None,
        memory: MemoryManager | None = None
    ):
        self.llm = llm or LLMClient()
        self.tools = tools or ToolRegistry()
        self.mcp = mcp or MCPManager()
        self.memory = memory or MemoryManager()
        self.system_prompt = TITAN_SYSTEM_PROMPT

    def _build_memory_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "memory_save",
                    "description": "Saves a fact or piece of information into Titan's long-term persistent memory so it is remembered in all future sessions (e.g. user name, preferences, decisions).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "Unique short key for the fact (e.g. 'user_name')."},
                            "value": {"type": "string", "description": "The fact content to remember."},
                            "category": {"type": "string", "description": "Optional category (e.g. 'profile', 'project', 'preference')."}
                        },
                        "required": ["key", "value"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_search",
                    "description": "Searches Titan's long-term persistent memory for facts saved in earlier sessions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Text to search for in remembered facts."},
                            "limit": {"type": "integer", "description": "Max results to return (default 5)."}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

    def _build_tools_list(self) -> list[dict[str, Any]]:
        all_tools = list(self.tools.get_tool_definitions())
        # Add memory tools (agent-level, routed through MemoryManager)
        all_tools.extend(self._build_memory_tool_definitions())
        # Add MCP tools if connected
        all_tools.extend(self.mcp.get_all_tools())
        return all_tools

    def _build_tool_catalog_text(self) -> str:
        """Compact live tool catalog appended to the system prompt each turn."""
        lines = []
        for t in self.tools.get_tool_definitions():
            fn = t.get("function", {})
            params = fn.get("parameters", {}).get("properties", {})
            param_hint = ", ".join(params.keys()) if params else "no params"
            lines.append(f"- {fn.get('name')}({param_hint}): {fn.get('description', '')}")
        for t in self._build_memory_tool_definitions():
            fn = t.get("function", {})
            params = fn.get("parameters", {}).get("properties", {})
            param_hint = ", ".join(params.keys()) if params else "no params"
            lines.append(f"- {fn.get('name')}({param_hint}): {fn.get('description', '')}")
        mcp_tools = self.mcp.get_all_tools()
        if mcp_tools:
            lines.append("\nMCP server tools:")
            for t in mcp_tools:
                fn = t.get("function", {})
                lines.append(f"- {fn.get('name')}: {fn.get('description', '')}")
        return "\n".join(lines)

    async def execute_tool_unified(self, name: str, args: dict[str, Any]) -> str:
        if name == "memory_save":
            key = str(args.get("key", "")).strip()
            value = str(args.get("value", "")).strip()
            category = str(args.get("category", "agent")).strip() or "agent"
            if not key or not value:
                return "Error: memory_save requires both 'key' and 'value'."
            self.memory.remember_fact(key, value, category)
            return f"Saved to memory: {key} = {value} (category: {category})"
        if name == "memory_search":
            query = str(args.get("query", "")).strip()
            limit = int(args.get("limit", 5) or 5)
            if not query:
                return "Error: memory_search requires 'query'."
            facts = self.memory.search_knowledge(query, limit=limit)
            if not facts:
                return "No matching facts found in memory."
            return "\n".join(
                f"- [{f['category']}] {f['key']}: {f['value']}" for f in facts
            )
        if name.startswith("mcp_"):
            return await self.mcp.execute_tool(name, args)
        else:
            return await self.tools.execute_tool(name, args)

    async def _emit_tool_results(
        self,
        response,
        messages: list[dict[str, Any]],
        iteration: int
    ) -> AsyncGenerator[AgentEvent, None]:
        """Executes all tool_calls inside `response` IN PARALLEL and streams events. Mutates `messages` in place."""
        assistant_msg = {
            "role": "assistant",
            "content": response.content or "",
            "tool_calls": response.tool_calls
        }
        messages.append(assistant_msg)

        parsed = []
        for tool_call in response.tool_calls:
            fn = tool_call.get("function", {})
            t_name = fn.get("name", "")
            t_args_raw = fn.get("arguments", "{}")
            if isinstance(t_args_raw, str):
                try:
                    t_args = json.loads(t_args_raw)
                except Exception:
                    t_args = {}
            else:
                t_args = t_args_raw
            parsed.append((tool_call, t_name, t_args))

        # Emit all scheduled tool_call events first
        for tool_call, t_name, t_args in parsed:
            yield AgentEvent("tool_call", {"name": t_name, "arguments": t_args})

        if len(parsed) > 1:
            yield AgentEvent("status", f"Running {len(parsed)} tools in parallel...")
        else:
            yield AgentEvent("status", f"Running tool: {parsed[0][1]}...")

        # Execute all tools concurrently
        async def _run_one(tool_call, t_name, t_args):
            try:
                result = await self.execute_tool_unified(t_name, t_args)
                return tool_call, t_name, result
            except Exception as e:
                return tool_call, t_name, f"Error: {e!s}"

        results = await asyncio.gather(*(_run_one(*p) for p in parsed))

        # Emit results and append tool messages in original order
        for tool_call, t_name, result in results:
            yield AgentEvent("tool_result", {"name": t_name, "result": result})
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.get("id", f"call_{iteration}"),
                "name": t_name,
                "content": str(result)
            })

    async def run_task(
        self,
        user_input: str,
        session_id: str = "default_session",
        mode: str = "fast"
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        Executes a user request with autonomous multi-step reasoning, tool execution,
        and a critical reflection (self-review) pass before the final answer.
        mode: "fast" | "deep" | "deep_search"
        Yields AgentEvent objects for real-time streaming to Web UI / CLI.
        """
        if mode not in ("fast", "deep", "deep_search"):
            mode = "fast"

        # Save user message to memory
        self.memory.add_message(session_id, "user", user_input)

        # Retrieve conversation history
        history = self.memory.get_recent_messages(session_id, limit=10)

        # Format messages for LLM
        catalog_text = self._build_tool_catalog_text()
        system_content = (
            self.system_prompt
            + "\n\n### LIVE TOOL CATALOG (all tools currently available):\n"
            + catalog_text
        )
        if mode == "deep":
            system_content += "\n\n" + DEEP_THINKING_PROMPT
        elif mode == "deep_search":
            system_content += "\n\n" + DEEP_SEARCH_PROMPT

        messages = [{"role": "system", "content": system_content}]
        for msg in history:
            m_dict = {"role": msg["role"], "content": msg["content"]}
            messages.append(m_dict)

        max_steps = MAX_ITERATIONS
        if mode in ("deep", "deep_search"):
            # Deep modes get a bigger iteration budget
            max_steps = min(MAX_ITERATIONS * 2, 40)

        # Deep Search mode: seed the context with an auto-researched dossier first
        if mode == "deep_search":
            yield AgentEvent("status", "Building deep search dossier...")
            try:
                from .deep_search import DeepSearchEngine
                dossier = await DeepSearchEngine().run(user_input)
                context_block = (
                    f"### DEEP SEARCH DOSSIER (auto-researched):\n"
                    f"Topic: {dossier['topic']}\n"
                    f"Total sources found: {dossier['total_sources_found']}\n\n"
                    "Sources:\n"
                )
                for s in dossier.get("sources", [])[:6]:
                    context_block += f"- {s.get('title', '')}: {s.get('url', '')}\n"
                messages.append({"role": "system", "content": context_block})
                yield AgentEvent("status", f"Dossier ready: {dossier['total_sources_found']} sources found.")
            except Exception as e:
                yield AgentEvent("status", f"Auto deep search unavailable: {e!s}")

        yield AgentEvent("status", "Planning and analyzing the task...")

        iteration = 0
        used_tools = False
        reflect_done = False

        while iteration < max_steps:
            iteration += 1
            yield AgentEvent("step_start", {"step": iteration, "max_steps": max_steps})

            available_tools = self._build_tools_list()

            try:
                response = await self.llm.chat_completion(messages, tools=available_tools)
            except Exception as e:
                err_msg = f"Error connecting to LLM: {e!s}"
                yield AgentEvent("error", err_msg)
                return

            # Yield thoughts if any
            if response.thoughts:
                yield AgentEvent("thought", response.thoughts)

            # If model produced tool calls, execute them (in parallel)
            if response.tool_calls:
                used_tools = True
                async for ev in self._emit_tool_results(response, messages, iteration):
                    yield ev

                # Check if iterations limit reached
                if iteration >= max_steps:
                    yield AgentEvent("final_answer", f"Reached the maximum number of steps ({max_steps}). The latest state and results are preserved above.")
                    return
                continue

            # ---- No tool calls: candidate final answer ----
            final_text = response.content or ""

            # Reflection (critic) pass: after real tool use (or always in deep modes)
            needs_reflection = used_tools or mode in ("deep", "deep_search")
            if needs_reflection and not reflect_done:
                reflect_done = True
                yield AgentEvent("status", "Critically reviewing results (reflection)...")
                critic_messages = list(messages) + [
                    {"role": "assistant", "content": final_text},
                    {"role": "user", "content": REFLECTION_PROMPT}
                ]
                try:
                    crit = await self.llm.chat_completion(critic_messages, tools=available_tools)
                except Exception as e:
                    yield AgentEvent("error", f"Reflection pass error: {e!s}")
                    crit = None

                if crit is not None:
                    if crit.thoughts:
                        yield AgentEvent("thought", crit.thoughts)
                    if crit.tool_calls:
                        # Reflection decided more work is needed — execute it
                        async for ev in self._emit_tool_results(crit, messages, iteration):
                            yield ev
                        if iteration >= max_steps:
                            yield AgentEvent("final_answer", f"Reached the maximum number of steps ({max_steps}). The latest state and results are preserved above.")
                            return
                        continue
                    elif crit.content:
                        # Reflection produced the polished final answer
                        final_text = crit.content or final_text

            yield AgentEvent("final_answer", final_text)
            self.memory.add_message(session_id, "assistant", final_text, thoughts=response.thoughts)
            return