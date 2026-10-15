# VibeBridge

A local Mac agent and Chrome extension prototype for AI-assisted development workflows.

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
5. Click **Test local agent**, then **Run Git diagnostics**.

## Scope and security

- The local service binds to `127.0.0.1`, not the network.
- Requests require a random bearer token.
- Commands run only within these configured roots: `~/Projects`, `~/Developer`, `~/VibeBridge`, and `~/MacOptimizer`.
- The local agent can execute commands without asking for per-command approval once you authorize its setup. Only use it on machines and projects you control. Keep the token private and stop the agent if you suspect it was exposed.
- This is a prototype. It does not yet inject into or directly control the active ChatGPT conversation. The Chrome extension is a local control panel; direct ChatGPT integration requires a separate implementation and compatibility testing.

## Stop or uninstall

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.vibebridge.agent.plist
```

Remove the LaunchAgent plist to prevent it from being loaded again. The token is stored in `~/Library/Application Support/VibeBridge/token`.
