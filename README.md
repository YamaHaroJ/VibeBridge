# VibeBridge

A local Mac agent and Chrome extension that attaches local project context to ChatGPT prompts and keeps project notes across conversations.

## Install on your Mac

### Current setup

The installer fetches the latest public `master` code after you approve setup, installs the Mac background agent, configures hourly updates, and registers a Chrome Native Messaging host for secure token bootstrap. It does not require a GitHub login to install or update the public agent. Python 3.9+ and Git must be present. GitHub CLI is optional for installation but required for GitHub repository discovery/creation features.

**What you need to approve:** first, approve running the downloaded installer; then approve Chrome's extension setup. Because VibeBridge is not yet published in the Chrome Web Store, Chrome requires the manual Developer mode → Load unpacked step below. After Web Store publication, that becomes a standard **Add to Chrome** approval. No installer can bypass Chrome's security controls.

1. Clone the repository into `~/VibeBridge` (the installer currently expects that exact location):
   ```bash
   gh repo clone YamaHaroJ/VibeBridge ~/VibeBridge
   cd ~/VibeBridge
   bash agent/install.sh
   ```
2. Open `chrome://extensions`, enable Developer mode, select **Load unpacked**, and choose `~/VibeBridge/extension` (the installer opens the relevant pages/folder for you).
3. Open VibeBridge and use its Connect/onboarding flow. Approve the explanation in the extension and then approve the native macOS dialog. The extension requests the token through Chrome Native Messaging; it is not copied to the clipboard or typed manually.
4. After pairing, confirm the local agent and GitHub status indicators report connected.
6. Click **Find GitHub repositories** to list repositories accessible to the authenticated GitHub CLI account, including older and newly created repositories. Select a repository and click **Clone selected repository to Mac** to clone it into `~/Projects`. Cloning requires GitHub CLI (`gh`) to be installed and signed in (`gh auth status`).
7. In ChatGPT, mention a discovered project by name. VibeBridge will attach its README, saved notes, Git remote, branch, latest commit, and working-tree status to relevant development prompts.
8. To save a durable fact, write `Remember for this project: ...` in a ChatGPT message after the correct project is active.
## GitHub connections: two separate connections

- **Local VibeBridge GitHub access** uses GitHub CLI (`gh`) authenticated on your Mac. The extension connection check tests this separately.
- **ChatGPT GitHub access** is managed in ChatGPT Settings → Apps/Connectors. VibeBridge cannot read, enable, or grant permissions for a ChatGPT connector. Connect GitHub there if you want ChatGPT to browse repository contents directly. VibeBridge can still attach context through the local agent when the local GitHub CLI has access.
- The extension on/off switch pauses automatic context injection; it does not disable the background macOS agent.

## Packaged macOS installer

The macOS installer workflow builds a disk image and a separate Chrome extension ZIP on each push to `master`. Open the repository's **Actions** tab, select **macOS installer package**, open the latest successful run, and download the artifact named `VibeBridge-macOS-installer-...`. The disk image contains a guided installer and the local project files. The artifact is currently unsigned and not notarized, so macOS may show a warning. Do not bypass warnings unless you trust the source and have verified the repository.

The installer checks prerequisites, asks for approval before installing the local background agent, fetches the latest public code, enables hourly agent updates, registers the Native Messaging host, and opens the extension setup. It cannot silently enable Chrome Developer mode, install an unpublished extension, grant macOS permissions, or connect ChatGPT Apps. The user must approve browser permissions. The remaining distribution blockers for a normal one-click experience are Chrome Web Store publication and signed/notarized macOS packaging.

## Automatic project switching and repository creation

- In ChatGPT, explicitly say **"Switch to Autofill Insurance Extension"** or include an exact `owner/repository` slug. If an explicit switch fails, VibeBridge should display the reason instead of silently continuing with the previous project's context.
- To create a repository and start using it in the same message, say **"Create a new repository called SampleApp and build a simple starter app."** VibeBridge asks for confirmation, defaults the repository to private, creates README.md and VIBEBRIDGE_CONTEXT.md, and attaches the new project's context to that prompt. It requires your local GitHub CLI account to have repository-creation access.
- The extension popup also has **Create a new GitHub repository** and **Test repository switching** actions. The test checks both directions using the local agent; it does not create or modify a repository.
- Use the **Enable VibeBridge** switch to pause or resume automatic context attachment. This does not stop the local agent.

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

Remove the LaunchAgent plist to prevent it from being loaded again. The token is stored in `~/Library/Application Support/VibeBridge/token` and is delivered to the extension through the registered Native Messaging host after the pairing flow. Do not copy or share it.


## Public distribution and updates

- The public source of truth is this repository: https://github.com/YamaHaroJ/VibeBridge.
- Every push to `master` creates a preview installer artifact in GitHub Actions. These artifacts expire and are for testing, not permanent downloads.
- The new release workflow publishes a versioned macOS installer disk image, Chrome extension ZIP, and SHA-256 checksums to GitHub Releases when a version tag such as `v0.3.0` is pushed: https://github.com/YamaHaroJ/VibeBridge/releases.
- The installer registers a macOS LaunchAgent that checks the public GitHub `master` branch hourly, validates changes before restarting the local agent, and rolls back on validation failure. It does not require GitHub CLI authentication to update the public VibeBridge code.
- The local agent and source code update automatically, but an unpacked Chrome extension may still require a reload in `chrome://extensions` to activate changed extension files. True consumer installation requires Chrome Web Store publication; macOS distribution also needs signing/notarization. The installer cannot silently grant Chrome or ChatGPT permissions.


## Chrome Web Store preparation

- Privacy policy draft: [PRIVACY.md](PRIVACY.md)
- Draft store listing, permission justifications, and publication checklist: [docs/CHROME_WEB_STORE_LISTING.md](docs/CHROME_WEB_STORE_LISTING.md)

These documents prepare the submission but do not mean the extension has been published. The privacy policy needs a stable public URL and should be reviewed against the final release before submission.
