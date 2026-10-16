# VibeBridge Project Memory

## P0 — Cross-conversation local-agent continuity (highest priority; added 2026-10-16)

**The local Mac agent connection must survive new ChatGPT conversations.** A new thread must not silently lose the ability to request authorized Mac operations through the VibeBridge bridge. This is the product's first-priority acceptance criterion because requiring the user to relay Terminal output defeats the product.

- On every new ChatGPT conversation, detect the extension-to-agent heartbeat and report the actual connection state from live diagnostics; never infer connectivity from remembered summaries or GitHub access.
- If connected, ChatGPT must be able to invoke the existing authenticated local-agent command/run interface, receive stdout/stderr and exit status, and continue the fix/test loop without user copy/paste.
- If the extension is connected but the chat cannot access the bridge action, treat that as a bridge integration/permissions/registration failure to investigate—not as an acceptable limitation and not as proof the Mac agent is offline.
- Persist a minimal, fresh handoff for every project and conversation: last executed action and exact result, local and remote HEAD, dirty status, extension manifest version, live loaded-tab version/heartbeat, tests with evidence, unresolved issues, and the single next action. Do not claim actions were executed if they were only proposed.
- Add an end-to-end new-thread acceptance test: open a fresh ChatGPT conversation, automatically discover the already-running local agent, run a harmless read-only diagnostic through the extension, receive the result directly in that conversation, then run the relevant test task without the user relaying output.
- Current limitation in this session: GitHub repository/workflow read and file-write tools are available, but no callable local-terminal/VibeBridge command tool or GitHub workflow-dispatch operation is exposed to this conversation. This is an observed tool-access gap, not evidence that the user's Mac agent is disconnected. Do not falsely report the live Mac steps complete; fix the product/tool handoff so the connection is available across threads.

## Eight active priorities (ordered)

1. **Persistent local-agent connection across new conversations** — expose and verify the existing VibeBridge command/result bridge in every new thread, including a harmless read-only end-to-end diagnostic.
2. **Composer safety** — never automatically rewrite or inject stale context into a user's visible draft; distinguish user-authorized command-result insertion from project-context pollution.
3. **Regression coverage** — test draft preservation, normal send, command-result insertion, no-match behavior, and cross-thread bridge continuity.
4. **Version and runtime verification** — compare GitHub HEAD, local checkout, installed manifest, popup build stamp, and live ChatGPT-tab heartbeat/version independently.
5. **Updater reliability** — verify polling, staged publication, rollback, and Chrome reload behavior against the actual Mac logs and files.
6. **Live Chrome end-to-end behavior** — verify ordinary messages and the authorized hands-off command/result loop in the real browser.
7. **Automatic project detection and low-friction development** — retain conversation-scoped project resolution and bounded concurrent Mac tasks.
8. **Project summary and handoff accuracy** — update every project's persistent summary after meaningful work with exact last action, result, revision, dirty state, versions, test evidence, known failures, and one next action. New conversations must validate the summary against live state.

## Current session handoff — 2026-10-16

- Latest verified repository HEAD before this update: `3f9fb2a8b3e77dd2a7142e56df764d6bdd25c386`; the three CI workflows passed on its parent `07559c6cc9ddeeb4d1a6c502f301462fe8fae51a`. The current summary edit itself must be committed and its resulting HEAD verified before treating it as latest.
- The screenshot's Chrome tab title `VibeBridge 0.2.95 Ready` is a conversation title, not reliable proof of extension version. Popup diagnostic showed `VibeBridge v0.2.96 · blocks 0 · commands 0`; live loaded content-script version still requires a fresh heartbeat/diagnostic.
- Composer sanitizer no-op and regression assertion were committed; the latest source changes have successful validation, unit-check workflow, and installer workflow reported for `07559c6`.
- Local Mac diagnostics, the local runner task, actual Chrome behavior, updater logs, and the fresh-thread command bridge remain **unverified** because no local runner/terminal invocation tool is exposed in this chat. Do not mark them done based on GitHub CI.
- Immediate next action: restore the missing local-agent invocation path across conversations, then run `test` and `diagnostics` on the trusted Mac runner and verify the live Chrome heartbeat.


## Current implementation status — 2026-10-16

- Extension target is `0.2.91` (automatic project detection/send; remove the literal `USER REQUEST` wrapper).
- Project resolution is conversation-scoped: explicit project names in the current message take priority, and short follow-ups use projects previously detected in that conversation. Do not use the global active project as a fallback for a different conversation.
- When a project matches, VibeBridge attaches background context automatically and sends the user's original text verbatim at the end. No choice buttons, extra confirmation step, `USER REQUEST:` label, or continuity wrapper should appear in the sent prompt. If no project matches, send the original text unchanged.
- Browser simulation and Mac runner tests are being rerun for this change. Do not claim the live Chrome path is verified until diagnostics show the loaded extension heartbeat/version and the actual behavior is checked.


- Extension target bumped to `0.2.90` in commit `c3f4a19`; follow-up test assertion updated in `94a7aee`.
- The `extension/chatgpt.js` context send flow no longer automatically attaches project context: it presents explicit **Send with project context** and **Send original only** choices. The ChatGPT page badge now prefixes the version with `v` and describes it as the loaded extension version.
- These remote commits are not yet proven deployed to the Mac or loaded by Chrome. Confirm on the Mac runner and wait for the browser heartbeat before claiming the user's visible version changed. The auto-send regression must be exercised in the real browser; unit checks alone are insufficient.
- Avoid appending continuity dumps into a user's message. Any pasted VibeBridge project-context wrapper is background context, not the user's actual request.


- Latest extension manifest target is `0.2.89`.
- Local diagnostics reported checkout revision `1e12a1b`, clean state, source manifest `0.2.88`, agent running on port `43127`, and `browserExtension.connected=false` with no reported version. This means the local source version is known, but the version loaded in Chrome is not yet verified.
- The browser heartbeat sends only extension version and ChatGPT host to the local agent. It does not send conversation content. It becomes visible only after the updated content script runs on a ChatGPT page.
- A source update or successful build does not reload an already-loaded unpacked Chrome extension. Do not claim automatic browser reload or end-to-end checkpoint success until verified on the actual Mac/Chrome session.

## Non-negotiable core product objective — read first

VibeBridge exists to remove the user from the command/output relay loop. ChatGPT should be able to make changes on the user's Mac, run commands and tests, receive stdout/stderr/exit codes automatically, diagnose failures, apply fixes, and rerun verification without asking the user to copy/paste Terminal commands, manually relay terminal output, or send screenshots. This is the product's central purpose, not an optional convenience feature.

Acceptance criteria for every development workflow:
1. ChatGPT can request a local operation through VibeBridge without the user typing a command.
2. VibeBridge executes it on the selected, allowed local project and returns complete bounded output plus exit status directly into the active ChatGPT conversation.
3. ChatGPT can use that result to decide the next operation and repeat the run/fix/test loop without the user manually forwarding results.
4. Concurrent independent tasks can run in parallel where safe, while resource-heavy work is bounded by CPU-aware scheduling.
5. The user is told to reload Chrome or approve an OS/browser permission only when that action genuinely cannot be automated; never present manual Terminal work or screenshot relay as the normal workflow.
6. Report a capability as working only after an end-to-end test proves the ChatGPT page → extension → local Mac agent → command execution → result returned to ChatGPT loop. Unit tests or a GitHub commit alone do not prove this.

Security constraints remain: authenticated loopback-only agent, allowed project roots, explicit setup consent, bounded timeouts/output, and safe handling of destructive commands. Do not weaken these safeguards to achieve hands-off operation. The target is an autonomous development loop within the user's authorized environment, not an unrestricted network-accessible shell.

## Mission
VibeBridge is a local-first Mac agent plus Chrome extension that carries relevant project context into ChatGPT development prompts. The goal is to let the user continue working naturally across new ChatGPT conversations without repeatedly explaining the repository, current state, decisions, or next steps.

## User workflow and preferences
- The user wants a step-by-step setup and then to continue by talking to ChatGPT normally.
- The user should not need to operate Terminal as part of normal use. ChatGPT should handle code changes and testing; VibeBridge should eventually install and verify its own updates through a safe, visible in-extension workflow. Until that exists, be explicit about any unavoidable local action and never pretend remote GitHub commits are installed locally.
- The user is comfortable reloading the Chrome extension when necessary, but wants Terminal use to be handled by ChatGPT through VibeBridge.
- Explain actions in plain language, one step at a time. Do not assume the user wants to inspect or write code manually.
- When the user says to continue, resume, update, fix, or says “okay” in a project conversation, use the attached project context to identify the intended project and next step.
- Do not state that a feature works just because it is planned. Verify the repository and runtime before claiming completion.

## Repository and environment
- GitHub repository: https://github.com/YamaHaroJ/VibeBridge
- Local macOS checkout: ~/VibeBridge
- Main branch: master
- Main branch: master; current extension and installer work is committed directly to master.
- Separate project: MacOptimizer. Do not mix its code or state with VibeBridge.
- Local agent: agent/server.py
- LaunchAgent installer: agent/install.sh
- Chrome extension: extension/
- Persistent local data: ~/Library/Application Support/VibeBridge/
- Local agent endpoint: http://127.0.0.1:43127

## Current architecture
1. The macOS Python HTTP agent binds to 127.0.0.1:43127 and authenticates requests with a bearer token.
2. Local project discovery is limited to configured roots: ~/Projects, ~/Developer, ~/VibeBridge, and ~/MacOptimizer. GitHub repository discovery uses the authenticated GitHub CLI account.
3. The Chrome extension content script extension/chatgpt.js detects ChatGPT send actions and asks extension/background.js to resolve project context.
4. extension/background.js calls the local agent and stores the selected project as activeProject/project in chrome.storage.local.
5. The agent attaches context assembled from project name/path, Git remote, branch, working-tree status, latest commit, README.md, this file (VIBEBRIDGE_CONTEXT.md), and saved local notes.
6. “Remember for this project: …” is intercepted and saved to the selected project's local notes.
7. The extension modifies the outgoing ChatGPT composer to prepend context. This depends on ChatGPT's webpage DOM and may need maintenance after UI changes.
8. Development branch work adds a user-approved local command relay: assistant responses can include a `vibebridge-run` fenced JSON block with a `command` string array. The extension presents a Run on my Mac button and confirmation dialog, calls the local agent's /run endpoint through the background worker, displays results, and can insert results into the ChatGPT composer for the user to send back. It is not automatic execution; the user explicitly approves each command.

## Implemented endpoints
- GET /health: local agent health check.
- GET /projects: discover allowed local projects.
- GET /context and POST /context: match a project and return assembled context.
- POST /remember: append a note to the project's local memory.
- POST /diagnostics: run limited Git diagnostics.
- POST /run: execute an argument-array command in an allowed project folder. This is powerful; keep the bearer token private and only authorize use on a machine/projects the user controls.

## Important behavior and limitations
- The extension popup has an on/off toggle for automatic project context attachment, a separate GitHub CLI/local-agent connection check, a link to ChatGPT Settings -> Apps/Connectors, a GitHub repository creation action, and a two-way project-switch test. These changes are committed but still need a real Mac runtime test.
- When a user explicitly asks in a ChatGPT message to create a repository with a name (for example, “create a new repository called SampleApp”), the content script asks for confirmation, defaults to private unless the request explicitly says public, creates the GitHub repository through authenticated gh, seeds README.md and VIBEBRIDGE_CONTEXT.md, and attempts to attach that context before sending the same message. This needs end-to-end validation on the user's Mac.
- GitHub CLI on the Mac and ChatGPT's GitHub App/connector are separate connections. The extension cannot inspect or change ChatGPT connector settings and cannot silently grant browser or operating-system permissions.
- A macOS DMG installer and Chrome extension ZIP are built by .github/workflows/macos-installer.yml. This is a guided, unsigned/not-notarized package; Chrome still requires the user to load the extension or a future Web Store release must be prepared.
- Project matching first checks local project names, then attempts to resolve explicit GitHub repository names/slugs using the authenticated GitHub CLI. Repositories not cloned locally are represented as github:owner/repo and should load README/context memory remotely. This behavior has not yet been end-to-end verified on the user's Mac.
- If multiple project names match, it reports ambiguity rather than choosing one.
- The extension does not read previous private ChatGPT conversation histories. Continuity comes from repository files, Git metadata, this memory document, and notes explicitly saved through VibeBridge.
- The command relay is committed on a development branch but has not been tested against the installed extension or local agent. Do not claim it works until tested.
- The command relay executes only after an explicit in-page confirmation, but commands can still modify or delete project files. Commands are executed in the selected project directory, not in a shell by default; do not pass shell interpreters or destructive commands without careful review.
- The context payload is capped. Keep this document concise, durable, and focused on decisions and state that are useful across sessions.
- Local notes are append-only plain text today. There is not yet a structured UI for editing, deleting, deduplicating, or prioritizing notes.
- Do not put bearer tokens, API keys, passwords, private customer data, or other secrets in this file or saved notes.

## Decisions to preserve
- Local-first design: the agent runs on the user's Mac and only listens on loopback.
- Keep project access restricted to explicitly configured roots.
- Persist durable decisions in project memory, while use Git status and the latest commit for changing implementation state.
- Use repository README for installation/user-facing documentation and this memory document for durable project-specific instructions and implementation status.
- Treat memory as supporting context, not proof: inspect current code and tests before changing or describing implementation.
- Normal workflow should not require the user to paste terminal commands. Prefer code changes through GitHub and a local agent update/restart triggered from the extension.

## Current checkpoint (2026-10-14)

- Latest GitHub work in this conversation: commit `e22b151` added authenticated filesystem endpoints to `agent/server.py`; commit `371ca02` added extension background-message forwarding for filesystem list/read/write/mkdir; commit `c4d3636` added `tests/test_filesystem_access.py`; commit `9db52a0` configured CI to run Python unit tests.
- These are repository commits only. They have NOT been installed or verified on the user's Mac. Do not claim end-to-end filesystem access or passing CI until the latest workflow run and live agent are checked.
- REQUIRED CONTINUITY BEHAVIOR: the goal is one continuously updated AI-written summary per conversation, where every new user message and assistant response is merged with the previous summary. Code now uses `extension/chatgpt.js` to detect newly rendered messages, `extension/background.js` to forward them, and `agent/server.py` to call the OpenAI Responses API and update `memory/AUTO_CHECKPOINT.md` with one evolving summary per conversation. The OpenAI API key is configured from the extension popup and stored locally at `~/Library/Application Support/VibeBridge/openai_api_key` with restrictive permissions; it is never committed to GitHub. The summary request preserves goals, decisions, verified implementation, blockers, and next steps and is intended to avoid raw transcript logging. Tests were added for summary merging and missing-key behavior. These are committed source changes only; local agent deployment, extension reload, API billing/key configuration, GitHub write behavior, and CI still require verification.
- Immediate priority: repair a safe, reliable local update/deploy path, then verify the installed agent and extension and filesystem API end to end. Build automatic per-message checkpointing of durable project state to `VIBEBRIDGE_CONTEXT.md` (or a separate checkpoint file), triggered on every new user and assistant message, with concise summaries, deduplication, and secret filtering. Until that exists, the assistant must explicitly commit a checkpoint after every VibeBridge-related message.
- Current limitation: this ChatGPT session cannot directly inspect or execute against the user's `127.0.0.1:43127` local agent. GitHub edits do not update the Mac by themselves.

## Next work, in priority order
1. Verify CI and end-to-end behavior for the continuously updated AI summary; get the updated local agent deployed, configure the OpenAI API key in the popup, and reload the extension.
2. Test that each user message and completed assistant response merges into the same conversation summary, and that GitHub write failures are surfaced.
3. Package and publish a signed/notarized macOS installer and Chrome Web Store extension to eliminate manual unpacked-extension loading.
4. Verify the local command relay end to end and improve project-context continuity/diagnostics.
5. Upgrade per-message excerpts to concise semantic summaries and improve memory management.

## Current known gaps
- End-to-end continuity and the new command relay have not been verified on the user's Mac.
- ChatGPT UI compatibility is fragile because the content script relies on DOM selectors and click interception.
- The local agent's /run endpoint can execute commands without per-command approval if called directly by a valid bearer-token client; do not expose it to the network or broaden project access.
- The extension command relay requires a visible user approval for every command and does not silently execute assistant-generated instructions.

## Continuity priority: read this first when resuming
This section is intentionally short and high priority: when a new ChatGPT conversation starts or context is near its limit, use the most recent discussion below to resume the user's last goal without making them repeat themselves. The extension already attaches this entire file as persistent project memory; its prompt now explicitly tells the assistant to prioritize this handoff section. Keep this summary current after meaningful project discussions, decisions, and completed changes. Preserve durable decisions and next steps, but do not claim repository changes are installed or runtime-tested unless verified.

## Most recent discussion (2026-10-14)
The user wants VibeBridge project continuity to survive conversation limits smoothly. We added a concise latest-discussion summary and updated the extension's context instructions to prioritize it when resuming work; next, test that remote context actually carries this section through and run the repository checks. The prior business direction remains: get the core product and distribution reliable first, then consider monetization through an external payment and licensing system.

## Most recent discussion (2026-10-15): minimal popup and setup model

The user wants the VibeBridge popup to be clean and uncluttered: no project/token inputs, diagnostics, update buttons, or testing tools in the normal popup. The popup has been redesigned in commits `bfde7b5` (HTML/theme) and `ffaeb1c` (behavior) as a compact light/dark adaptive power switch with a small local-agent status indicator. The switch stays disabled unless a saved token exists and the local agent health check succeeds. This is source code committed to GitHub only; it is not installed or runtime-tested on the user's Mac.

Important setup distinction: ChatGPT's GitHub connector is optional for VibeBridge's local project-context injection; it lets ChatGPT browse GitHub directly but does not authenticate the local agent. The local Mac setup still depends on the VibeBridge agent, its local bearer token being stored in extension storage, and GitHub CLI authentication for repository operations. The current installer prints the token but does not automatically place it in Chrome extension storage. Therefore a brand-new install could remain locked with this minimal popup unless a separate first-run setup/bootstrap flow is implemented. Next priority: remove this remaining setup friction safely (ideally an explicit one-time onboarding or secure native messaging/bootstrap mechanism), then validate existing-token startup and toggle behavior on the user's Mac. Do not expose the bearer token through an unauthenticated local HTTP endpoint.

## Latest UI work (2026-10-15)
- Popup styling is a compact, cool-feeling, light/dark adaptive card with a single power switch, concise connection statuses, and a one-time consent dialog.
- Commit `d66809c` adds a second subtle status line for GitHub. Commit `96e1f19` makes initialization check the local agent's `/health` endpoint and then `/github-projects`; the switch is enabled only if both succeed. GitHub status reports the repository count. This verifies the Mac's GitHub CLI authentication, not ChatGPT's separate GitHub connector.
- Critical incomplete setup dependency remains: secure one-time pairing to populate the extension's token storage is not implemented. The consent dialog does not itself pair; when no token exists it explains pairing is still needed. Do not claim first-run setup is complete or that this has been tested on the user's Mac.

## Token pairing investigation (2026-10-15)
- User wants the local agent token to be transferred automatically into extension storage after explicit approval, with no manual token entry.
- A first draft briefly added an unauthenticated `POST /pair` token response. It was rejected as unsafe because any installed Chrome extension could potentially request the bearer token; a client-supplied `approved: true` flag is not proof of user approval.
- Follow-up commits `955edf2` and `fc27bb3` disable that route and remove the extension's token-fetch behavior. Existing authenticated connections still work; brand-new installs still need secure pairing.
- Next design: use a trusted native approval step (for example a macOS confirmation dialog initiated by the local agent) or Chrome Native Messaging with a fixed, trusted extension ID. Do not expose the bearer token from an unauthenticated HTTP endpoint. Keep the UI low-friction and never ask the user to type the token.
- Latest pairing commits are source changes only and have not been tested on the user's Mac.

## Native token approval implementation (2026-10-15)
- User approved the flow: click Connect in extension, read consent explanation, confirm, then receive a native macOS approval dialog; on approval the token transfers automatically and the extension checks local agent + GitHub CLI.
- Commit `e2e39d3` adds a `/pair` handler in `agent/server.py`: it validates a Chrome extension origin, displays an AppleScript macOS approval dialog on first pairing, stores the approved extension origin with mode 0600, and returns the local token only after approval. Cancel returns an error without transferring the token. A different extension origin is rejected.
- Commit `968ed93` makes the popup request `/pair` after its consent checkbox and Connect button, save the returned token to Chrome local storage, then run the health/GitHub checks.
- This has been committed to GitHub but is not yet tested on macOS. Verify AppleScript quoting/dialog appearance, Chrome extension CORS preflight, LaunchAgent GUI permission, cancellation behavior, and CI results before calling it done. Token pairing should only be considered operational after a full fresh-install test.


## Test-build update workflow and diagnostics (2026-10-15)
- User wants the test product to update before any public stable release, with ChatGPT handling source changes and the user only reloading the unpacked extension after files arrive. No Terminal commands should be required in normal use.
- Commits on master added a collapsed “Maintenance & diagnostics” section in the popup with “Check for updates” and “View logs”. It calls authenticated local endpoints `POST /update` and `GET /update-status`. The status endpoint returns the local revision, current public master revision, updater LaunchAgent state, and tails of `update.log`, `updater.log`, `updater-error.log`, `agent.log`, and `agent-error.log` under `~/Library/Application Support/VibeBridge/`. These features are committed but are not installed or verified on the user's Mac.
- Installer hardening: `agent/install.sh` sets a restrictive umask, forces owner-only permissions on the local token, and no longer prints the token. The packaged installer now tells the user to use the extension's Connect flow and approve the native macOS prompt rather than copy a token from Terminal. It explicitly does not request Full Disk Access; only necessary setup, Chrome extension, and first-pairing approvals should be requested.
- Current updater still tracks public `master` hourly. It pauses when the local Git tree is dirty, validates Python/manifest/JavaScript, rolls back on validation failure, and restarts the agent. After extension files are fetched, Chrome still needs Reload. The test-versus-stable branch/release split is not fully implemented yet; a `development` branch was created but is not yet wired to a separate test updater.
- CI for the earlier commits through `f9ddf7f` passed validation; newest popup/logging commits still have queued/running workflows as of this checkpoint. Check current workflow status before claiming they pass.
- Important bootstrap limit: this session cannot connect to `127.0.0.1:43127` or read local Mac logs directly. Once the updated popup is on the Mac, the user can click Maintenance & diagnostics → View logs, then send the displayed log output back into ChatGPT. Do not claim local runtime verification before that.


## Extension build versioning rule (2026-10-15)
- Every change to the Chrome extension that should be tested on the user's Mac MUST bump `extension/manifest.json` version before asking the user to reload it. Never ask the user to reload an extension without providing the expected build number.
- The popup's `Extension build: vX.Y.Z · loaded` stamp is generated from Chrome's loaded manifest. Use it as the confirmation that the new extension files are loaded; GitHub commit success alone is not installation proof.
- Bump patch versions for ordinary test fixes (for example, 0.2.1 -> 0.2.2); reserve minor/major bumps for planned releases. Mention the expected version and relevant commit in the reload instruction.


## Remote Mac task queue (2026-10-15)
- Commit `6d2ea34` adds a background issue poller to `agent/server.py`. It polls the authenticated GitHub CLI account every 30 seconds for open issues in `YamaHaroJ/VibeBridge` titled exactly `VibeBridge task: validate`, `VibeBridge task: test`, or `VibeBridge task: diagnostics`.
- The poller only accepts issues authored by `YamaHaroJ`; issue bodies are never executed. It runs fixed argument-array commands, comments bounded results on the issue, then closes it. Arbitrary shell/command text is deliberately unsupported.
- Commit `6903f88` adds unit tests for the closed task enum and fixed-command execution.
- This is a source change. The existing Mac updater checks hourly, so the poller is not active until the updated `agent/server.py` reaches the Mac and the agent restarts. Once deployed, ChatGPT can request one of the predefined tasks by opening an issue with the exact title; the agent reports results as an issue comment.
- Remaining verification: run CI, verify `agent/server.py` compiles, run unit tests, and verify the Mac issue poller processes an owner-authored test task. Do not claim end-to-end Mac execution until the issue comment proves it.


## Native Messaging pairing and verification checkpoint (2026-10-15)
- The current source path uses Chrome Native Messaging for token bootstrap; the unauthenticated HTTP `/pair` token-transfer route is disabled (returns 410). The native host only handles `getToken`, and Chrome's host manifest restricts launch to the fixed extension ID.
- Commits `9457331`, `e2b6fdf`, `8ff8dea`, `9fe2dca`, `fb4926a`, `1f26b92`, `f016c12`, `90c750b`, `b8956ad`, `5922d31`, `b6f134c`, and `a4effdb` implement the host, popup integration, disabled HTTP pairing, installer registration, and regression tests. Extension manifest version is currently `0.2.20`.
- The README setup steps were stale and still instructed users to paste a clipboard token. It has now been updated to describe Native Messaging and native approval instead.
- Remote Mac task issues `#38` through `#43` were created to request validation/tests, but no runner comments had arrived at the last check. Do not claim these latest tests passed until a fresh runner comment confirms it.
- Next: commit this checkpoint, then request fresh Mac validation and test tasks. If the runner still does not process tasks, diagnose the local poller/agent deployment instead of repeatedly creating issues. Do not ask the user to run terminal commands unless the remote task path is demonstrably unavailable.


## Fast Mac runner update (2026-10-15)
- The remote Mac task worker was restored in commit `250522d`; it was missing from the newer `agent/server.py` despite prior project notes saying it existed. The current worker accepts only fixed owner-authored task titles and never executes issue body text.
- Commit `f942193` reduced task polling from 30 seconds to 2 seconds, shortened the GitHub issue-list timeout to 8 seconds, and bounded individual commands to 45 seconds. Commit `75fa6f7` adds a regression assertion for the two-second polling interval. Commit `8c49020` prioritizes the newest issues and scans only five at a time, avoiding stale queued tasks blocking new requests.
- Mac runner task issue `#49` passed the unit suite: 31 tests in 0.014 seconds. Issue `#50` passed Python compilation, manifest JSON, installer shell syntax, and all three JavaScript syntax checks. These are genuine Mac-runner results.
- The two-second interval is the polling target after the updated `agent/server.py` reaches the Mac and restarts. Detection latency is typically about 0–2 seconds plus GitHub CLI/API overhead; it is not a guarantee of end-to-end completion in two seconds. Task execution itself is separate.
- Remaining verification: confirm the running Mac agent has deployed the latest `8c49020` source and that issue `#49`/`#50` close after comments. The successful tasks show the runner was active on the checkout it tested, but do not by themselves prove it is running the newest polling optimization.


## Runner follow-up: queue polling regression found (2026-10-15)
- The runner's task poll interval is two seconds, and the updater is configured for five-second checks plus `RunAtLoad`.
- Diagnostics issues `#51` and `#52` and verification issues `#55` and `#56` remained unanswered. Investigation found the queue command added in `8c49020` used `gh issue list --order desc`, which may not be supported by the installed GitHub CLI. A failed list command is silently retried, explaining why task pickup can stop after that change.
- Fixed by removing `--order desc`, retaining supported `--sort created --limit 5`, and centralizing the command in `REMOTE_TASK_LIST_ARGS`. Commits: `b1a47d7`, `67900f8`; regression assertion in `e5a9050`.
- This is committed but not yet verified on the live Mac runner. Once the updater deploys this server version, queued tasks should resume. If no task results arrive, the installed updater/agent process itself needs manual restart or installation from the Mac, which cannot be triggered from GitHub alone.


## Runner queue starvation fix (2026-10-15)
- Found another concrete flaw: task polling scanned only the first five open issues. Since the queue had older unprocessed task issues, GitHub CLI ordering could keep returning stale issues and starve newer tasks indefinitely.
- Commit `a6e7506` changes the worker to scan up to 100 open issues per poll and select every unseen issue whose exact title, author, and task enum are allowed. Regression assertion is in `3a91b82`.
- Verification request `#58` opened after this fix.
- This fix prevents old queue entries from starving new requests, but still requires the Mac agent to deploy it. No response from issues `#51`-`#57` means the running Mac process is still not confirmed.


## Independent fast task reporter verified (2026-10-15)
- Added `.github/workflows/runner-report.yml` in commit `7579d5f`. GitHub Actions starts on newly opened/reopened issues titled exactly `VibeBridge task: test`, `VibeBridge task: validate`, or `VibeBridge task: diagnostics`; it runs fixed tasks on GitHub-hosted Ubuntu and posts a result comment with the workflow log link. It does not depend on the local Mac worker for reporting.
- Reporter test issue `#59` completed successfully via Actions run `38798365423`: **PASS**, unit suite. All 31 tests passed in 0.020 seconds. It posted a `VibeBridge fast reporter — PASS` comment to the issue. Link: https://github.com/YamaHaroJ/VibeBridge/actions/runs/38798365423
- Separate issue `#60` also received a Mac runner validation PASS, demonstrating the Mac worker has now responded again. The new GitHub Actions validation run was queued at check time and still needs final confirmation.
- Hosted reporter cannot inspect the actual Mac's local processes, but test/validation results now return through a separate workflow even if the Mac worker is offline.


## Local diagnostics endpoint (2026-10-15)
- Added authenticated `GET /diagnostics/local` to `agent/server.py`. It returns an allowlisted snapshot of the VibeBridge agent/updater LaunchAgent state, PIDs, OS version, timestamp, and the current request PID. It deliberately excludes unrelated process names, process arguments, environment variables, and logs.
- Added extension background message `VIBEBRIDGE_LOCAL_DIAGNOSTICS` to call the endpoint using the existing bearer token. Added focused unit tests in `tests/test_local_diagnostics.py` for service metadata filtering, non-macOS behavior, and launchctl timeout handling.
- Commits: `53d15ef` (agent endpoint), `4499b15` (extension bridge), `5ce88f7` (tests).
- The self-hosted GitHub Actions workflow was changed to manual dispatch only. Normal issue creation/pushes no longer queue jobs on a potentially offline self-hosted runner; hosted Actions remains responsible for source tests, while local service state is read by the local agent.
- Not yet verified on the user's installed Mac. Next: run hosted tests, confirm workflow dispatch syntax, then trigger local diagnostics through the extension once the latest agent source is deployed.


## Local process diagnostics verified (2026-10-15)
- The authenticated local endpoint `GET /diagnostics/local` is now used by the existing Mac task worker for the predefined `diagnostics` task. The task no longer dumps general process output or log contents into a GitHub issue.
- Mac task issue `#63` returned a live snapshot from macOS 15.8.2: `com.vibebridge.agent` was loaded/running (PID 79353, port 43127) and `com.vibebridge.updater` was loaded/running (PID 79366). This is real Mac-agent output, not a GitHub-hosted simulation. The result contains only VibeBridge service metadata.
- Mac task issue `#64` passed the full local suite: **35 tests passed** in 0.033 seconds. Hosted validation and checks also passed for commit `b6169d0`: [validation run](https://github.com/YamaHaroJ/VibeBridge/actions/runs/38799979481), [checks run](https://github.com/YamaHaroJ/VibeBridge/actions/runs/38799979467).
- The extension popup's existing **Maintenance & diagnostics → View logs** view now also requests the scoped service snapshot and displays the agent/updater state and PIDs. The popup source change is committed, but visual verification inside the running Chrome extension has not been performed in this session; Chrome must reload the updated extension files before the new display appears.
- The self-hosted Actions workflow is manual-dispatch-only so normal pushes/issues do not queue on an offline Mac runner. Local Mac process inspection is handled by the already-installed VibeBridge agent instead.
- Latest relevant commits: `53d15ef` agent endpoint; `4499b15` extension message bridge; `5ce88f7` endpoint tests; `a12c17c` popup display; `1254ec0` Mac diagnostics task; `0f41248` regression test; `b6169d0` output formatting fix.


## Chrome extension persistence (2026-10-15)
- The unpacked extension must be loaded from the stable path `~/VibeBridge/extension` (not `~/VibeBridge/agent`, a temporary download, or the installer package's temporary folder).
- Chrome normally retains a loaded unpacked extension across browser restarts as long as the same Chrome profile and folder path remain available. The updater replaces files within `~/VibeBridge/extension` and does not intentionally delete or relocate that directory. Reload the extension after updates.
- Updated `agent/install.sh` to verify required extension files, fail clearly if the payload is missing, print the stable path/persistence explanation, and reopen `chrome://extensions` after a successful health check.
- Chrome Web Store distribution is still the eventual way to make install/update behavior seamless for ordinary users; a local unpacked install is still a developer-mode setup.


## Popup connection-state fix (2026-10-15)
- Commit `0ff035d` changes `extension/popup.js` so a successful local `/health` check immediately marks VibeBridge connected, enables the main on/off switch, and hides “Connect this Mac.”
- GitHub CLI/repository lookup is now a separate status. If it fails, the popup retains the local connected state and explains that only GitHub repository features need sign-in; it no longer resets the main switch and asks to connect the Mac again.
- Validation run: https://github.com/YamaHaroJ/VibeBridge/actions/runs/38802894618 (running at checkpoint time).
- Local Chrome runtime verification is still required after the updater syncs the latest popup.js and the extension is reloaded.


## Version synchronization rule (2026-10-15)
- User explicitly requires every extension reload associated with a code change to include a version bump, so both sides can verify they are running the same build.
- Popup connection-state fix is versioned as **0.2.21** in `extension/manifest.json`; commit `74ad273`.
- Before asking the user to reload, check that the local updater has synced the commit and tell them the exact version expected in `chrome://extensions`. Do not imply a GitHub commit changes the local extension until it has synced.


## Connect-button loop fix (2026-10-15)
- User reports the Connect this Mac consent flow closes and returns to the same connect button without a confirmation.
- Commit `a2a51aa` changes pairing to always request a fresh token from Chrome Native Messaging (instead of reusing a potentially stale token), validates that token against `/health` before storing it, then immediately renders a visible connected state before refreshing the remaining status checks.
- Commit `80b0690` bumps the extension manifest to **0.2.22** in accordance with the user's requirement: every extension reload must have a version bump so both sides can confirm the loaded build.
- Must wait for updater to sync; user should see version 0.2.22 before reload. Then test Connect this Mac once. GitHub validation/runtime verification still pending at checkpoint.

## Current checkpoint (2026-10-16): context reliability fixes
- Current extension manifest version is **0.2.62**. Recent changes in this session touched only agent/tests, so no extension reload is required.
- Commit `57130c2` lets explicit `github:owner/repo` context load without first listing all repositories. Commit `e756e31` makes optional local-project checkpoint fetching bounded and non-blocking on timeout.
- Commit `1e6eb96` fixes the multi-project context header to use real line breaks. Commit `3d7a2be` centralizes formatting in `format_project_context_sections`.
- Commit `62336e4` reduces optional remote checkpoint retrieval timeout to 4 seconds and catches OS errors. Commit `1b7b8bc` adds a timeout fallback regression test; `11abe5f` fixes its mock decorators.
- Mac runner confirmed **52 tests passing** on the latest test run (issue #113). The intermediate run in issue #112 failed due to a duplicated mock decorator, which was fixed before #113.
- Next: continue hardening context resolution and checkpointing; do not claim local installation/runtime state beyond what the Mac task runner verifies. Avoid extension edits unless necessary; if any extension file changes, bump manifest version first.

## Context resilience update (2026-10-16)
- Commit `7eb72c1` adds `safe_git_output()` so optional local Git metadata commands that fail, are unavailable, or time out no longer abort project context assembly. Context still includes README and project memory.
- Commit `6036b92` adds a regression test for a Git metadata timeout. Mac runner test request #114 is pending.
- Latest confirmed Mac runner result before this change: 52 tests passed on issue #113. Do not assume #114 passed until its result arrives.

## Terminal relay verification work (2026-10-16)
- Live Mac diagnostics confirmed agent and updater are both running on macOS 15.8.2; agent PID 37480 was listening on port 43127 at the time of the check (issue #116).
- Fixed a real command-routing gap: the extension can store `github:owner/repo` as the selected project, but the agent's `/run` route previously treated that slug as a filesystem path. Commit `8c10e99` now resolves a selected GitHub slug to its matching local checkout and clearly rejects remote-only repositories for local terminal commands.
- Added regression coverage for local-slug mapping and remote-only rejection. Latest confirmed full suite: **55 tests passed** (issue #118) before the smoke-task addition.
- Commits `ea6a468` and `501bd32` add a fixed, harmless `terminal-smoke` task. It calls the actual authenticated local `/run` HTTP endpoint with a hard-coded Python print command and never exposes the bearer token. This is intended to verify the live Mac terminal relay rather than only unit-test it.
- Next: confirm tests pass on current master, then request `VibeBridge task: terminal-smoke`. This verifies the local agent HTTP execution route and project resolution, but not yet the Chrome content-script button end-to-end.
- No extension source changed; manifest stays **0.2.62**, so no Chrome reload is required for these agent changes.

## Live terminal smoke result (2026-10-16)
- Mac runner task #120 passed against the live local agent: authenticated `POST /run` executed the fixed harmless command `python3 -c "print('VibeBridge terminal relay OK')"` in `/Users/jay/VibeBridge` and returned the expected output.
- This proves the local agent's authenticated terminal execution endpoint is running and executes commands in the VibeBridge checkout. It does not yet prove the Chrome extension's injected **Run on my Mac** button completes the full UI-to-agent round trip.
- Unit suite passed 55 tests on issue #119 after a transient earlier run raced with the test-file update.
- Next: keep hardening the browser relay and add integration coverage for the extension message/HTTP bridge. Extension files were not changed; version remains **0.2.62**.

## Cross-chat handoff contract (2026-10-16)

The memory's purpose is not merely to describe the repository. A new ChatGPT chat must be able to resume the actual unfinished task without asking the user to reconstruct the previous thread.

Every assistant response to a VibeBridge-enriched user message must end with one `vibebridge-memory` fenced JSON block. The extension hides the block and sends it to the checkpoint endpoint. Each materially affected repository gets its own entry; never merge two repositories' goals or todos into one generic summary.

Required per-repository entry:
- `repository`: exact `owner/repo` slug.
- `summary`: durable goal, architecture, current state, verified behavior/evidence, and unverified behavior.
- `handoff`: the latest user request for this project (quote or faithfully preserve it), what the assistant actually changed/answered, test results and evidence, exact point to resume, next concrete action, and blockers.
- `todos`: prioritized unfinished actions only; remove completed work.
- `decisions`: durable choices and constraints that should survive new chats.
- `updated`: ISO-8601 timestamp.

Memory quality rules:
1. Keep the durable summary short and stable; put fast-changing progress and the latest user request in the handoff.
2. Record evidence precisely: commit SHA, workflow/test result, artifact/build version, and whether local Mac/Chrome runtime verification actually occurred.
3. Distinguish implemented, CI-tested, deployed, and live-runtime-verified. A GitHub commit does not mean it is installed locally.
4. When a message names multiple projects, create a separate handoff for each project actually affected. Do not let the active project overwrite explicit message mentions.
5. Preserve the user's working style: build/test first, concise updates, hands-off Terminal workflow, and do not ask them to repeat context already attached.
6. Never store secrets, private customer information, or raw conversation transcripts.

Latest implementation update: commit `895bc8c` adds an explicit per-response checkpoint instruction to the injected prompt, requiring the hidden block to include the most recent user request, actual assistant action/result, verification evidence, exact resume point, next action, blockers, separate project summaries, todos, and decisions. Commit `537f3b9` bumps the extension to `0.2.74`. These changes are source commits until CI passes and the extension is loaded/reloaded in Chrome. The checkpoint parser already stores the durable summary, latest handoff, living todos, and decisions in `memory/AUTO_CHECKPOINT.md` per repository/conversation.

## Rolling project-memory policy (2026-10-16)
- Treat memory as an evolving project log, not a static profile or a single last-message note. The project is being built across turns, so the recent build sequence is the most important operational context.
- Every checkpoint should merge forward: update the current project summary and latest handoff, maintain prioritized open todos and durable decisions, and preserve the latest eight dated project-building handoffs for that conversation.
- Give recent work priority in injected context: latest user request, what was changed, exact commit/build, tests and evidence, current blocker, and the next concrete action. Older milestones remain useful only when they explain architecture or why a decision was made.
- Keep project histories separate by repository and conversation. A message affecting multiple repositories must create a separate rolling handoff for each.
- The checkpoint writer now retains up to eight dated entries under `### Recent project-building history` when updating the same conversation section. This is committed in `3484283`, with regex/string escaping corrected in `a299544`. CI is still required to validate this parser change; it has not been verified on the user's Mac.

## Continuous context-injection bug (2026-10-16)
- User reports that after sending a message, the full VibeBridge project-context block was pasted into the ChatGPT composer after the next interaction, including the README and project memory. Treat as a high-priority, recurring composer mutation bug.
- Commit `e2c10b4` adds a defensive send guard: if the composer contains any VibeBridge wrapper/checkpoint instruction markers, the content script does not resolve or inject context again. This is a safeguard, not yet proof the user-visible bug is fully fixed.
- Commit `edfacb0` bumps the Chrome extension to `0.2.75`. Packaging/check CI is running as of this note. Still investigate the deeper path: the existing code builds one very long `addition` string containing project context plus internal checkpoint instructions and writes it directly into ChatGPT's visible composer. Confirm whether ChatGPT's React editor preserves/mutates that text on submit, and avoid showing any internal checkpoint instructions as user-facing prompt text if a safer approach is feasible.
- User expectation: fix the recurring bug directly, test the behavior, avoid long explanations, and never ask them to retype or debug manually unless a live local check is strictly necessary.

## Critical cross-project composer mutation incident (2026-10-16)
- User reported the full VibeBridge context/README/persistent-memory block was inserted into the ChatGPT message box without consent; user says this is recurring and affects project conversations broadly.
- Root cause confirmed in `extension/chatgpt.js`: the send handler called `writeComposer(composer, addition + original)`, intentionally prepending a large project-context string into ChatGPT's visible composer. The prior marker guard only stopped already-wrapped prompts from being wrapped a second time; it did not prevent the first unsolicited mutation.
- Emergency safeguard committed: `cab3451` removes the composer write from the context-resolve path and displays a notice that automatic injection is paused. Extension version bumped to `0.2.78` in `85b1e9a`.
- Regression test updated in `c7b94bd` to require context resolution while prohibiting `writeComposer(composer, addition + original)`. GitHub Actions Validate VibeBridge and VibeBridge checks passed on `c7b94bd`.
- Safety behavior is not yet loaded on the user's Mac. Must verify the packaged installer workflow and then ensure version 0.2.78 is synced/reloaded. Do not claim the live bug is fixed until the user tests two messages and confirms the composer remains unchanged.
- Next engineering task after the incident is contained: design an explicit, user-approved context delivery mechanism that does not silently rewrite the user's draft; until then, do not restore automatic visible-composer prepending. Cross-project context resolution can remain, but no hidden block should be written into ChatGPT's editor.

## Verification checkpoint (2026-10-16)

- Mac runner verified the installed local agent: 77/77 Python tests passed in 0.899s; authenticated `POST /run` smoke test passed in 0.13s; local diagnostics report the agent running on port 43127 and the updater LaunchAgent loaded. Results: issues #211, #212, #214, and #215.
- Commit `730dc282a3089e73302cf118c078ca107b9f3bfe` adds `node tests/test_extension_bridge.js` to CI because this integration test existed but was not being run by the workflow.
- Commit `10d9d2565592a581a6eac8defce2e939e5cef1b0` adds success and nonzero-exit tests for the background worker's authenticated `/run` relay. CI passed: the bridge test reported 8 scenarios passed and Python tests reported 77/77 passed.
- Commit `8a9c9817cd41fb282d16ae3c3fc6939334ab7e19` formalizes the non-negotiable goal: ChatGPT must run local tasks, receive results, diagnose, fix, and retest without the user manually relaying terminal output or screenshots.
- IMPORTANT LIMITATION: these checks prove the Mac agent route and background-worker contract, not the full live ChatGPT DOM → content script auto-run → Mac command → automatically submitted result loop. That browser-level end-to-end loop remains unverified. Automatic command execution requires the extension's `autoRunCommands` setting to be true; do not assume it is enabled. Next priority is a safe, automated end-to-end test of the real extension flow and a reliable status signal for the active hands-off setting, without asking the user to paste terminal output.

## Latest handoff (2026-10-16, after composer safety regression)

- Fixed the recurring context leak regression: extension/chatgpt.js now resolves and stores project context but does not write it into ChatGPT's visible composer. It displays that automatic injection is paused; the user's original draft is sent unchanged. Do not re-enable silent composer mutation.
- Updated tests/test_chatgpt_content_script.js to assert the prompt stays unchanged, and tests/test_auto_checkpoint.py to enforce the non-mutating contract.
- Bumped extension version to 0.2.82.
- Latest validation on commit a8e1cf640fd28223ad125598b51c535779db3b10: Validate VibeBridge and VibeBridge checks passed; macOS installer workflow was still running at last check. Earlier Chrome package workflow passed on 1b41f093ec15374b1f3bbfe10544a33bb65f7093.
- This is GitHub source, not proof the user's installed Chrome extension has updated. The real ChatGPT DOM → extension → Mac agent loop is still not end-to-end verified. Next: confirm installer packaging, then use the Mac runner to validate version 0.2.82 and safely test context resolution without composer changes. Do not ask the user to relay Terminal output.

## Latest verification handoff (2026-10-16)

- Commit da813fa adds both JavaScript regression suites to the predefined Mac `test` task. Commit ff5874a adds a unit test that ensures those suites remain part of the task.
- Mac runner on the deployed checkout: Python suite **78/78 passed**; `node tests/test_extension_bridge.js` **8 scenarios passed**; `node tests/test_chatgpt_content_script.js` **3 scenarios passed**. The expanded task took 2.45 seconds.
- Mac authenticated `/run` smoke test passed in 0.18 seconds and printed `VibeBridge terminal relay OK`. Diagnostics confirmed the agent is running on 127.0.0.1:43127 and the updater LaunchAgent is loaded.
- GitHub Validate VibeBridge and VibeBridge checks passed on ff5874a. The macOS installer workflow was still running at last check.
- The source safety fix remains: context resolution does not mutate the visible ChatGPT composer. Chrome extension manifest version is 0.2.82. Installed Chrome behavior and full browser-to-Mac auto-loop are still not proven; next priority is a safe user-approved context attach flow and real browser-level verification, without silently rewriting drafts.

## Latest handoff (2026-10-16, explicit context consent)

- Replaced automatic composer mutation with an explicit choice after context resolution: the user can click **Attach context & send** or **Send without context**. If the draft changes while loading, VibeBridge refuses to overwrite it. The context buttons are removed immediately after a choice to prevent duplicate sends.
- Added four DOM-simulation scenarios, including untouched draft/no-context send and opt-in context attachment. Mac runner on commit 47b5022 passed **78 Python tests**, **8 background bridge scenarios**, and **4 ChatGPT content-script scenarios**. `Validate VibeBridge`, `VibeBridge checks`, and Chrome extension packaging passed; macOS installer workflow was still running at last check.
- Extension version: **0.2.84**. Mac diagnostics previously confirmed agent running at 127.0.0.1:43127 and updater loaded; authenticated `/run` smoke test passed.
- Important: the DOM simulation is not a live Chrome end-to-end test. Verify the installed extension on the Mac before claiming the user-visible flow works. Continue preserving the user's draft and never silently inject context.


## Latest development checkpoint (2026-10-16): hands-off context sending

- User explicitly rejected all VibeBridge banners and context-choice buttons. The desired normal workflow is automatic: attach matched project context and send; if no project matches, send the original draft unchanged; if a recoverable context error occurs, preserve and send the original unchanged. Do not display success/transient notices. Do not remove confirmation for local terminal command execution or weaken the local agent's security boundaries.
- Implemented on `master`, extension version `0.2.87`. Commit `7cba699366406ec2a38edeb84b70de5d3a902ce4` is the latest source commit at this checkpoint. It makes the context-choice callback auto-attach, suppresses content-script notices, and updates the fallback to resolve the current ChatGPT send button. Regression tests now cover automatic context attachment, plain sends when no context matches, no banner, and safe error fallback.
- Verification: GitHub Actions for commit `7cba699366406ec2a38edeb84b70de5d3a902ce4` all passed: VibeBridge checks, Validate VibeBridge, and macOS installer package. Earlier test iterations failed on stale/incorrect test assertions, which were corrected before the passing commit. Do not infer that the extension source is installed locally solely from CI.
- Live Mac evidence on 2026-10-16: authenticated `/run` terminal smoke test passed (output: `VibeBridge terminal relay OK`); local diagnostics report `com.vibebridge.agent` loaded/running on port 43127 and `com.vibebridge.updater` loaded/running. A diagnostic request did not yet establish the local checkout HEAD, clean/dirty state, or installed extension version, so local source drift remains unverified.
- Next priority: use the running Mac updater/runner to confirm local checkout and extension version match `0.2.87`/commit `7cba699`, then run a real ChatGPT-tab send test proving matched context auto-attaches, no banner/buttons appear, and no-match sends the original unchanged. If local source is stale, use the existing safe updater rather than asking the user to run Terminal commands. After that, resume end-to-end verification of automatic conversation checkpointing and secure fresh-install pairing. Do not claim full end-to-end completion based only on unit tests or CI.


## Follow-up audit (2026-10-16): checkpointing gap confirmed

- Local Mac runner verification: authenticated `/run` smoke test passed with output `VibeBridge terminal relay OK`; `com.vibebridge.agent` and `com.vibebridge.updater` are both loaded/running. The local Mac regression run passed: 78 Python tests, 8 bridge scenarios, and 4 content-script DOM scenarios.
- GitHub CI and packaging passed for `7cba699366406ec2a38edeb84b70de5d3a902ce4`. A later project-memory-only update at `f76663716fc67d1fafa51dbfb9945c65629dc99e` also passed validation, checks, and macOS installer packaging.
- Important correction after inspecting current source: automatic rolling AI summaries of every user message and completed assistant response are **not implemented** in current `agent/server.py`, `extension/popup.js`, or `extension/popup.html`. The content script only saves explicitly authored `vibebridge-memory` assistant code blocks through `/checkpoint`. Prior checkpoint notes implying that an OpenAI Responses API key/configuration flow already exists are stale; the current popup has no OpenAI key configuration. Do not claim continuous per-message summaries work.
- Next priority after confirming local version drift: design and implement rolling conversation checkpoints safely. First establish how to configure/store the API key locally without exposing it, then capture only newly completed user/assistant messages, summarize/merge into one per-conversation project checkpoint, avoid duplicate writes during streaming, handle GitHub API failures, and add tests for secrets filtering, deduplication, bounded payloads, and concurrent updates. Never transmit full historical conversation text or secrets by default; do not show on-screen notices for ordinary success/failure because the user explicitly wants no banners.
- Latest known source version remains extension `0.2.87`; latest master before this note was `7cba699`. Local diagnostics confirmed service processes only; the exact installed extension version and local checkout SHA remain unverified. CI green is not proof of browser end-to-end behavior.


## Latest development checkpoint (2026-10-16): safer local version diagnostics

- Added allowlisted local checkout metadata to `GET /diagnostics/local`: short Git revision, a boolean dirty flag, and the version from `extension/manifest.json`. It intentionally does not return changed filenames, environment values, logs, or secrets. This makes it possible to compare the Mac checkout with GitHub without asking the user to inspect Terminal.
- Regression coverage updated for macOS/Linux behavior and metadata privacy. One CI pass initially exposed stale diagnostics test expectations; those tests were corrected, including escaped-newline fixtures.
- Verified Mac regression task on the updated checkout: 79 Python tests passed, 8 bridge integration scenarios passed, and 4 ChatGPT content-script DOM scenarios passed. Latest source commit for this change: `2b7202dd258faedcf871c554363aca6e98d78e8a`. GitHub checks are passing; validation/installer workflows were still running at the last poll.
- The actual rolling AI summary feature remains unimplemented. Current code only persists explicit `vibebridge-memory` blocks; do not claim every user/assistant message is merged automatically.
- Next implementation priority remains a real per-conversation rolling summary pipeline: secure local API-key configuration, capture only newly completed messages, deduplicate streaming updates, summarize/merge bounded context, and write the checkpoint through authenticated GitHub CLI with concurrency/conflict handling. Keep ordinary success/failure invisible in the ChatGPT page (no banners), and never send raw historical transcripts or secrets by default.


## Rolling checkpoint hardening (2026-10-16)

- Hardened the existing explicit checkpoint writer before attempting automatic transcript summarization: common bearer/API/GitHub tokens, password assignments, client secrets, and PEM private-key blocks are redacted before writing checkpoint sections or conversation handoff history to GitHub.
- Repeated identical handoffs are no longer appended repeatedly to the recent project-building history, reducing duplicate entries from streaming retries.
- Added regression coverage for credential redaction. Mac runner passed the full fixed test task on the current code: 80 Python tests, 8 bridge integration scenarios, and 4 content-script DOM scenarios.
- This does not yet create automatic rolling summaries from ordinary user/assistant messages. The next step is the explicit, opt-in summarization configuration and completed-turn capture pipeline; never transmit raw conversation history to a third-party API without a clear user opt-in.


## Opt-in automatic rolling checkpoint prototype (2026-10-16)

- Extension version bumped to `0.2.88`.
- Added an **off-by-default** popup toggle, `Automatic project memory`. Its enabled state is stored in Chrome extension storage; no API key is required because ChatGPT itself generates the compact checkpoint.
- When enabled and project context resolves, the outgoing prompt asks ChatGPT to append a bounded `vibebridge-memory` JSON block with durable summary, handoff, todos, and decisions. The existing content-script handler hides that block and forwards it to the authenticated local agent, which writes the checkpoint to the matched GitHub repository.
- The opt-in label warns that checkpoints are saved to GitHub; users should check repository visibility before enabling. No raw transcript is requested. Server-side credential redaction remains enabled.
- Tests now assert opt-in wiring and repository scoping. Mac runner: 81 Python tests passed, 8 bridge integration scenarios passed, and 4 content-script DOM scenarios passed. GitHub validation, VibeBridge checks, and Chrome extension packaging passed on commit `9f610b5dad75eff8a5c85b830f83259f8238d324`; macOS installer packaging was still running at last poll.
- This is the first opt-in prototype, not a verified live-browser end-to-end test. Next: test the setting and checkpoint lifecycle in Chrome, add duplicate/idempotency protection for repeated memory blocks, and verify deployment reports the new extension version.


## Verified handoff — 2026-10-16 23:xx UTC (composer-safety patch)

- Source of truth checked directly on GitHub `master`, not the local Mac checkout. Repository default branch is `master`.
- Before this patch, `extension/manifest.json` declared version `0.2.96`; the visible screenshot showed a tab title saying `VibeBridge 0.2.95 Ready` and a separate popup badge saying `VibeBridge v0.2.96 · blocks 0 · commands 0`. This indicates inconsistent UI/runtime version reporting; it does not prove which full content-script build was active in the tab.
- Confirmed in source: `extension/chatgpt.js` had `sanitizeBridgeComposer` write a cleaned string into the visible composer, and invoked it from the mutation observer and startup path. This contradicted the requirement not to mutate drafts automatically.
- Changed `extension/chatgpt.js` to make stale-composer sanitization a no-op and removed the observer/startup calls. The script no longer automatically rewrites a stale context wrapper out of the visible draft. This intentionally leaves any legacy wrapper for explicit user review rather than risking deletion of user text.
- Updated `tests/test_chatgpt_content_script.js` so the stale-wrapper scenario asserts the original draft remains unchanged.
- Commits pushed directly to `master`: source fix `894f11bd8f0a5f80a47e7f1fac4c520cf2a797ee`; regression test `70f54a4bf387cf0cedb1de69e6e65d4f824da19d`. These were two sequential commits; CI/test results have NOT yet been inspected after these commits. Do not claim tests pass until the workflow run confirms it.
- Still outstanding after this patch:
  1. Inspect and fix any remaining automatic composer writes, distinguishing explicit user-requested command-result insertion from project-context injection.
  2. Run and verify GitHub Actions regression, validation, extension packaging, and macOS installer workflows on the new HEAD.
  3. Verify the Mac runner's local checkout revision/dirty flag and installed manifest version against GitHub, then check actual Chrome tab content-script version. GitHub source state is not proof of local deployment.
  4. Audit updater's actual behavior and logs; updater source currently has a five-second polling adjustment and atomically publishes extension files, but live deployment is unverified.
  5. Inspect current live-send/no-match behavior in a real ChatGPT tab, with no banners or context-choice UI per the user's stated preference.
  6. Continue automatic project recognition and hands-off Mac operation only after safety and deployment checks.
  7. For every project, keep this handoff precise: last actual action/command, exact result, branch/commit/version, tests with evidence, known failures, and one next action. Never infer success from intended work or stale summaries.
- Important feature gap from the existing history remains: automatic rolling summaries of every completed user/assistant turn are not implemented. Current code saves only explicit `vibebridge-memory` blocks when that flow is triggered. Do not represent the full automatic summary pipeline as complete.


### Correction to the handoff interpretation — 2026-10-16

- The screenshot's Chrome tab text `VibeBridge 0.2.95 Ready` is the ChatGPT conversation title, not a reliable live extension-version indicator. The popup's bottom-right diagnostic explicitly showed `VibeBridge v0.2.96 · blocks 0 · commands 0`. Therefore the screenshot alone does NOT prove a 0.2.95/0.2.96 runtime mismatch. Use the popup's live browser-tab probe and `/diagnostics/local` allowlisted revision/version fields to verify the loaded content script and local checkout independently.


### Follow-up verification — 2026-10-16

- Latest GitHub HEAD at time of verification: `07559c6cc9ddeeb4d1a6c502f301462fe8fae51a`.
- GitHub Actions for that exact HEAD all completed successfully:
  - VibeBridge checks: run 38980079745 — success.
  - Validate VibeBridge: run 38980079772 — success.
  - macOS installer package: run 38980079705 — success.
- Confirmed source at HEAD has no call to `sanitizeBridgeComposer(initialComposer)`, no mutation-observer call to `sanitizeBridgeComposer(composer)`, and no `writeComposer(el, cleaned)` sanitizer write. The content script still has explicit command-result insertion paths for hands-off command execution and the user-clicked “insert result” action; those are distinct from automatic project-context injection and should remain covered by separate tests.
- `extension/manifest.json` is still version `0.2.96`. The screenshot's tab title is not proof of the loaded extension version; use the popup's own build stamp and live tab diagnostic.
- **Not yet verified and not to be claimed complete:** tests on the actual Mac runner after the latest commits; local checkout HEAD/dirty status; installed extension directory revision; actual loaded ChatGPT content-script revision; end-to-end ordinary-send and hands-off command loop; updater repair/reload behavior; and cross-conversation automatic persistence. This chat's available GitHub connector exposes source/workflow read and repository-write operations, but no terminal or workflow-dispatch operation to execute commands on the user's Mac. The workflow's issue reporter explicitly delegates local runner tasks rather than executing them.
- Exact next action when Mac execution is available: run the repository's `.github/workflows/mac-runner.yml` workflow with task `test`, then `diagnostics`; compare the runner's `git` revision and agent/updater logs with the GitHub HEAD above, reload the extension, and verify popup live-tab version before calling deployment fixed.
