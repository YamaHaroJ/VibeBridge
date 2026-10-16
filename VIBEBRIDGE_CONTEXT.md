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

- Latest verified remote HEAD: `dacaaf17f69f0128672b22fa8a5819e156b9863e`. Manifest version `0.2.98`.
- **Actual Mac runner results now verified:** task `test` PASS — 87 Python tests, 8 background bridge scenarios, 5 ChatGPT content-script scenarios; all exit 0. Task `terminal-smoke` PASS — authenticated `/run` returned `VibeBridge terminal relay OK`, exit code 0. Task `diagnostics` PASS — local checkout revision `dacaaf1`, clean working tree, agent running on port 43127, extension `0.2.98`, live ChatGPT tab heartbeat connected.
- **New issue:** local diagnostics reported `com.vibebridge.updater` loaded but `not running`. Investigate updater LaunchAgent scheduling/logs before considering update behavior fixed.
- Source fixes: `c9b9875` pings the existing ChatGPT content script before reinjecting on tab activation; `cb47a66` tests ping-first recovery. Mac runner `test` task now includes both JavaScript suites; `terminal-smoke` checks authenticated command round-trip without exposing the token.
- GitHub Actions `VibeBridge checks` and `Validate VibeBridge` passed at `dacaaf1`; macOS installer packaging was still running at last check.
- Next priority: diagnose why the updater is loaded but not running, then verify its launch/recovery and installed-source synchronization. The Mac command bridge is now confirmed callable through the owner-authored fixed-task queue; use fixed tasks and capture their actual reports rather than claiming work ran without evidence.

