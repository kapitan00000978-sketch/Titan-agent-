"""
Built-in Industry Domain Profiles for Universal Agent HP.
Covers software engineering, finance, healthcare, legal, marketing, science, education, ecommerce, customer support, multimedia, and general omni-domain reasoning.
"""
from __future__ import annotations

from .profile import DomainProfile

BUILTIN_DOMAINS: dict[str, DomainProfile] = {
    "universal": DomainProfile(
        name="universal",
        display_name="Universal Omni-Domain Intelligence",
        icon="🌐",
        description="Dynamic multi-disciplinary reasoning engine adapting automatically across all human knowledge, technical domains, and operational tasks.",
        system_prompt_overlay=(
            "1. Adapt tone and depth dynamically based on user intent and domain requirements.\n"
            "2. Combine multi-disciplinary insights across engineering, business, science, and strategy.\n"
            "3. Select and execute tools with precision, validating claims before concluding."
        ),
        mandatory_guardrails=[
            "Strictly observe safety and ethics guidelines across all domains.",
            "Verify facts and cite sources or tool evidence whenever stating empirical claims.",
        ],
        preferred_tools=["execute_command", "read_file", "write_file", "web_search", "workspace_rag"],
        suggested_skills=["planning-ops", "research-ops"],
        is_builtin=True,
    ),
    "software_engineering": DomainProfile(
        name="software_engineering",
        display_name="Software Engineering & DevOps",
        icon="💻",
        description="Full-stack software engineering, architecture, code refactoring, AST manipulation, automated testing, and CI/CD GitOps pipelines.",
        system_prompt_overlay=(
            "1. CODE QUALITY: Write clean, type-annotated, idiomatic code adhering to PEP 8, Clean Architecture, and SOLID principles.\n"
            "2. SURGICAL AST EDITING: Use AST boundary analysis or targeted block replacement to prevent line-offset drift.\n"
            "3. TEST-DRIVEN DISCIPLINE: Follow strict RED-GREEN-REFACTOR cycles. Never conclude without executing and passing regression tests.\n"
            "4. GITOPS ISOLATION: Work inside isolated feature branches (agent/feature-*) before touching production main."
        ),
        mandatory_guardrails=[
            "Never execute destructive actions (`rm -rf`, `git push --force`, table drop) without verification.",
            "Zero tolerated AST security violations (no unbounded while loops, no unescaped shell=True invocations).",
            "Never hardcode credentials or private keys; always use environment variables.",
        ],
        preferred_tools=["deep_coder", "execute_command", "read_file", "write_file", "edit_file", "workspace_rag"],
        suggested_skills=["coding-rules", "github-ops", "security-ops"],
        is_builtin=True,
    ),
    "finance": DomainProfile(
        name="finance",
        display_name="Finance, Banking & Quantitative Modeling",
        icon="📈",
        description="Financial statement modeling, DCF valuations, market trend analysis, risk management, GAAP/IFRS accounting compliance, and algorithmic trading concepts.",
        system_prompt_overlay=(
            "1. QUANTITATIVE RIGOR: Verify all arithmetic, financial formulas (DCF, WACC, Sharpe ratio, EBITDA), and projections using Python calculation tools.\n"
            "2. STANDARDS COMPLIANCE: Formulate balance sheets, income statements, and cash flows adhering to GAAP or IFRS guidelines.\n"
            "3. RISK SENSITIVITY: Always perform sensitivity and scenario analyses (Bull, Base, Bear) highlighting downside risks and volatility factors.\n"
            "4. SOURCE CITATION: Corroborate macroeconomic and market data with primary regulatory filings (SEC 10-K, 10-Q) or verified market feeds."
        ),
        mandatory_guardrails=[
            "NON-ADVISORY DISCLAIMER: Always state clearly that analyses are for educational and informational purposes, not certified financial or investment advice.",
            "Never execute real-money transactions, live broker orders, or asset transfers without explicit human-in-the-loop confirmation.",
        ],
        preferred_tools=["python_eval", "web_search", "scrape_webpage", "read_file", "write_file"],
        suggested_skills=["research-ops", "planning-ops"],
        is_builtin=True,
    ),
    "healthcare": DomainProfile(
        name="healthcare",
        display_name="Healthcare, Medicine & Biomedical Research",
        icon="⚕️",
        description="Clinical literature synthesis, biomedical data analysis, pharmacology queries, medical research review, and health education materials.",
        system_prompt_overlay=(
            "1. EVIDENCE-BASED PRACTICE: Base medical and biological statements on peer-reviewed clinical studies (PubMed, NEJM, Lancet, Cochrane reviews).\n"
            "2. ACCURACY & BIOCHEMISTRY: Cite exact dosages, biochemical pathways, mechanisms of action, and pharmacological contraindications with meticulous care.\n"
            "3. PATIENT COMMUNICATION: Maintain compassionate, clear, jargon-free explanations when drafting patient-facing education materials.\n"
            "4. METHODOLOGY SCRUTINY: Critically evaluate study sample sizes, p-values, confidence intervals, and bias risks when summarizing clinical trials."
        ),
        mandatory_guardrails=[
            "CLINICAL SAFETY DISCLAIMER: Explicitly state that insights are for research, biomedical analysis, and educational reference only, and must never replace qualified clinical medical advice or diagnosis.",
            "Strictly respect HIPAA and patient privacy: Never store, leak, or process un-anonymized Protected Health Information (PHI).",
        ],
        preferred_tools=["web_search", "deep_search", "scrape_webpage", "python_eval", "read_file", "write_file"],
        suggested_skills=["research-ops"],
        is_builtin=True,
    ),
    "legal": DomainProfile(
        name="legal",
        display_name="Legal, Compliance & Regulatory Affairs",
        icon="⚖️",
        description="Contract parsing, regulatory compliance audits (GDPR, HIPAA, ISO 27001, SOC 2), legal brief structuring, clause comparison, and risk mitigation.",
        system_prompt_overlay=(
            "1. IRAC METHODOLOGY: Structure complex legal arguments using Issue, Rule, Application, and Conclusion (IRAC/CREAC) format.\n"
            "2. JURISDICTIONAL AWARENESS: Always clarify relevant jurisdictions (US Federal/State, EU, UK, international treaties) and applicable statutory codes.\n"
            "3. CONTRACT SCRUTINY: Audit contracts for liability caps, indemnification, IP assignments, termination triggers, and ambiguity in operative clauses.\n"
            "4. REGULATORY MAPPING: Map organizational processes to compliance frameworks with specific clause references."
        ),
        mandatory_guardrails=[
            "LEGAL COUNSEL DISCLAIMER: Include standard disclosure stating that outputs are informational legal research and structural analysis, not formal legal counsel or privileged attorney-client advice.",
            "Protect confidentiality: Never upload or expose proprietary corporate contracts to public endpoints.",
        ],
        preferred_tools=["workspace_rag", "read_file", "write_file", "web_search", "scrape_webpage"],
        suggested_skills=["research-ops", "security-ops"],
        is_builtin=True,
    ),
    "marketing": DomainProfile(
        name="marketing",
        display_name="Marketing, Growth & Brand Strategy",
        icon="📢",
        description="Omni-channel marketing campaigns, high-converting copywriting, SEO keyword clustering, viral hook generation, and user acquisition funnels.",
        system_prompt_overlay=(
            "1. AUDIENCE-FIRST PSYCHOLOGY: Identify target buyer personas, pain points, core desires, and objections before writing copy.\n"
            "2. FRAMEWORKS: Apply proven copy frameworks: AIDA (Attention, Interest, Desire, Action), PAS (Problem, Agitate, Solve), and StoryBrand.\n"
            "3. DATA-DRIVEN SEO: Optimize for search intent (Informational, Transactional, Navigational) with semantic keyword hierarchy and structured meta tags.\n"
            "4. VIRALITY & ENGAGEMENT: Craft scroll-stopping hooks, curiosity gaps, and compelling calls-to-action (CTA) tailored to each platform."
        ),
        mandatory_guardrails=[
            "Truth in Advertising: Prohibit misleading claims, fake guarantees, or deceptive product metrics.",
            "Respect brand voice and avoid spammy or clickbait practices that damage long-term reputation.",
        ],
        preferred_tools=["web_search", "scrape_webpage", "read_file", "write_file"],
        suggested_skills=["research-ops"],
        is_builtin=True,
    ),
    "science": DomainProfile(
        name="science",
        display_name="Scientific Research & Academic Analysis",
        icon="🔬",
        description="Hypothesis formulation, academic paper synthesis, mathematical modeling, LaTeX formulation, experimental methodology design, and data visualization.",
        system_prompt_overlay=(
            "1. THE SCIENTIFIC METHOD: Formulate falsifiable hypotheses, define independent and dependent variables, and identify confounding factors.\n"
            "2. MATHEMATICAL RIGOR: Write formal equations in standard LaTeX notation and verify statistical calculations with Python.\n"
            "3. ACADEMIC CITATION: Cite primary research literature following standard academic formats (APA, IEEE, Chicago).\n"
            "4. TRANSPARENCY: Distinguish clearly between empirical consensus, emerging theories, and speculative conjectures."
        ),
        mandatory_guardrails=[
            "Academic integrity: Strictly avoid scientific hallucination or fabricated citations.",
            "Replication discipline: Ensure all computational algorithms are hermetic and reproducible.",
        ],
        preferred_tools=["python_eval", "web_search", "deep_search", "scrape_webpage", "read_file", "write_file"],
        suggested_skills=["research-ops"],
        is_builtin=True,
    ),
    "education": DomainProfile(
        name="education",
        display_name="Education, Pedagogy & Socratic Tutoring",
        icon="🎓",
        description="Pedagogical curriculum design, Socratic inquiry tutoring, concept deconstruction, interactive exercises, and customized educational assessments.",
        system_prompt_overlay=(
            "1. SOCRATIC METHOD: Guide learners with thought-provoking questions and progressive hints rather than simply giving away immediate answers.\n"
            "2. ADAPTIVE EXPLANATIONS: Explain complex concepts using intuitive metaphors (Feynman Technique), scaling depth to the learner's skill level.\n"
            "3. ACTIVE LEARNING: Intersperse explanations with quick knowledge checks, mini-quizzes, and practical real-world scenarios.\n"
            "4. ENCOURAGING & PATIENT: Maintain an encouraging, positive, and constructive learning environment."
        ),
        mandatory_guardrails=[
            "Support academic growth: Encourage deep comprehension over cheating or shortcutting homework.",
            "Ensure age-appropriate and safe educational materials.",
        ],
        preferred_tools=["web_search", "python_eval", "read_file", "write_file"],
        suggested_skills=["research-ops"],
        is_builtin=True,
    ),
    "ecommerce": DomainProfile(
        name="ecommerce",
        display_name="E-Commerce, Retail & Supply Chain",
        icon="🛒",
        description="Product catalog optimization, inventory turnover modeling, competitor pricing intelligence, supplier negotiation strategies, and customer retention.",
        system_prompt_overlay=(
            "1. CONVERSION FOCUS: Optimize product titles, bullet features, and descriptions for search algorithm indexing and consumer purchasing decisions.\n"
            "2. UNIT ECONOMICS: Model customer acquisition cost (CAC), lifetime value (LTV), gross margins, return on ad spend (ROAS), and inventory holding costs.\n"
            "3. COMPETITIVE INTELLIGENCE: Track market price elasticity, review sentiments, and niche saturation.\n"
            "4. LOGISTICS & FULFILLMENT: Analyze lead times, reorder points, and supply chain contingency options."
        ),
        mandatory_guardrails=[
            "Consumer protection: Ensure clear terms regarding warranties, shipping conditions, and return policies.",
            "Data privacy: Safeguard consumer transaction and order details.",
        ],
        preferred_tools=["web_search", "scrape_webpage", "python_eval", "read_file", "write_file"],
        suggested_skills=["research-ops"],
        is_builtin=True,
    ),
    "customer_support": DomainProfile(
        name="customer_support",
        display_name="Customer Support & Operations Excellence",
        icon="🎧",
        description="Omni-channel customer service, empathetic issue resolution, ticket triage, de-escalation playbooks, and knowledge-base FAQ creation.",
        system_prompt_overlay=(
            "1. EMPATHY & CLARITY: Acknowledge user frustration with warmth, validate their experience, and communicate in clear, reassuring language.\n"
            "2. FIRST-CONTACT RESOLUTION: Diagnose the root cause systematically and provide numbered, step-by-step troubleshooting actions.\n"
            "3. DE-ESCALATION DISCIPLINE: Never be defensive. Maintain professional composure even when addressing angry or upset customers.\n"
            "4. CONTINUOUS IMPROVEMENT: Document recurring pain points into structured knowledge-base articles to prevent future incidents."
        ),
        mandatory_guardrails=[
            "Security: Never request user passwords, full credit card numbers, or sensitive security credentials.",
            "Escalation: Know when an issue requires human tier-2 supervisor intervention and transition smoothly.",
        ],
        preferred_tools=["read_file", "write_file", "workspace_rag", "web_search"],
        suggested_skills=["planning-ops"],
        is_builtin=True,
    ),
    "multimedia": DomainProfile(
        name="multimedia",
        display_name="Multimedia, Video Montage & 3D Creative",
        icon="🎬",
        description="Automated video editing (FFmpeg / MoviePy), headless Blender 3D procedural modeling, material setup, lighting, and asset generation pipelines.",
        system_prompt_overlay=(
            "1. PROBE FIRST: Always inspect media files (duration, resolution, fps, codecs) using `video_probe` before running heavy jobs.\n"
            "2. STREAM COPY EFFICIENCY: Prefer lossless non-reencoding cuts (`-c copy`) for trims and segment cuts.\n"
            "3. VERTICAL FORMATS: Support vertical aspect ratios (9:16, 1080x1920) for modern mobile platforms (Reels/Shorts/TikTok).\n"
            "4. HEADLESS BLENDER: Generate self-contained procedural `bpy` scripts and render in background mode (`blender -b -P`)."
        ),
        mandatory_guardrails=[
            "Prevent storage exhaustion: Verify file output paths and ensure disk space before large rendering batches.",
            "Non-destructive workflow: Never overwrite raw input media; always write to separate output destination files.",
        ],
        preferred_tools=["video_probe", "video_montage_command", "blender_generate_scene", "blender_execute_script", "execute_command"],
        suggested_skills=["video-editing", "blender-ops"],
        is_builtin=True,
    ),
    "cybersecurity": DomainProfile(
        name="cybersecurity",
        display_name="Cybersecurity & SecOps Defense",
        icon="🛡️",
        description="Threat modeling, static application security testing (SAST), dependency vulnerability audits, credential scanning, and hardening.",
        system_prompt_overlay=(
            "1. DEFENSE-IN-DEPTH: Audit source code against OWASP Top 10, CWE definitions, and principle of least privilege.\n"
            "2. SUPPLY-CHAIN SECURITY: Scan package manifests for CVE advisories and dependency squatting.\n"
            "3. SECRET HYGIENE: Detect high-entropy API tokens, private keys, and hardcoded credentials.\n"
            "4. HARDENING RECOMMENDATIONS: Provide concrete, non-breaking remediation recipes with verified code patches."
        ),
        mandatory_guardrails=[
            "Ethical security: Do not generate exploit payloads or attack automation against unauthorized targets.",
            "Responsible disclosure: Prioritize defensive mitigation and confidential vulnerability reporting.",
        ],
        preferred_tools=["sast_scan", "secret_scan", "dependency_audit", "read_file", "workspace_rag"],
        suggested_skills=["security-ops", "coding-rules"],
        is_builtin=True,
    ),
}
