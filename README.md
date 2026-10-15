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
5. Click **Check connection**, then **Find local projects** once to discover projects.\n6. In ChatGPT, mention a discovered project by name. VibeBridge will attach its README, saved notes, Git remote, branch, latest commit, and working-tree status to relevant development prompts.\n7. To save a durable fact, write `Remember for this project: ...` in a ChatGPT message after the correct project is active.

## Scope and security

- The local service binds to `127.0.0.1`, not the network.
- Requests require a random bearer token.
- Commands run only within these configured roots: `~/Projects`, `~/Developer`, `~/VibeBridge`, and `~/MacOptimizer`.
- The local agent can execute commands without asking for per-command approval once you authorize its setup. Only use it on machines and projects you control. Keep the token private and stop the agent if you suspect it was exposed.
- The ChatGPT content script adds project context visibly to relevant outgoing prompts. ChatGPT's webpage changes over time, so this interaction may need maintenance.\n- The extension does not read private history from previous ChatGPT conversations. It carries forward local README, Git metadata, and notes explicitly saved through VibeBridge.\n- Context attachment is not a guarantee that every project name will be recognized; the project must be discoverable in one of the configured roots.

## Stop or uninstall

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.vibebridge.agent.plist
```

Remove the LaunchAgent plist to prevent it from being loaded again. The token is stored in `~/Library/Application Support/VibeBridge/token`.
