Here’s a concise “security-gap radar” you can keep handy as you continue hardening both the TypeScript front-end and the FastAPI/WebSocket back-end.  It isn’t an exhaustive penetration-test plan, but it highlights the places that most often get missed after teams tighten input–validation but before they invite a red-team.

────────────────────────
1. Surface-Area Inventory
────────────────────────
• REST routes (public, authenticated, admin)  
• WebSocket endpoints (quotes, analytics, admin dashboard, notifications)  
• Static assets & Next.js pages (SSG/SSR)  
• Third-party browser scripts (analytics, feature flags, etc.)  
• CI/CD pipeline & secrets management (Doppler, GPG keys, pre-commit hooks)  
• DevTools / mock servers that can be flipped on accidentally in prod

Ask: “For each surface, what can an untrusted party send me, and what can they learn?”

────────────────────────
2. Front-End Defences (browser → your servers)
────────────────────────
1. Content Security Policy (CSP)  
   • Lock script-src, frame-src, connect-src to only the domains you truly need.  
2. Strict-Transform Sanitisation  
   • We now normalise query params; mirror that for body payloads (e.g. multipart forms, JSON).  
   • Sanitise all dynamic text before injecting into `dangerouslySetInnerHTML`.  
3. CORS & Pre-flight Rules  
   • Fail closed: only allow explicit domains, methods, and headers.  
4. CSRF Protection  
   • Even though you’re mostly API-token based, enable `SameSite` cookies and/or double-submit JWT strategy for browser-based endpoints.  
5. WebSocket Origin & Payload Limits  
   • Check `Origin` header, rate-limit frames per connection, cap frame size.  
   • Enforce per-message schema validation client-side *and* server-side.  
6. Secure Storage  
   • Never persist tokens in `localStorage` (XSS risk). Prefer `httpOnly` cookies or in-memory caches with refresh flows.  
7. Dependency Hygiene  
   • Keep `npm audit` / `pnpm audit` in CI, monitor transitive vulns.  
   • Freeze versions via lockfile; upgrade on a schedule.  
8. MFA / Sensitive Screens  
   • Auto-logout or step-up authentication on long-lived admin pages.

────────────────────────
3. Back-End Defences (API & WS)
────────────────────────
1. Strong Schema & Runtime Validation  
   • FastAPI + Pydantic already help—enforce `model_config = {"extra": "forbid"}` to reject unknown fields.  
2. Auth & AuthZ Layers  
   • Short-lived access tokens, refresh tokens w/ rotation.  
   • Fine-grained scopes / roles; use *deny by default* on new routes.  
   • Record audit-trail for admin ops (e.g., quote overrides).  
3. Rate-Limiting & Abuse Protection  
   • Per-IP + per-account quotas (burst & sustained) on REST and WS.  
   • Captcha / email verification for signup flows if opened to public.  
4. Transport Security  
   • Enforce TLS 1.2+ everywhere (even if in-house/on-prem).  
   • HSTS, secure cookies, and proper cipher suites.  
5. Secrets & Config  
   • Doppler is good—verify prod service accounts have minimum scope; rotate regularly.  
   • Block “debug=true” configs from ever reaching prod images.  
6. Output Encoding  
   • Sanitize data that may be re-rendered in a browser (stored XSS coming *from* API).  
7. File Upload & Binary Data  
   • MIME-type + extension verification, virus scan, limit size, store off-site or in a hardened bucket.  
8. WebSocket Session Management  
   • Issue one-time signed tokens (`exp`, `nbf`, `aud`) for the handshake; re-validate on reconnect.  
   • Explicitly close idle or abusive connections; enforce message schema per channel.  
9. Error-Handling & Logging  
   • Send generic error to client, detailed stack only to structured logs (with redaction).  
   • Include request-id correlation, but never leak secrets in logs.  
10. Scheduled Security Jobs  
   • Dependency scanning (SCA), SAST, DAST, container-image CVE scans.  
   • Automated dependency-update PRs with tests.

────────────────────────
4. Deployment / Infrastructure
────────────────────────
• Even on-prem or private colo, assume the network is hostile—firewalls, zero-trust, mutual-TLS between services.  
• Immutable images (OCI) + read-only root filesystems.  
• Secrets injected at run-time (env vars or in-memory), never baked into images.  
• Automated patch management for OS and runtime.  
• Back-ups + disaster-recovery drills (ransomware resilience).

────────────────────────
5. Future “Adversarial” Pass
────────────────────────
1. Threat-Model Review (STRIDE, LINDDUN)  
2. Automated scanners (ZAP, Burp) against staging  
3. Dependency fuzzing (OSS-Fuzz, Jazzer) for critical parsing code  
4. Manual penetration test / red-team exercise  
5. Chaos-engineering style “fault injection” into auth flows and WebSocket channels.

────────────────────────
6. Quick-Reference “Don’t Forget” List
────────────────────────
☑️  *Every* external input validated & length-capped.  
☑️  Output always encoded for the channel (HTML, JSON, URL).  
☑️  Principle of least privilege—services, DB users, tokens.  
☑️  Logged-in user context checked on *every* business action.  
☑️  Rotate & revoke credentials on a schedule (not just when leaked).  
☑️  Back-ups tested, not just configured.  
☑️  Staging mirrors prod settings minus secrets.  
☑️  CI pipeline is locked down—no write tokens in untrusted jobs.

Keep this list nearby as you iterate; each wave can choose a few items to tighten while features progress.  That balanced approach avoids security “big bangs” while still closing the obvious doors unethical actors love to test first.