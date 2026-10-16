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

- Latest remote HEAD: `046142f12a1261fafe9d66d4be9245c67b578746`. Manifest version `0.2.98`.
- Actual Mac task `test` PASS: 87 Python tests, 8 background bridge scenarios, 5 content-script scenarios; all exit 0. Repeated after the diagnostics update, same result.
- Actual Mac task `terminal-smoke` PASS: authenticated local `/run` returned `VibeBridge terminal relay OK`.
- Actual Mac task `validate` PASS: Python compilation, manifest JSON, installer shell syntax, and JavaScript syntax checks all exit 0.
- Live diagnostics at `c62f872`: agent loaded/running on port 43127, clean checkout, extension manifest `0.2.98`; at the later snapshot, browser heartbeat was disconnected with zero active ChatGPT tabs. This may mean ChatGPT was closed or its heartbeat stale; recheck with an active ChatGPT tab.
- Updater LaunchAgent reports loaded but idle/not running. This is not alone proof of failure for a `StartInterval` job. Added safe updater schedule and last-status metadata to diagnostics in `b285a1a`; added regression assertion in `046142f`. The Mac diagnostic task ran before those newest changes had reached the local checkout, so the new fields still need verification after updater sync.
- CI: `VibeBridge checks` passed at `b285a1a`; CI for `046142f` is running. Recheck before claiming final green.
- Next: verify updater plist schedule/log fields after local sync; with ChatGPT open, re-probe browser heartbeat. Continue issue #302 until a fresh thread can autonomously discover and use the local bridge.

