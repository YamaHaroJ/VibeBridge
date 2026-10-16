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

- Latest remote HEAD: `257c1e62a0cf220aa5c6aa048462d6ce3b5efb43`. Manifest version remains `0.2.98`.
- Confirmed Mac runner results from local `~/VibeBridge`: `test` PASS (87 Python tests, 8 bridge integration scenarios, 5 content-script scenarios; all exit 0); `terminal-smoke` PASS (authenticated `/run` returned `VibeBridge terminal relay OK`); `validate` PASS (Python compile, manifest JSON, shell syntax, JavaScript syntax).
- Live Mac diagnostics at revision `c62f872`: agent running on port 43127, clean checkout, updater running, extension `0.2.98`, active ChatGPT heartbeat connected. Later snapshot reported no active tab; latest task is rechecking after updater diagnostics changes.
- Added safe updater schedule/status fields to local diagnostics (`b285a1a`). CI caught a stale test fixture; fixed it in `257c1e6`. Do not claim CI green until the newest checks and Mac task report complete.
- For fresh-thread continuity, this file is the handoff source; issue #302 contains acceptance criteria. New thread should first read current diagnostics and the latest handoff, not trust this snapshot as live state.
- Next: verify latest CI + Mac tests; rerun diagnostics after local updater sync to confirm schedule/log fields and ChatGPT heartbeat; continue issue #302's fresh-thread authenticated command/result loop and close remaining acceptance criteria only with evidence.

