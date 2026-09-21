---
name: security-ops
description: Security review playbook — threat-model first, check injection, secrets, permissions.
keywords: security, vulnerability, audit, scan, owasp, injection, secret, threat, risk, exploit
---

# Security Ops

Follow this playbook for any security review, scan, or hardening task.

## Threat-model first
1. Identify the trust boundaries: what input is untrusted, where does data
   cross into execution, storage, or display?
2. Enumerate the top risks in scope (injection, XSS, SSRF, path traversal,
   secrets exposure, auth bypass, rate limiting).

## Checks
3. INPUT: every user-controlled string must be validated/escaped; look for
   `eval`, `exec`, raw SQL concatenation, unsafe regex.
4. SECRETS: scan for hardcoded API keys, tokens, passwords; flag anything
   committed to repos or logged.
5. PERMISSIONS: least privilege — what runs as admin that shouldn't? What
   files are world-readable?
6. NETWORK: SSRF guards on any URL-fetching code; TLS everywhere; no
   debug endpoints in production.
7. DEPENDENCIES: flag known-vulnerable packages and outdated pinned versions.

## Output shape
Report findings by severity: **Critical / Important / Minor / Nit**, each
with file/line-ish location, why it matters, and a concrete fix. End with a
priority-ordered remediation list.