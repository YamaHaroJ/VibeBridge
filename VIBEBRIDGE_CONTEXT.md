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

- Latest remote HEAD at handoff update: `930c7e9c514a1ab9eb3dfeac719734348fdde8b9`. Extension manifest version `0.2.99`.
- Mac runner test PASS on local revision `930c7e9`: 90 Python tests, 8 bridge integration scenarios, 5 ChatGPT content-script scenarios; all exit 0. Earlier `terminal-smoke` PASS (authenticated local `/run` returned `VibeBridge terminal relay OK`), `validate` PASS, and clean checkout.
- Updater fixed: removed stale hardcoded `0.2.98` assertion that was preventing automatic updates. Mac updater reports current HEAD deployed and clean working tree. Updater LaunchAgent is configured `RunAtLoad=true`, `StartInterval=5`; "not running" between invocations is expected.
- Heartbeat recovery improved: one-second retry loop after injecting `chatgpt.js`, plus a one-minute Chrome alarm to recover open ChatGPT tabs. Added extension version mismatch check that calls `chrome.runtime.reload()` when the local agent confirms the on-disk extension version is newer than the loaded version.
- **Outstanding deployment step:** latest diagnostics show disk version `0.2.99`, but the running Chrome extension still reports `0.2.98`. The old loaded extension cannot execute the newly added self-reload logic yet. Reload VibeBridge once in `chrome://extensions`; then verify diagnostics report loaded version `0.2.99` and heartbeat remains connected. After this bootstrap reload, the new periodic version check should handle subsequent version changes.
- Latest observed Mac diagnostics: agent running on port 43127; local checkout clean/current; one ChatGPT tab heartbeat connected but loaded version `0.2.98`. This is evidence of heartbeat from the old extension, not proof the new extension version is loaded.
- Issue #302 remains open until the fresh-thread acceptance test passes: new conversation reads this handoff, gets live diagnostics, runs authorized harmless local command and receives stdout/stderr/exit code, then continues without user relaying Terminal output. Do not mark the list complete before that test.
- Recent commits: `e6f9fa4` periodic recovery; `e787284` version `0.2.99` + alarms permission; `f73e22c` automatic reload on disk-version change; `6dc4610` reload regression test; `930c7e9` alarm contract test correction.

