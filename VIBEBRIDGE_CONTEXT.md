# VibeBridge Project Memory

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

