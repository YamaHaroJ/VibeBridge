# VibeBridge

A local Mac agent and Chrome extension that attaches local project context to ChatGPT prompts and keeps project notes across conversations.

## Install on your Mac

1. Clone the repository into `~/VibeBridge` (the installer currently expects that exact location):
   ```bash
   gh repo clone YamaHaroJ/VibeBridge ~/VibeBridge
   cd ~/VibeBridge
   bash agent/install.sh
   ```
2. Save the displayed bearer token somewhere private. Anyone with this token can execute commands in the configured project folders.
3. Open `chrome://extensions`, enable Developer mode, select **Load unpacked**, and choose `~/VibeBridge/extension`.
4. Open the VibeBridge extension, paste the token, enter a project path such as `~/VibeBridge`, and click **Save settings**.
5. Click **Check connection**, then **Find local projects** to discover repositories already on this Mac.
6. Click **Find GitHub repositories** to list repositories accessible to the authenticated GitHub CLI account, including older and newly created repositories. Select a repository and click **Clone selected repository to Mac** to clone it into `~/Projects`. Cloning requires GitHub CLI (`gh`) to be installed and signed in (`gh auth status`).
7. In ChatGPT, mention a discovered project by name. VibeBridge will attach its README, saved notes, Git remote, branch, latest commit, and working-tree status to relevant development prompts.
8. To save a durable fact, write `Remember for this project: ...` in a ChatGPT message after the correct project is active.
## Project memory

- `VIBEBRIDGE_CONTEXT.md` stores durable project goals, architecture, user workflow preferences, implementation status, decisions, limitations, and prioritized next steps. The local agent automatically includes it in project context when the file exists.
- `README.md` remains the install and usage guide. Git remote, branch, working-tree status, and latest commit are read live so memory does not need to duplicate changing Git state.
- `Remember for this project: ...` saves a local note under `~/Library/Application Support/VibeBridge/projects/`. These notes are separate from Git and are not uploaded to the repository.
- Do not save credentials, bearer tokens, passwords, or private customer data in project memory.
- Memory is contextual guidance, not proof that a feature is implemented. Verify current code and runtime behavior before relying on a statement.

## Scope and security

- The local service binds to `127.0.0.1`, not the network.
- Requests require a random bearer token.
- Commands run only within these configured roots: `~/Projects`, `~/Developer`, `~/VibeBridge`, and `~/MacOptimizer`.
- The local agent can execute commands without asking for per-command approval once you authorize its setup. Only use it on machines and projects you control. Keep the token private and stop the agent if you suspect it was exposed.
- The ChatGPT content script adds project context visibly to relevant outgoing prompts. ChatGPT's webpage changes over time, so this interaction may need maintenance.
- The extension does not read private history from previous ChatGPT conversations. It carries forward local README, Git metadata, and notes explicitly saved through VibeBridge.
- Context attachment is not a guarantee that every project name will be recognized; the project must be discoverable in one of the configured roots.

## Stop or uninstall

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.vibebridge.agent.plist
```

Remove the LaunchAgent plist to prevent it from being loaded again. The token is stored in `~/Library/Application Support/VibeBridge/token`.
