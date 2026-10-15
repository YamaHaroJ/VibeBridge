# VibeBridge Privacy Policy

**Last updated:** October 15, 2026

VibeBridge is a local-first development helper consisting of a Chrome extension and a background agent on your Mac. This policy describes what the current source code is designed to access and transmit. Review the source and release notes for changes before installing an update.

## Information VibeBridge processes

- **Selected project context:** When you send a relevant prompt in ChatGPT, the extension can ask the local agent for context such as the selected project name and path, Git remote, branch, working-tree status, latest commit, README, `VIBEBRIDGE_CONTEXT.md`, and notes you saved for that project.
- **ChatGPT prompt content:** The extension inspects the current ChatGPT composer to determine whether project context should be attached. When context is attached, it becomes part of the prompt you choose to send to ChatGPT and is handled by ChatGPT under the terms and privacy settings of your ChatGPT account.
- **Project checkpoints:** When an assistant response contains a VibeBridge checkpoint block, the extension sends that block to the local agent. The agent can write the summary to `memory/AUTO_CHECKPOINT.md` in the explicitly named GitHub repository using the GitHub CLI available on your Mac. The checkpoint feature is intended to save concise summaries, not raw conversation transcripts. A summary may still contain information you included in the summary, so do not save secrets or personal data.
- **Local setup and authentication:** A random bearer token is stored at `~/Library/Application Support/VibeBridge/token` with restrictive file permissions. The extension stores the token and selected project in Chrome local extension storage. Keep the token private.
- **Optional GitHub features:** If you use repository discovery, cloning, or creation, VibeBridge invokes GitHub CLI on your Mac. Those operations use the GitHub account you authenticated locally and the permissions you granted to that account.
- **Optional command relay:** If included in your installed version, the local agent can run a command in an allowed project folder only after you approve the action in the extension. Commands can read or modify files accessible to your Mac account.

## Where information goes

The local agent binds to `127.0.0.1` and is designed to accept requests from this Mac, not to expose an HTTP service to your local network. VibeBridge does not operate a central VibeBridge server and does not include analytics or advertising code in the current source.

Information can leave your Mac when you choose to:
1. Send a prompt to ChatGPT, including any project context VibeBridge adds.
2. Save a checkpoint to GitHub, which writes the summary to the repository you identify.
3. Use GitHub CLI features that fetch, clone, or create repositories.

GitHub and ChatGPT process information under their own terms and privacy policies. A private GitHub repository is still accessible to people and applications authorized for that repository.

## Permissions

The extension requests Chrome storage and tab access and permission to communicate with the local agent at `127.0.0.1:43127`. Its content script runs on ChatGPT pages (`chatgpt.com` and `chat.openai.com`) to add context and recognize explicit checkpoint blocks. It does not need access to unrelated websites.

## Retention and deletion

- Local notes, logs, and the bearer token are stored under `~/Library/Application Support/VibeBridge/` until you remove them.
- Checkpoints written to GitHub remain in that repository and its Git history until you remove them according to GitHub's repository behavior and retention controls.
- Prompts and context sent to ChatGPT are subject to your ChatGPT account settings and OpenAI's policies.
- You can stop the background agent by unloading its LaunchAgent and remove local VibeBridge files to uninstall. Before deleting data, preserve any project notes or checkpoints you want to keep.

## Security

Keep the local bearer token private. The agent can perform sensitive actions within configured project roots, so only install VibeBridge from a source you trust. Do not store passwords, API keys, access tokens, private customer data, or other secrets in project memory or checkpoints. No software can guarantee absolute security; review the permissions and code before installing.

## Contact

For privacy questions or to report a concern, open an issue in the [VibeBridge GitHub repository](https://github.com/YamaHaroJ/VibeBridge/issues). Do not include tokens, credentials, or private project information in a public issue.
