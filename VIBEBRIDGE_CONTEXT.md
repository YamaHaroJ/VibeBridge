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

- Remote HEAD at start of this handoff update: `e6c97e9016766040259141a7f727193e2f423a58`; extension manifest version `0.2.99`. CI workflows `VibeBridge checks`, `Validate VibeBridge`, and `macOS installer package` all passed on `e6c97e9`.
- Latest Mac runner test task PASS on local revision `930c7e9`: 90 Python tests, 8 bridge integration scenarios, 5 content-script scenarios; each command exit 0. Authenticated `terminal-smoke` also PASS with output `VibeBridge terminal relay OK`.
- Mac diagnostics at 2026-10-16 23:33 UTC: agent running on port 43127; checkout clean at `930c7e9`, disk extension version `0.2.99`; browser extension heartbeat connected on `chatgpt.com` but still reports loaded version `0.2.98`. Updater is scheduled at 5 seconds and says revision `930c7e9` already deployed. GitHub-only handoff commits may not be picked up by Mac runner's updater yet.
- Implemented heartbeat injection retries, one-minute alarm recovery, and background version mismatch reload logic; CI passes. However, the currently loaded 0.2.98 extension cannot run the new mismatch-reload code until it is reloaded once.
- **Remaining manual bootstrap blocker:** reload VibeBridge in `chrome://extensions` once, then run diagnostics and confirm loaded version `0.2.99` with a fresh heartbeat. This environment has GitHub access and can queue predefined Mac runner tasks, but cannot click Chrome's local extension reload UI. Do not claim automatic update is end-to-end fixed until this is verified.
- Issue #302 remains OPEN. Local command round trip and Mac test are verified, but the exact fresh-thread continuity acceptance and current-version live Chrome verification remain incomplete. New conversation should read this file, check live diagnostics rather than trust this summary, run `terminal-smoke`/tests via the existing task bridge, and compare remote/local HEAD before continuing.
- Next action: bootstrap-reload extension once; then verify 0.2.99 live heartbeat, verify auto-reload on a later version bump, and run the new-thread continuity acceptance test.

