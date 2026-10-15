# VibeBridge Project Memory

## Mission
VibeBridge is a local-first Mac agent plus Chrome extension that carries relevant project context into ChatGPT development prompts. The goal is to let the user continue working naturally across new ChatGPT conversations without repeatedly explaining the repository, current state, decisions, or next steps.

## User workflow and preferences
- The user wants a step-by-step setup and then to continue by talking to ChatGPT normally.
- Avoid asking the user to repeatedly paste terminal commands. Prefer one carefully reviewed final terminal paste when local installation or restart is needed.
- Explain actions in plain language, one step at a time. Do not assume the user wants to inspect or write code manually.
- When the user says to continue, resume, update, fix, or says “okay” in a project conversation, use the attached project context to identify the intended project and next step.
- Do not state that a feature works just because it is planned. Verify the repository and runtime before claiming completion.

## Repository and environment
- GitHub repository: https://github.com/YamaHaroJ/VibeBridge
- Local macOS checkout: ~/VibeBridge
- Main branch: master
- Separate project: MacOptimizer. Do not mix its code or state with VibeBridge.
- Local agent: agent/server.py
- LaunchAgent installer: agent/install.sh
- Chrome extension: extension/
- Persistent local data: ~/Library/Application Support/VibeBridge/
- Local agent endpoint: http://127.0.0.1:43127
- Project notes are stored locally under Application Support/VibeBridge/projects/ as one Markdown file per resolved project path.

## Current architecture
1. The macOS Python HTTP agent binds to 127.0.0.1:43127.
2. Requests require a bearer token stored at ~/Library/Application Support/VibeBridge/token.
3. Project discovery is limited to configured roots: ~/Projects, ~/Developer, ~/VibeBridge, and ~/MacOptimizer.
4. The Chrome extension content script extension/chatgpt.js detects ChatGPT send actions and asks extension/background.js to resolve project context.
5. extension/background.js calls the local agent and stores the selected project as activeProject/project in chrome.storage.local.
6. The agent attaches context assembled from project name/path, Git remote, branch, working-tree status, latest commit, README.md, this file (VIBEBRIDGE_CONTEXT.md), and saved local notes.
7. “Remember for this project: …” is intercepted and saved to the selected project's local notes.
8. The extension currently modifies the outgoing ChatGPT composer to prepend context. This depends on ChatGPT's webpage DOM and may need maintenance after UI changes.

## Implemented endpoints
- GET /health: local agent health check.
- GET /projects: discover allowed local projects.
- GET /context and POST /context: match a project and return assembled context.
- POST /remember: append a note to the project's local memory.
- POST /diagnostics: run limited Git diagnostics.
- POST /run: execute an argument-array command in an allowed project folder. This is powerful; keep the bearer token private and only authorize use on a machine/projects the user controls.

## Important behavior and limitations
- Project matching uses names mentioned in the message; if there is no explicit name, it falls back to the active project.
- If multiple project names match, it reports ambiguity rather than choosing one.
- The extension does not read previous private ChatGPT conversation histories. Continuity comes from repository files, Git metadata, this memory document, and notes explicitly saved through VibeBridge.
- The context payload is capped. Keep this document concise, durable, and focused on decisions and state that are useful across sessions.
- Local notes are append-only plain text today. There is not yet a structured UI for editing, deleting, deduplicating, or prioritizing notes.
- Do not put bearer tokens, API keys, passwords, private customer data, or other secrets in this file or saved notes.

## Decisions to preserve
- Local-first design: the agent runs on the user's Mac and only listens on loopback.
- Keep project access restricted to explicitly configured roots.
- Persist durable decisions in project memory, while use Git status and the latest commit for changing implementation state.
- Use repository README for installation/user-facing documentation and this file for durable project-specific context and implementation decisions.
- Treat memory as supporting context, not proof: inspect current code and tests before changing or describing implementation.

## Next work, in priority order
1. Finish and verify the seamless ChatGPT continuity flow: identify the intended project, retain active-project state across new chats, and reliably attach the right context when the user says “continue,” “update,” or “okay.”
2. Improve memory quality: distinguish durable decisions from temporary observations; prevent repeated/near-duplicate notes; provide a way to correct or remove stale notes; and include the most relevant notes within the context budget.
3. Add a clear context-injection status/diagnostic so the user can tell which project was selected and whether memory was attached.
4. Keep GitHub-wide repository discovery as a core requirement: list old and new repositories accessible to the authenticated GitHub CLI account, distinguish repos already cloned locally, and let the user deliberately clone a selected repo into `~/Projects`.
5. Test the extension against current ChatGPT composer/send-button behavior and ensure a failed context lookup never loses or duplicates the user\u2019s original message.
6. Improve memory management after discovery and continuity are stable: provide a way to correct or remove stale notes and prioritize useful information within the context budget.
4. Test the extension against current ChatGPT composer/send-button behavior and ensure a failed context lookup never loses or duplicates the user's original message.
5. Update README and version metadata only after implementation and verification.

## Current known gaps
- End-to-end continuity has not yet been verified on the user's Mac after the latest repository state.
- ChatGPT UI compatibility is fragile because the content script relies on DOM selectors and click interception.
- Memory notes are currently free-form appended lines; memory organization and stale-note handling remain future work.
- The local agent's /run endpoint can execute commands without per-command approval after setup; do not broaden access or expose it to the network.
