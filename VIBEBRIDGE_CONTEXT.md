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

## Most recent discussion (2026-10-14)
The user was discussing preparing VibeBridge for Chrome Web Store publication, including the one-time developer registration fee and how a paid version could be introduced later. Current direction: get the core product and distribution working first, then add monetization through an external payment and licensing system rather than relying on Chrome Web Store built-in payments.
