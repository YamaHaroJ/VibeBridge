# VibeBridge Project Memory Design

## Goal

Make development context survive ChatGPT conversation changes. A user should be able to start a fresh chat, mention a project by name, and have VibeBridge identify the project and provide concise, current context.

## Context sources

1. **README.md** — project purpose, setup, architecture, and usage.
2. **VIBEBRIDGE_CONTEXT.md** — persistent project-specific facts:
   - goals and intended users
   - decisions and constraints
   - user preferences for implementation
   - completed work and current status
   - known bugs and failed attempts
   - next steps
3. **Git metadata** — local path, remote repository, branch, latest commit, working-tree status.
4. **Current files** — inspect relevant code only when needed; never treat the README as proof that a feature exists.

## Request flow

1. Discover local projects and associate each project with its local path and Git remote.
2. Detect project names or repository URLs in the user's ChatGPT message.
3. If one project is a clear match, load its context. If several projects match, show the candidates rather than guessing.
4. Add a compact, visible project-context block to the request before it is submitted, or offer a clear one-click attach action. Do not silently alter messages without a user-visible indication.
5. After a task, summarize durable new decisions and status into that project's context file, then ask before committing or pushing those memory changes unless the user has enabled that behavior.

## Context block format

- Project name and local path
- Repository URL and active branch
- One-paragraph project summary
- Confirmed implementation status
- Durable decisions and constraints
- Recent work and unresolved issues
- Next step

## Safety and correctness

- Project matching must use discovered names, paths, and Git remotes, not just vague keyword similarity.
- Keep separate projects and their memories isolated.
- Label inferred facts as inferred; distinguish confirmed implementation from planned features.
- Never claim access to a previous ChatGPT conversation unless its information was explicitly saved in project memory or is available through an authorized connector.
- Do not include secrets, tokens, credentials, or private customer data in generated context.
- Keep context concise and refresh code/Git facts from the current checkout.
- ChatGPT page integration is a separate layer and must be tested against the changing ChatGPT interface. The local agent alone cannot read or control the active conversation.
