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

- Latest verified remote HEAD: `49852c75207200bcf1f589888d449b65ea868737`. Manifest version `0.2.98`.
- Mac runner task `test` PASS on `257c1e6`: 87 Python tests, 8 background bridge scenarios, 5 content-script scenarios; all exit 0. `terminal-smoke` PASS: authenticated `/run` returned `VibeBridge terminal relay OK`. `validate` PASS: Python compile, manifest JSON, shell syntax, JavaScript syntax.
- Automatic updater verified: local Mac advanced from `257c1e6` to `49852c7`, clean working tree, updater log says "Update complete". Updater plist has `RunAtLoad=true`, `StartInterval=5`; updater is normally idle between scheduled runs.
- CI on `49852c7`: `VibeBridge checks` PASS, `Validate VibeBridge` PASS; macOS installer package was still running at last check.
- Latest local diagnostics: agent running on port 43127, extension manifest `0.2.98`, checkout clean/current. Browser heartbeat had zero active ChatGPT tabs in the latest snapshot, so the live content-script heartbeat still needs verification with a ChatGPT tab open.
- Issue #302 remains open. Current thread has proven the local command queue works and task results return through GitHub issues. Still required before marking P0 complete: run diagnostics with ChatGPT open, verify the heartbeat, and verify a genuinely fresh ChatGPT conversation can automatically locate current handoff + invoke the authorized local task without user relaying output. Do not call the fix list complete until this cross-thread acceptance test passes.
- For a fresh thread: read this section and issue #302 first; check live local diagnostics before trusting this saved snapshot. Latest source changes include updater diagnostics `b285a1a`, diagnostics fixture fix `257c1e6`, and this handoff update `49852c7`.

