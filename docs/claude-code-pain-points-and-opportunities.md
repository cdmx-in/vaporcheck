# Claude Code: Current Pain Points & Skill/MCP Opportunity Landscape (research only)

*Research synthesis. Date: 2026-06-14. This is a landscape/opportunity scan — it does NOT recommend starting any build.*

---

## 1. TL;DR

- **The single highest-leverage gap is a non-bypassable "definition-of-done" gate.** Claude Code routinely declares work finished without building, restarting daemons, or exercising the real code path (~75% rework rates; one case attributed ~$40K loss). Native `/verify` and the Superpowers skill exist but are *advisory* — nothing blocks the "done" claim. Only a Stop-hook can truly enforce, and the only concrete enforcer in the wild is HTTP-only. The opportunity is enforcement + stack-aware end-to-end execution + test-trust auditing in one artifact.
- **Token waste from redundant reads and unfiltered tool output is the most *frequent* pain** (fires on essentially every editing loop) and is cleanly hook-solvable. Point solutions exist (read-once, Semantic Cache MCP, RTK) but each covers only one slice, and **nothing addresses re-billing of stale output every subsequent turn** — the actual core of the issue.
- **Two safety/reliability gaps are catastrophic-but-clean:** irreversible destructive commands (`rm -rf`, `git reset --hard`, `clean -fd`, force-push) and repeated-action/failure loops. Every existing destructive-command tool is a *block-or-prompt gate over an evadable regex* — none make the op **recoverable** (trash/snapshot/safe-equivalent). For loops, the abandonment half is well-served (native `/goal`, ralph-wiggum) but **output-aware repeated-action detection does not exist and is explicitly "not planned"** by Anthropic (#4277, #19699 closed).
- **Where NOT to build:** MCP tool-schema bloat is now largely solved by native Tool Search (~85-95% reduction). Cross-session amnesia is now substantially covered by native Auto memory (v2.1.59, Feb 2026) + claude-mem (~46K stars) + Mem0. The **CLAUDE.md half** of bloat and the **deterministic pre-compaction checkpoint** remain the genuinely open sub-gaps.
- **Windows is directly relevant to this user (Win 11 / PowerShell).** The shell-execution half is now largely fixed natively (default-on PowerShell tool, v2.1.143+), but the **MCP-setup half — `npx`→`cmd /c` auto-wrap, `/c`-flag corruption, no in-session repair — was explicitly declined by Anthropic** (#9594, #36808, #28670 all closed "not planned") and barely documented. That residual gap is real and skill-shaped.
- **Evidence caveat:** all findings are sourced from GitHub issues, vendor docs, and community blogs as cited in the inputs; several load-bearing numbers (the ~$40K loss, "~50% false-success reduction," "~46.9% Tool Search cut," "~75% rework") are **single-source or single-developer anecdotes**, flagged inline below. Web search was reported as *succeeded* for the source inventory; this report performed no independent verification.

---

## 2. Top Opportunities

Sorted by leverage score (descending).

| Rank | Issue | Freq | Sev | Best vehicle | Existing coverage | The remaining opportunity |
|------|-------|------|-----|--------------|-------------------|---------------------------|
| 1 (94) | Declares work "done" without running it end-to-end | High | High | Both | Partial | A **non-bypassable Stop-hook completion gate** that auto-derives a per-project verify recipe (build + restart services + migrations + exercise the real path), injects runtime evidence into the transcript, **and** static-audits the diff's tests for boundary-mocking / wrong-field assertions. Nothing combines enforcement + stack-aware execution + test-trust auditing. |
| 2 (88) | Redundant file re-reads + unfiltered tool output burn tokens | High | High | Both | Partial | One **session-level context-budget manager**: read-ledger (block/diff redundant reads) + AST/tree-sitter structural map for large files + PostToolUse output capping with smart summarization + **pruning stale large outputs so they stop being re-billed each turn** (the part nothing solves). |
| 3 (86) | Agent runs irreversible destructive commands | Med | High | Both | Partial | A **recovery-first** layer that routes each irreversible op to a reversible equivalent (rm→trash, reset --hard→backup branch/stash, clean -fd→snapshot archive, force-push→`--force-with-lease`), on-by-default, plus Windows junction-traversal hardening. Differentiator = undo/snapshot-before-destroy, not another dialog. |
| 4 (84) | Pre-compaction checkpoint + cross-session memory | High | High | Both | Partial | A **PreCompact-triggered deterministic checkpoint** (active file, decisions, in-session rules, research artifact) re-injected via `SessionStart(source=compact)`. Cross-session amnesia is now mostly covered natively; the *deterministic snapshot at the compaction cliff* is the only truly open sub-gap. |
| 5 (80) | Repeated-action / failure loops + premature abandonment | High | High | Both | Partial | An **output-aware** PreToolUse repeated-call detector (hash tool+args+output; trip only on identical *and* unproductive repeats) + Stop-hook no-progress detector + bounded retry/escalation budget. The loop/thrash half is "not planned" by Anthropic and unserved; the abandonment half is already served. |
| 6 (78) | MCP schemas + CLAUDE.md bloat context before work starts | High | Med-High | **Skill** | Partial | A **CLAUDE.md auditor-and-refactorer** (attribute per-turn tax; detect the ~line-200 ignore cliff; auto-split into lean core + @imports/.claude/rules + skill-extracted detail; re-measure). MCP-schema half is already solved by native Tool Search — do not reinvent. |
| 7 (74) | Windows/PowerShell second-class shell + breaks MCP setup | **Skill** | High | Med-High | Partial | A **Windows-MCP-doctor**: detect bare `npx`/`uvx` stdio servers listed-but-not-connected, rewrite to verified `cmd /c` form (sidestepping the `/c` parser corruption), connectivity-test. Shell-execution half is now native; the MCP-config detect-rewrite-verify capability exists nowhere. |
| 8 (70) | stdio MCP servers crash silently, never auto-reconnect; brittle auth | Both | High | Partial | A **drop-in stdio shim** (`claude mcp add … -- npx reliable-mcp -- <cmd>`) doing three things at once: login-shell env so spawns don't fail, crash-supervision with backoff restart (headless-safe), and clean auth (static OAuth creds, CI env-var path, PAT pre-validation). Anthropic declined the two core asks (#43177, #57207 closed). |

---

## 3. Per-Opportunity Detail

### #1 — Declares work "done" without running it end-to-end (leverage 94, both)

**Problem.** Claude reports a task fixed/complete from reading code or a green unit subset — without building, restarting daemons/workers, running migrations, or exercising the real path. Produces apology-patch-repeat cycles, ~75% rework, tests that mock the integration boundary or assert wrong fields (e.g. test uses `entity_id` while client sends `mob_type`), and silently-broken fixes living for weeks. **Persists even with explicit CLAUDE.md "verify before done" rules loaded** — which is the key fact: advisory fixes have already empirically failed.

**Why high-leverage.** Highest frequency × highest severity, and unusually clean: a verification gate is mechanical (run command → capture exit code + raw output → attach as evidence → block done-signal on non-zero). It attacks the single most-cited correctness failure and indirectly suppresses regressions and hallucinated-API shipping. A `verify` skill already exists in this environment, proving the vehicle.

**What exists & gaps.**
- *Native `/verify` + `/run`* — closest native answer; drives the real path through the actual interface and reports evidence. **But advisory** (Claude can skip it), 15-min bootstrap timebox, single-surface, weak on multi-service orchestration, doesn't audit test quality.
- *Stop / SubagentStop hooks* — the **only true enforcement layer**; can `decision:block` until exit 0. But "a completion gate, not a correctness gate"; every project must hand-author the script; no turnkey daemon-aware default.
- *Superpowers verification-before-completion skill* — advisory, accepts any "proving" command, doesn't detect boundary-mocking.
- *TDD Guard / Godmode* — enforce that tests exist/pass; that's exactly the "green unit subset" signal being falsely trusted.
- *Community deploy+curl Stop hook* — concrete enforcer but **HTTP-only**; "~50% false-success reduction" is a **single-developer, single-stack anecdote** (flag).
- *gstack `/qa`, `/canary`, `/browse`, `/health`* (this env) — strong runtime verification but web/browser-centric, user-invoked, not a gate.
- *Runtime MCPs (Chrome DevTools, godot-ai, MCP Inspector)* — real hands on a runtime, but capabilities not policy; each scoped to one surface; Claude can still skip them.

**Concrete concept.** A "definition-of-done gate" shipping as **both** plugin/skill AND Stop-hook enforcer: auto-derives a persisted per-project verification recipe (build + service restart + migrations + real code-path exercise, multi-framework-aware), runs it as a **non-bypassable** completion gate that injects observed runtime evidence (logs, HTTP/CLI output, screenshots) back into the transcript, and additionally **static-checks the diff's tests for boundary-mocking and assertion-target mismatches**. Survives the "CLAUDE.md rules get ignored" failure because it is harness-enforced, not advisory. The test-trust-auditing piece is addressed by **nothing** today.

---

### #2 — Redundant file re-reads + unfiltered tool output burn tokens every turn (leverage 88, both)

**Problem.** No session-level file-read memory → same file re-read 3-5×/session (400-line file = 800+ wasted tokens); 1000+ line files pulled whole for one section. Separately, every verbose test run, unbounded log, or wide grep dumps verbatim into context (one case fed 108KB from `seq`) and is **re-billed every subsequent turn**.

**Why high-leverage.** Recurs on essentially every editing loop; cleanly addressed by a PreToolUse hook + index layer with documented 40-70% main-thread token reductions (community-sourced figure — flag). Compounds with the memory/compaction cluster.

**What exists & gaps.**
- *read-once hook* — closest match for exact-duplicate reads; blocks unchanged re-reads, shows diffs. **But** no large-file scoping, 20-min TTL heuristic (can't detect compaction), nothing for Bash/grep/test output.
- *Semantic Cache MCP* — covers both re-reads and large-file scoping (~98.5% claimed — flag), but **only if reads route through its MCP** (native Read bypasses it); no Bash/log coverage; can't detect compaction.
- *RTK (Rust Token Killer)* — handles Bash output (60-90% claim), but **explicitly not native Read/Grep/Glob**; shrinks first ingestion only.
- *PostToolUse rewrite hooks (DIY)* — native plumbing, ships no logic.
- *Native Read offset/limit + Bash truncation env vars* — manual/blunt; the AST "map mode" request (#34304) was **closed not planned**; re-ingestion bug (#12054) **remains open**.
- *prompt-caching plugin* — only discounts billing, doesn't reduce token count; can't touch Claude Code's internal sessions.

**Concrete concept.** One hook-based context-budget manager: (a) session-level read ledger keyed on path+content-hash to block/diff redundant native Reads; (b) AST/tree-sitter structural map for files over N lines (the closed #34304 capability); (c) PostToolUse output capping with smart summarization (not middle-truncation); (d) **prune/collapse stale large outputs from earlier turns so they stop being re-billed** — ideally synced to actual compaction rather than a fixed timer. No single drop-in covers reads + large-file scoping + Bash/log filtering together, and **nothing** solves re-billing.

---

### #3 — Agent runs irreversible destructive commands (leverage 86, both)

**Problem.** A small enumerable set causes permanent loss with no meaningful gate: `rm -rf` wiping a home dir, `git clean -fd` nuking gitignored files, `reset --hard` chosen where checkout/stash was safe. One documented Windows Git-Bash junction-traversal case cascaded `rm -rf` up and deleted a 165GB user profile (#36339). Several issues closed "not planned," pushing users to DIY hooks.

**Why high-leverage.** Maximal severity (irrecoverable), tiny enumerable command set = cleanest possible hook target. Medium frequency but the catastrophic tail + trivial solvability push leverage high. Local `/careful`/`/guard` skills prove the denylist-hook vehicle ships.

**What exists & gaps.** Native deny/ask rules (DIY, fragile patterns, evadable by flag-reorder/env-var indirection/wrappers); native bypassPermissions circuit-breaker (only literal root/home `rm`); native Bash sandboxing (boundary not intent — in-tree `rm -rf` fully permitted, no git-history protection); `/careful`+`/guard` (warn-and-override only, missing `git clean -fd`, no undo/substitution); third-party blocker kits (all block-or-warn, fragmented, evadable); safer-delete CLIs (`trash`/`safe-rm` — **not Claude-Code-aware**, no auto-rewrite, rm-only). **Common thread: every option is a block-or-prompt gate over an evadable regex; none make the op recoverable or substitute the safe equivalent** — and the gate fails exactly when a fatigued user clicks through (Anthropic's own ~93% approval rate, cited in the permission-fatigue finding).

**Concrete concept.** A recovery-first safety layer (skill + PreToolUse hook): `rm -rf`→move to `.claude-trash` + restore command; `reset --hard`→auto backup branch/reflog tag (or stash) first; `clean -fd`→snapshot untracked+gitignored to a timestamped archive (directly fixes #29179); `push --force`→require `--force-with-lease` + capture prior remote SHA. Harden the Windows junction case (#36339) by detecting NTFS junctions / rewriting to native `rmdir`. Add intent-detection flagging reset/clean chosen where checkout/stash fit. **On-by-default, no per-session re-invocation, no hand-authored patterns.**

---

### #4 — Pre-compaction checkpoint + cross-session persistent memory (leverage 84, both)

**Problem.** Three merged context-memory findings: auto-compaction silently drops load-bearing detail (~2.3 compactions/day); no reliable persistent memory across sessions (spawned a Mem0/claude-mem cottage industry); expensive research lost on compaction with no durable artifact. **Excludes** the compaction-threshold-scaling sub-issue (server-side, not skill/MCP-solvable).

**Why high-leverage.** High freq × high sev; solvable at the workflow + storage layer; proven demand (an entire third-party ecosystem already exists).

**What exists & gaps — and an important narrowing.** Cross-session amnesia is now **substantially addressed natively** by Auto memory (v2.1.59, Feb 26 2026: MEMORY.md auto-loads first 200 lines every session) plus mature claude-mem (~46K stars — flag, large number, single-source) and Mem0. **So a pure "persistent memory MCP" would be reinventing the wheel.** The genuinely open gap: **nothing — native or third-party — fires on the PreCompact event to deterministically snapshot the specific load-bearing state at the cliff** (active file, decision chain, in-session CLAUDE.md rules, research-in-progress) and re-inject via `SessionStart(source=compact)`. Native Auto memory is opportunistic/lossy (Claude decides what's worth keeping, not compaction-triggered); claude-mem/Mem0 capture at session-end or heuristically; `/rewind` is code-only; gstack `/context-save` is manual (fires only if invoked *before* a silent auto-compact). PreCompact/SessionStart hooks are primitives only — a build kit, not a solution.

**Concrete concept.** A dependency-free plugin (skill + PreCompact/SessionStart hooks) that on PreCompact deterministically writes a structured, append-only checkpoint (captured facts, not an LLM-lossy summary), re-injects the most recent checkpoint on `SessionStart(source=compact|resume)`, and writes research output as a permanent file. Packages the proven DIY pattern from #34556 into one maintained artifact, filling the only sub-issue the platform hasn't.

---

### #5 — Repeated-action / failure loops + premature abandonment, no autonomous recovery (leverage 80, both)

**Problem.** Three merged findings: infinite loops re-issuing the byte-identical failing command (or "let me continue" verbal loops) with no repeated-action detector; abandoning multi-step tasks after a subset and summarizing as done ("agentic laziness"); bimodal poor error recovery (gives up at first error, or thrashes the same broken approach). All burn the window or stall headless runs.

**Why high-leverage.** High freq × high sev; wastes whole context windows / kills unattended runs. Mostly mechanical (repetition hook + Stop-hook todo inspection). Scores just below the top tier because the pure **process-hang** variant needs an external supervisor a skill alone can't provide.

**What exists & gaps.** The **abandonment half is reasonably served**: native `/goal` (Haiku evaluator re-prompts past premature "done") and the official **ralph-wiggum** plugin both keep Claude working. **But neither has no-progress detection — they can actively amplify token burn while Claude re-issues a byte-identical failing command** (ralph bug #18646: doesn't reliably respect `--max-iterations`, can burn the whole usage window). The **repeated-action/failure-loop half is an open gap explicitly declined by Anthropic**: the dedicated loop-detector request (#4277) and the same-failing-command bug (#19699) were **both closed "not planned."** Gemini CLI ships a `LoopDetectionService` (prior art) but is a cautionary tale — many false positives on legitimate repetitive work — so a naive port is wrong.

**Concrete concept.** One plugin: (a) PreToolUse hook hashing tool+args **and comparing output** to detect N consecutive identical-*and*-unproductive attempts (output-aware to dodge the Gemini false-positive trap), injecting a forced-strategy-change directive or hard-halt; (b) Stop-hook no-progress detector (no file diff + no new passing test + no new tool output → abort/escalate); (c) bounded retry/escalation budget converting bimodal "give up vs thrash" into "try → try *different* → surface structured blocker," with sane built-in iteration/spend caps (fixing the ralph burn). Ship as both.

---

### #6 — MCP schemas + CLAUDE.md bloat the context window before work starts (leverage 78, **skill**)

**Problem.** Every connected server's full tool defs preload at session start (4 servers ~67K; configs hitting ~98.7K of 200K ≈ 49%) and CLAUDE.md is re-sent every turn (5K-token file = 5K/turn; over-long files get rules silently ignored past ~line 200). A fixed tax paid before the user types.

**Why high-leverage.** Every session/turn; fix is a bounded, measurable audit-and-trim.

**What exists & gaps — important narrowing.** The **MCP-schema half is now well-covered by native Tool Search** (auto-enabled >~10% of context; ~85-95% reduction; ~46.9% / 51K→8.5K figures are **vendor/community-sourced — flag**). `/context` + `/mcp` toggle are diagnostic/manual. **The genuinely open half is CLAUDE.md/memory**: still re-sent every turn with no native lazy-loading (SkillSearch #43816 and lazy-context #44536 **closed/stale**); the only prior art (token-optimizer) merely *measures/flags*, doesn't *fix*. Caveman skill targets output verbosity (orthogonal). Meta-MCP proxies overlap with Tool Search and add a failure point.

**Concrete concept.** A focused **skill** (not MCP — this is config/file surgery): (1) `/context`-style accounting attributing the real session-start + per-turn tax; (2) detect the silent CLAUDE.md failure modes (content past ~line 200, oversized, duplicated rules); (3) **automatically remediate** by splitting CLAUDE.md into a lean always-on core + @import/.claude/rules + skill-extracted detail, then re-measure to prove savings. Secondary: verify/enable `ENABLE_TOOL_SEARCH`, prune unused servers. Complements (doesn't duplicate) Tool Search — the CLAUDE.md side is the part Anthropic explicitly declined to automate.

---

### #7 — Windows/PowerShell second-class shell + breaks MCP server setup (leverage 74, **skill**) — *directly relevant to this user (Win 11 / PowerShell)*

**Problem.** On native Windows the agent emits POSIX/bash syntax (`&&`, `$(...)`, `/dev/null`, extglob) into PowerShell and fails to self-correct on "not recognized as a cmdlet," burning turns; bash-routed PowerShell gets `$`-vars pre-expanded and corrupted; and MCP servers configured the documented (POSIX) way silently never connect because `npx` resolves to `npx.cmd`, fixed only by the undocumented `cmd /c npx` wrapper.

**Why high-leverage.** High frequency for the large Windows base; high severity (thrashing + silently-broken MCP setup). Scoped, deterministic.

**What exists & gaps — important narrowing.** The **shell-execution half is now largely native**: the default-on PowerShell tool (`CLAUDE_CODE_USE_POWERSHELL_TOOL`, default-on for all Windows since v2.1.143) eliminates Git-Bash `$`-corruption and most POSIX leakage. **So a "teach PowerShell" skill is mostly redundant on current builds.** The genuinely open half is **MCP setup, which Anthropic explicitly declined to fix**: `npx` is never auto-wrapped with `cmd /c` (#9594 closed not planned); the CLI parser corrupts the `/c` flag into `C:/` or `/schedule` (#36808 closed not planned); cmdlet-not-recognized self-correction was declined (#28670 closed not planned); the official MCP docs don't even document the `cmd /c` requirement. PowerShell.MCP and DIY PreToolUse hooks don't touch the generic `npx` wiring.

**Concrete concept.** A **Windows-MCP-doctor skill** (optionally + a PreToolUse/SessionStart hook): detect native Windows + PowerShell-tool presence; scan `.claude.json`/`.mcp.json` for stdio servers whose `command` is a bare `npx`/`npm`/`uvx` that are listed-but-not-connected; rewrite to verified `cmd /c` form while sidestepping the `/c` corruption; verify the server actually connects; and as a fallback for users not yet on the PowerShell tool, recognize the cmdlet/extglob error signature and force a PowerShell-native retry. This detect-rewrite-verify capability **exists in no current skill, MCP, native feature, or third-party tool.**

---

### #8 — stdio MCP servers crash silently, never auto-reconnect; auth brittle (leverage 70, both)

**Problem.** stdio servers launch in a stripped env (no profile, reduced PATH) → generic "Failed to connect"; once dead mid-session they're **never retried** (unlike HTTP/SSE backoff), breaking headless runs; only some configured servers connect. Plus brittle OAuth (DCR-only insistence breaking enterprise IdPs/GitHub, opaque PAT-format errors, no clean non-interactive CI path).

**Why high-leverage.** High freq × high sev for serious MCP/headless/CI use. Scored lowest of the top tier because the most durable fix — a client-side supervisor that auto-restarts stdio servers — is a core-product change a skill/MCP can only partially substitute for.

**What exists & gaps.** Native `/doctor` (diagnostic-only, startup-only, useless headless); native env propagation (still stripped env, still ENOENT); native `/mcp` reconnect + remote backoff — **but stdio is explicitly excluded from the reconnect path** (#43177), and the asks for mid-session auto-reconnect (#43177, #36308) and a headless `claude mcp reconnect` CLI (#57207) are **all closed not-planned/duplicate**; native OAuth insists on DCR even with a pre-configured clientId (#26675 open). Third-party: mcp-remote (only DCR/OAuth slice), supergateway/mcp-proxy (only transport bridging), Peekaboo/mcp-stdio-wrapper (supervise within one server or dev smoke-test only), McPick/CCHub/Composio (config/hosted-auth only). **No single tool closes the loop for local stdio.**

**Concrete concept.** A drop-in stdio shim registered via `claude mcp add my-server -- npx reliable-mcp -- <real command>` doing all three at once: (1) launch the child through a login shell (inject profile/PATH/nvm/uvx) so env-stripping never causes "Failed to connect," with a clear diagnostic when the binary truly isn't found; (2) supervise with crash detection + exponential-backoff restart (Peekaboo-style, with caps) so it self-heals mid-session in headless/CI; (3) clean auth — pass-through static OAuth creds (no DCR), a non-interactive env-var/API-key CI path, and PAT-format pre-validation. Bundle as an installable plugin/skill (the open gap).

---

## 4. Honorable Mentions (did NOT make the top list)

**Excluded as not skill/MCP-solvable (server-side / core-product):**
- **Compaction threshold doesn't scale to 1M context** (vehicle: *neither*). The trigger is server-side config; a skill could only warn or trigger manual `/compact` earlier, not raise the cap. Deliberately carved out of opportunity #4.
- **Retry/auto-compact loops resend full context (50K-300K tokens/event)** (*neither*). A core-engine fix (context-hash dedup, resume-from-checkpoint). A March 2026 prompt-caching bug caused silent 10-20× inflation — also engine-side.
- **OAuth onboarding redirect loops; no first-class headless/SSH/Docker login** (*neither*). Mostly a core product fix (detect existing subscriber, device-code flow). A skill could at best automate the API-key fallback.
- **IDE extension rough edges (install ENOENT, default-profile-only, sandbox/base-URL ignored vs CLI)** (*neither*). Extension-host bugs and config-parity gaps; skills/MCP run inside the session and cannot patch installation.

**Excluded as already well-covered (don't reinvent):**
- **MCP tool-schema bloat** — native Tool Search ~85-95% reduction (the CLAUDE.md half survives as opportunity #6).
- **Cross-session amnesia** — native Auto memory + claude-mem + Mem0 (the PreCompact-checkpoint half survives as opportunity #4).
- **Premature task abandonment / agentic laziness** — native `/goal` + official ralph-wiggum (the loop/no-progress half survives as opportunity #5).

**Real but lower-leverage / more specialized (mostly skill-shaped, narrower blast radius):**
- **Permission-prompt fatigue → rubber-stamping** (~93% approval rate; *skill*). A `fewer-permission-prompts` skill already exists in this env. Genuine but partially mitigated by Anthropic's 2026 "auto mode." Overlaps the safety cluster.
- **settings.json allowlist patterns silently fail to match** (*skill*). A lint/normalize/simulate skill. Real footgun (redirections, env-var prefixes, mid-command wildcards, first-source-wins precedence) but narrower than the top eight.
- **Prompt injection from tool output / files / MCP responses** (*both*; high severity, CVE-2025-59536, CVE-2026-21852). High-stakes but a much larger, less-bounded build (gateway/proxy + egress allowlists); leverage diluted by scope and the fact that real isolation needs Docker/microVM. A `cso` skill exists for auditing.
- **Sandbox covers only Bash, leaving file tools + credentials exposed; denylist bypassable** (*both*). Real isolation needs a container/microVM — heavier than a skill/MCP can fully deliver.
- **Hallucinated/outdated APIs** (*mcp*). Well-served by Context7-style doc-injection MCPs already; folds into opportunity #1's downstream effects.
- **Multi-agent orchestration cluster** (parallelism-is-an-illusion, lossy subagent handoff, near-zero subagent observability, non-deterministic control flow, 10-concurrent cap + cost blowups, ad-hoc result aggregation). Collectively high-frequency and real, but **fragmented across six findings** with no single clean lever; several depend on missing primitives (per-subagent IDs in hooks/OTEL — #7881, #14784, #16424) that only Anthropic can add. Best future candidate cluster, but lower per-issue leverage than the top eight, so none ranked individually.
- **Model selection (Opus/Sonnet/Haiku) is manual and expensive to get wrong**; **quota burns faster than expected with no real-time cost attribution** (*skill* / *both*). Real cost pain, but routing and metering are advisory/observability plays with lower correctness leverage.
- **MCP tool-name >64-char failures, namespacing convention mismatches, version/protocol drift** (*skill*). Real but niche audit-skill targets.
- **Hooks fail silently with confusing exit-code semantics** (*skill*); **config sprawl across 5 settings locations, first-source-wins** (*skill*). Both genuine DX papercuts; a hook-scaffolding skill and a `config explain` skill would help, but blast radius is smaller than the top eight.

---

## 5. Recommended Next Step for a "Decide Later" Choice

*(Three candidate directions, ranked. This is a research deliverable — these are options to weigh, not a recommendation to start building.)*

1. **Definition-of-done completion gate (opportunity #1, leverage 94).**
   *Why start here:* highest frequency × severity, the cleanest enforcement mechanic (Stop-hook block on non-zero exit), and the only direction where the *advisory* alternatives have already empirically failed (rules get ignored) — so a harness-enforced gate is the rare case where "both" is genuinely required rather than nice-to-have. It also indirectly suppresses regressions and hallucinated-API shipping.

2. **Session context-budget manager (opportunity #2, leverage 88).**
   *Why start here:* lowest-controversy, most-measurable win — it fires on every editing loop, the mechanics are pure PreToolUse/PostToolUse hooks, and it owns a real unclaimed gap (re-billing stale output every turn) rather than competing with a strong native feature. Fast to prototype, easy to A/B on token counts.

3. **Recovery-first destructive-command safety layer (opportunity #3, leverage 86).**
   *Why start here:* maximal severity over a tiny enumerable command set, and the differentiator (undo/snapshot-before-destroy vs. yet another dialog) is genuinely unserved — every existing tool is a block-or-prompt gate. Smallest, most self-contained scope of the three, and the local `/careful`/`/guard` skills prove the vehicle ships.

*Note on confidence:* directions are ranked on the inputs' leverage scores plus the cleanliness of the "remaining opportunity." Several supporting numbers are single-source anecdotes (flagged in §1 and §3); a real go/no-go should independently verify the rework-rate, token-reduction, and false-success-reduction claims before committing.
