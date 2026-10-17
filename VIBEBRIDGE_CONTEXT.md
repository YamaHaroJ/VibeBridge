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


## Latest verification — 2026-10-16 23:50 UTC

- Remote master HEAD: `513aa6c1aac4a78cc3c89a0632a0c129865b6d5c`; manifest `0.2.99`. GitHub workflows `VibeBridge checks`, `Validate VibeBridge`, `macOS installer package`, and fast task reporter passed on this SHA.
- Mac runner task `test` completed PASS in 3.87s on issue #330: `python3 -m unittest discover -s tests -v` — 90 tests, exit 0; `node tests/test_extension_bridge.js` — 8 scenarios, exit 0; `node tests/test_chatgpt_content_script.js` — 5 scenarios, exit 0. Runner reports checkout `513aa6c1` and manifest `0.2.99`. This is fresh test-task evidence, not fresh live Chrome-version evidence.
- Requested new Mac diagnostics on issue #331; result has not arrived at handoff update time.
- Still not complete: current live loaded version/heartbeat, real Chrome command-result loop in a newly opened ChatGPT thread, and automatic reload after a subsequent version bump. Do not close issue #302 until those acceptance checks pass.
- Next action: retrieve issue #331 diagnostics; if live extension remains old, bootstrap-reload once in `chrome://extensions`, then verify loaded version `0.2.99` and run fresh-thread command/result acceptance.


## Live verification update — 2026-10-16 23:52 UTC

- Mac diagnostics task #331 PASS: local agent running on 127.0.0.1:43127; checkout `513aa6c` clean; disk manifest `0.2.99`; two live `chatgpt.com` tabs report extension `0.2.99` with fresh heartbeat at 23:50:25 UTC. Updater LaunchAgent is loaded/configured with RunAtLoad and 5-second interval; its process is normally idle between runs.
- Authenticated local terminal smoke task #332 PASS in 0.24s through the local `/run` route; output: `VibeBridge terminal relay OK`.
- Still unverified: command/result completion in a freshly opened ChatGPT conversation, composer safety in live Chrome, auto-reload after a future version bump, automatic project detection/concurrent task acceptance. Keep issue #302 open until these pass.
- Next action: run a dedicated fresh-thread command/result acceptance and composer-preservation E2E; then exercise updater with a controlled version bump and verify rollback/recovery evidence.


## Fresh diagnostics — 2026-10-17 00:00 UTC

- Mac diagnostics task #334 PASS. Agent is running on port 43127; local checkout `c3557cc` clean; manifest `0.2.99`; updater LaunchAgent loaded with RunAtLoad and 5-second interval.
- Important regression/blocker: diagnostics found **no connected ChatGPT browser tabs** at 00:00:11 UTC (connected=false, activeTabCount=0). The earlier two-tab heartbeat at 23:50 UTC is no longer current. Re-check after opening/reloading ChatGPT with VibeBridge enabled.
- Mac runner test task #335 PASS on local revision `c3557ccc177d57f7513763b752e42818e02d3107`, manifest `0.2.99`: 90 Python tests, 8 bridge integration scenarios, and 5 content-script scenarios all passed (exit 0). This verifies regression suites, not live Chrome continuity.
- Fresh-thread task #333 did not execute: only the generic GitHub reporter's “Task unknown” failure returned; this is not Mac acceptance evidence.
- Current tool limitation: this ChatGPT session has GitHub repository read/write tools but no callable local Mac command bridge or workflow-dispatch action. The Mac runner can report task results via issue comments, but I cannot click the local Chrome UI from here.
- Next action: open/reload a ChatGPT tab with VibeBridge enabled, then run diagnostics and the authenticated command/result acceptance in a fresh thread. Until that live heartbeat is restored, composer safety, fresh-thread continuity, updater bump/recovery, automatic project detection/concurrency, and BYOD specials remain unverified. Do not close issue #302.


## Composer safety patch — 2026-10-17 00:21 UTC

- Commit `dd aadb7` (full SHA `dd aadb7c534905ebc7e4e887be1cc0c03faa59a0`) updates `extension/chatgpt.js`: when a hands-off command finishes, if the ChatGPT composer already contains a draft, VibeBridge leaves it untouched and does not auto-send. The command result remains visible with the explicit insert control available.
- Mac regression test task #336 PASS on commit `dd aadb7c534905ebc7e4e887be1cc0c03faa59a0`: 90 Python tests, 8 bridge scenarios, and 5 content-script scenarios passed (exit 0). The suite does not yet prove the specific auto-command/non-empty-composer branch or live Chrome behavior.
- Latest master now includes a source change after local Mac checkout `c3557cc`; do not claim it is deployed or tested until the runner reports the new revision and tests pass.
- Live heartbeat remains unresolved based on last Mac diagnostics (zero connected tabs at 00:00:11 UTC). The #336 reporter confirmed tests on the new source commit but did not provide fresh Mac checkout/heartbeat data. Fresh-thread acceptance, a targeted regression test for auto-command with a non-empty composer, updater version bump/recovery, project detection/concurrency, and BYOD specials remain open. Issue #302 remains open.

## Draft-safety regression guard — 2026-10-17 00:24 UTC

- Added a targeted source-level regression guard in `tests/test_chatgpt_content_script.js` at commit `260d702ae7a246e739f627b15d4690ff365d187d`. It verifies that automatic command completion exposes the explicit insert control, checks for a non-empty composer, returns before writing the result, and only reaches auto-send after the write path. The mock DOM does not model the complete MutationObserver-generated command-card interaction, so this is a guard—not a substitute for a true command-card behavioral test.
- Queued standard Mac regression run in issue #337: https://github.com/YamaHaroJ/VibeBridge/issues/337. Await exact checkout SHA, manifest version, command exit codes, and live heartbeat result before claiming it passed.
- Next: inspect #337 result; improve this into a behavioral command-card test if harness supports it; restore live ChatGPT heartbeat and run fresh-thread command/result acceptance. Updater version-bump/recovery, project detection/concurrency, and BYOD specials are still open. Issue #302 remains open.

## Follow-up check — 2026-10-17 00:26 UTC

- Rechecked task #337: still open with zero comments, so no runner test result is available yet. Do not assume the Mac runner executed it.
- Confirmed the updater source is present at `agent/updater.py`; its staged deployment validates Python, manifest, and JavaScript syntax and preserves a backup for rollback on validation failure. These are source-level observations only; no live updater bump/recovery was run in this session.
- Searched repository issues for BYOD; no matching issue exists, so the phrase remains unidentified rather than silently treated as resolved.
- Highest blocking item remains direct live Mac bridge access from this ChatGPT conversation. GitHub-only changes cannot prove live heartbeat or fresh-thread command execution. Keep issue #302 open.

## Latest fix — 2026-10-17 00:28 UTC

- Commit `ec627bc952e0817c67f950cfecc55ec3910cb9fa`: corrected hands-off command text so it no longer promises the command result will automatically be sent when a pre-existing draft must be preserved.
- Commit `27722708b681ba33e210d412ce901a75a5cd6e89`: regression guard checks that the updated copy remains in place along with the existing draft-safety ordering assertions.
- Full regression task queued as issue #338: https://github.com/YamaHaroJ/VibeBridge/issues/338. No results yet.
- Current hard blocker unchanged: this ChatGPT session has GitHub repo access but no direct local Mac/Chrome command tool. Latest reported live heartbeat was disconnected; must not claim bridge acceptance until a real same-thread command round-trip and fresh-thread check run.
- #337 remains without comments/results. BYOD search returned no matching issue. Updater source has staged runtime validation and rollback on validation failure, but no live version-bump/recovery exercise is evidenced here.
- Next: inspect #338 runner results; add true behavior-level command-card test if harness supports it; continue updater/project-detection/concurrency work; retain #302 open.


## Verification update — 2026-10-17 after 00:28 UTC

- Verified remote master HEAD: `05b824cf931b43ff1b4296b13d50937ba7c3d505`; extension manifest remains `0.2.99`.
- GitHub Actions on that exact HEAD passed: VibeBridge checks run `38986519768`, Validate VibeBridge run `38986519843`, and macOS installer package run `38986519926`. The checks workflow ran the Python unittest suite and both Node regression scripts; all reported success.
- Attempted to clone and run the suite in this session, but the runtime could not resolve `github.com`; no local execution is claimed.
- These green GitHub-hosted checks do not satisfy issue #338's requested self-hosted Mac run, nor prove a live heartbeat, Chrome-tab version, updater rollback, or fresh-thread command/result round trip. The available connector has no workflow-dispatch or local-agent command action, so the Mac runner could not be started from this session.
- Remaining fix list: (1) restore/verify live heartbeat and same-thread/fresh-thread command-result bridge; (2) run the explicit Mac regression task and capture exact exit codes/heartbeat; (3) test updater version bump and recovery on Mac; (4) verify project detection and bounded concurrency live; (5) identify what “BYOD specials” refers to in the outstanding notes or remove it from the VibeBridge list if unrelated. Issue #302 remains open. Do not mark the list complete until the live acceptance criteria pass.
