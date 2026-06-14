# Identifier Existence-Verifier — Evidence Check (web-verified)

**To:** Product / Decision owner · **Date:** 2026-06-14 · **Posture:** Skeptical evidence review

---

## 1. VERDICT

**GO-WITH-CAVEATS — confidence: MODERATE-HIGH.** The problem is real and primary-sourced (peer-reviewed USENIX/ICSE/JLA/JELS evidence that LLMs emit non-existent packages, APIs, and citations at meaningful rates), but the *only* defensible wedge is the **cross-class, in-loop, fail-closed gate** — every single-class slice (citations, packages) is already contested by shipping agent-callable tools, so a single-class pitch is a NO-GO.

---

## 2. Is the magnitude real?

| Claim | Verdict | Corrected figure | Best source (URL) | Source quality |
|---|---|---|---|---|
| ~19.7% of LLM code references hallucinated packages; ~43% recur | **Confirmed** | 19.7% is share of *recommended packages* (not "code samples"), 440,445/2.23M; 205,474 unique. 43% recur in **all 10** re-runs (58% >once, 39% never). Python-only recurrence subset. | https://arxiv.org/abs/2406.10279 ; https://www.usenix.org/system/files/conference/usenixsecurity25/sec25cycle1-prepub-742-spracklen.pdf ; https://github.com/Spracks/PackageHallucination | **Primary, peer-reviewed (USENIX Security 2025).** Strongest tier. |
| "Slopsquatting" is a real named supply-chain vector | **Confirmed (mechanism); thin (in-the-wild malice)** | Term real (Seth Larson, Apr 2025). Mechanism proven by **benign** PoC (huggingface-cli, ~30k downloads). Malicious in-the-wild = weakly evidenced/inferred; Wikipedia: "not yet... a reported [cyber]attack." | https://simonwillison.net/2025/Apr/12/andrew-nesbitt/ ; https://www.theregister.com/2024/03/28/ai_bots_hallucinate_software_packages/ ; https://en.wikipedia.org/wiki/Slopsquatting | Mixed: academic substrate primary; **repeatability stat (43/58%) traces to Socket.dev, an interested vendor.** Real-world malice = vendor-hedged. |
| LLMs fabricate citations/URLs/DOIs 3–13% (RAG) to 58–88% (legal) | **Confirmed — but do NOT conflate the ranges** | 3–13% = URLs *with* search/RAG; 58–88% = legal *without* retrieval; purpose-built legal RAG sits 17–33%. Different conditions. | https://arxiv.org/abs/2604.03173 (3–13%, preprint) ; https://academic.oup.com/jla/article/16/1/64/7699227 (58–88%) ; https://arxiv.org/abs/2405.20362 (17–33%) | Legal figures **peer-reviewed (JLA/JELS)**; the 3–13% is an **April-2026 preprint, not yet peer-reviewed**. 89.4%-humanities-DOI = illustrative, secondhand. |
| LLMs call nonexistent/deprecated APIs/symbols | **Confirmed, multi-source** | Deprecated-API usage 34–37% (DUR); rare-API invalid ~61% (CloudAPIBench); API-misuse affects 44% of tasks. Highly conditional on symbol frequency. | https://arxiv.org/abs/2406.09834 (ICSE 2025) ; https://arxiv.org/abs/2407.09726 ; https://arxiv.org/html/2409.20550v1 (TOSEM) | **Peer-reviewed (ICSE/TOSEM).** Solid; deprecated ≠ nonexistent (distinct problem). |
| Hallucinated identifiers cause real harm in agentic coding | **Confirmed (edits, tool-calls); inferred (slopsquat victim chain)** | Failed edits + non-registered tool-call crashes best-grounded; slopsquat LLM→victim link inferred. | https://arxiv.org/abs/2405.15793 (SWE-agent) ; https://github.com/google/adk-python/issues/4173 ; https://www.koi.ai/blog/phantomraven | Mixed: harm types peer-reviewed/reproducible; **PhantomRaven attribution is vendor; victim chain inferred.** |

**What collapsed under verification:** (a) the viral **43%/58% recurrence** stats are most-cited via **Socket.dev, a vendor selling mitigation**; (b) **in-the-wild *malicious* slopsquatting** is NOT substantiated by primary sources (clean case was a benign researcher PoC); (c) the **30k-download** figure is a single Lasso/Lanyado anecdote; (d) several "~20% of code" restatements are secondary amplifications of the one USENIX paper.

---

## 3. Is the whitespace real?

| Tool | Classes | Agent-callable? | Gate vs post-hoc | Checks existence? | Overlap |
|---|---|---|---|---|---|
| DepShield MCP | packages (npm, PyPI) | **Yes (MCP)** | **Fail-closed** (via external Cursor rule) | Yes, authoritative | **Closest threat (packages)** |
| DepScope | packages (19 ecosystems) | **Yes (MCP)** | Context-injection (explicitly NOT a gate) | Yes + canonical/deprecated/typosquat | Best resolution; no gate |
| Socket MCP | packages (9 ecosystems) | **Yes (MCP)** | Fail-closed hook **but fails OPEN on error** | Partial (scores, assumes existence) | Strong, security-framed |
| citecheck (arXiv 2603.17339) | citations | **Yes (MCP)** | Fail-closed + policy engine | Yes, 4 registries | **Closest threat (citations)** — "infra for agentic editing" |
| mcp-refchecker | citations | **Yes (MCP)** | Detection/advisory | Yes, authoritative | Direct (citations) |
| Scholar Sidekick verifyCitation | citations (8 ID types) | **Yes (MCP)** | Detection (4-way verdict) | Yes, authoritative | Direct (citations) |
| slopcheck (0xToxSec) | packages (7 registries) | No (CLI/CI/hook) | **Fail-closed** | Yes, authoritative | Out-of-loop gate |
| SafeDep vet MCP | packages (npm, PyPI) | **Yes (MCP)** | Fail-closed (must-call-before-install) | Partial (malice/vuln verdict) | Strong UX proof-point |
| Context7 | library names / API docs | **Yes (MCP)** | Context-injection | **No** (RAG only; no not-found verdict) | Adjacent, NOT a competitor |
| Hallucination Inspector (2604.20202) | API symbols (Android) | No (library) | Post-hoc/batch | Yes (symbol-table oracle) | Research; in-loop "aspirational" |
| PackMonitor (2602.20717) | packages | No (needs logit access) | **Fail-closed "zero hallucination"** | Yes, authoritative | Research; not black-box-able |
| Guardrails AI / NeMo | none (grounding/format) | library | Fail-closed | **No** (entailment, not registry) | Named category — does NOT compete |

**Does ANY shipping tool already do agent-callable, in-loop, cross-class existence verification?** **No.** Every shipping tool is **single-class.** No found product or paper spans citations + packages + tool-names + file-paths + API-symbols under one normalized `exists/not-found/deprecated/canonical` verdict.

**Genuinely unserved slices:** **tool-names, file-paths, API-symbols** (live/agent-callable) — multiple independent scans returned no source.

**Competitors to beat:** Citations = red ocean (do not lead). Packages = contested (DepShield/Socket/SafeDep/DepScope/slopcheck); the clean neutral resolver-as-gate is the open seam but trivially closeable. **Incumbent to differentiate against: citecheck** — one product decision (post-hoc→in-loop) and one scope expansion from being a direct competitor.

---

## 4. Sharpest MVP wedge

Build a single in-loop, agent-callable MCP returning one normalized `exists / not-found / deprecated / canonical` verdict acting as a fail-closed gate — **lead with PACKAGES + the THREE unserved classes (tool-names, file-paths, API-symbols), NOT citations.**

- **Packages** = strongest primary-sourced magnitude + real agentic harm; no shipping tool offers a neutral, intrinsic fail-closed existence gate. Beat them on **intrinsic fail-closed** + **deprecated/canonical**.
- **Tool-names + file-paths + API-symbols** = genuine greenfield, highest-value agentic failures, cheap to check (tool registry, filesystem, LSP/compiler are locally authoritative).
- **Differentiation = the combination:** cross-class union + true fail-closed + deprecated/canonical. Citations are a later breadth-add, never the headline.

---

## 5. Risks & unknowns

- **"Fail-closed" is architecturally hard from outside the model.** An MCP tool cannot force an agent to honor its verdict; true enforcement needs a **hook/gateway** layer. The only true fail-closed existence gates today use decoding-time/logit access (unavailable for black-box models). **Core technical risk: the headline feature is the hardest to deliver honestly.**
- **False-positives on legitimately-new identifiers** → needs grace windows, staleness handling, a `cannot-verify` state.
- **Registry coverage & latency** — five classes = five+ authoritative backends; network errors force a fail-open/closed policy decision.
- **Deprecated ≠ nonexistent, version-dependent** — needs version-aware ground truth.
- **Citation slice crowded/commoditized** — me-too risk if it leaks into headline.
- **Magnitude is dated** — USENIX models are early-2024; a 2026 replication (arXiv 2605.17062) reports **4.62–6.10%**. Verify on current frontier models before sizing.

---

## 6. What still needs checking

- Whether an external MCP can be made genuinely fail-closed without a harness/hook — prototype the Claude Code hook + MCP gateway path **first**.
- DepShield internals (enforcement lives in an external Cursor rule, not the server).
- Context7 not-found path (code read to fully rule out a hidden existence path).
- The April-2026 3–13% citation-URL preprint (2604.03173) — not yet peer-reviewed.
- Current frontier-model hallucination rates (2605.17062 suggests far lower).
- No primary benchmark exists quantifying in-loop existence-gating *effectiveness* across classes.

---

**Bottom line:** GO, but only as the **unified, cross-class, fail-closed gate** wedged on **packages + tool-names + file-paths + API-symbols**. Treat **citecheck** as the incumbent, lead with breadth + intrinsic fail-closed + deprecated/canonical, keep citations off the headline, and de-risk the fail-closed-from-outside-the-model question *first* — it is both the differentiator and the hardest deliverable.
