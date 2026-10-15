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
- Active development branch: fix/project-memory-selection
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

## Next work, in priority order
1. Verify the command relay end to end: reload extension, approve a harmless command such as `python3 --version` (or another safe read-only command) in the active project, confirm output appears, then insert and send the result back to ChatGPT.
2. Implement and verify safe self-update through the local agent so remote code changes can be pulled, validated, restarted, and reported without Terminal use. Preserve a rollback path and stop on uncommitted local changes.
3. Add automated tests and CI for project resolution, remote README/memory loading, ambiguous repository names, command payload validation, and failed lookups preserving the original message.
4. Verify automatic switching in real ChatGPT threads and prevent cross-project memory leakage.
5. Improve memory management: distinguish durable decisions from temporary notes, prevent duplicates, and allow stale notes to be corrected or removed.
6. Add clear status/diagnostics so the user can tell which project was selected and whether context was attached.

## Current known gaps
- End-to-end continuity and the new command relay have not been verified on the user's Mac.
- ChatGPT UI compatibility is fragile because the content script relies on DOM selectors and click interception.
- The local agent's /run endpoint can execute commands without per-command approval if called directly by a valid bearer-token client; do not expose it to the network or broaden project access.
- The extension command relay requires a visible user approval for every command and does not silently execute assistant-generated instructions.
