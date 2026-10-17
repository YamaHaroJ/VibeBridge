# VibeBridge Project Memory

## What this is

A local Mac agent + Chrome extension that gives ChatGPT persistent, accurate
context about the user's local projects and GitHub repositories — delivered
fresh into every conversation instead of relying on ChatGPT's own memory,
which goes stale and drifts.

## Architecture (current, as of 2026-10-17)

- **Local agent** (`agent/server.py`, `127.0.0.1:43127`): builds live project
  context (README, git state, saved notes, `memory/AUTO_CHECKPOINT.md`
  handoffs) on request. Paired to the extension via Chrome Native Messaging.
- **Extension** (`extension/`): on a user's first message in a new ChatGPT
  thread, resolves the relevant project and sends a context primer as its
  own chat turn (never merged into the user's draft — that merge was the
  source of an earlier leaked-text bug). The primer includes the repository
  roster, the command/checkpoint protocol, and the resolved project's
  context. The user's actual message follows unmodified once that turn
  completes.
- **Checkpointing**: every several exchanges (or ~10 minutes), the extension
  asks the assistant to emit a `vibebridge-memory` block summarizing current
  state; this gets saved to `memory/AUTO_CHECKPOINT.md` on GitHub and
  resurfaces in the next conversation's primer. This is what makes a long
  back-and-forth survive into a new thread.
- **Command execution**: an assistant message containing a fenced
  ` ```vibebridge-run ` block gets a "Run on my Mac" control; results return
  to the same conversation.
- **Licensing** (`cloud-api/`): Stripe-backed subscription (VibeBridge Pro,
  $9/mo, 14-day trial), deployed on Vercel. Priming, checkpointing, and
  command execution are gated on an active license.

## What's verified

- 85 Python tests + 8 bridge-integration scenarios + 6 content-script
  scenarios pass (`tests/`).
- `cloud-api` checkout/webhook/license-status endpoints tested live against
  the real Stripe account.
- Live-tested against real chatgpt.com in a real browser (2026-10-17): a
  fresh conversation correctly receives the context primer as its own turn,
  a second fresh conversation correctly receives it too (fixed a storage-key
  collision that made only the *first* new thread ever get primed).

## Known gaps / next steps

- A full real end-to-end subscription (actual trial signup, not a local test
  bypass) hasn't been completed yet.
- Chrome Web Store listing needs to disclose subscription terms before
  re-submitting for review.
- If the assistant's response ever references "issue #302," "no callable
  command tool," or a GitHub-Issues-based task relay: that's stale. All of
  that was resolved and removed on 2026-10-16/17. Do not re-investigate it.

## Do not reintroduce

- The GitHub-Issues-as-task-queue relay (agent polling issues titled
  "VibeBridge task: X"). Removed deliberately — it was a workaround for a
  session that lacked direct tool access, not something the real product
  needs.
- The macOS installer disk-image/notarization pipeline. Removed deliberately
  — `agent/install.sh` is the real installer.
- Merging injected context into the user's visible composer draft. That
  caused the original leaked-text bug; context is delivered as a separate
  chat turn instead.
