# Chrome Web Store Submission Checklist

This document prepares VibeBridge for store submission. It is not proof that the extension has been submitted, reviewed, or published.

## Draft listing

**Name:** VibeBridge

**Short description:** Keep your ChatGPT development projects in context with a local Mac agent.

**Detailed description:**

VibeBridge connects a Chrome extension to a local agent running on your Mac. When you work on ChatGPT coding and project tasks, it can attach context from your selected local project, including its README, saved project notes, Git metadata, and current working-tree status. It can save concise assistant-generated project checkpoints to a GitHub repository you specify. Optional GitHub tools can discover or clone repositories through the GitHub CLI installed on your Mac.

VibeBridge is local-first: the agent listens on your Mac's loopback interface. You control the selected project and whether context attachment is enabled. Context you send in a ChatGPT prompt is processed by ChatGPT. Checkpoints you choose to save are written to the target GitHub repository.

**Single purpose:** Attach relevant local project context to ChatGPT development prompts and maintain explicit project checkpoints.

## Permissions justification

- `storage`: save the local agent token, selected project, and enable/disable preference in Chrome extension storage.
- `tabs`: open the extension's setup and ChatGPT settings pages and support user-invoked browser workflows.
- `http://127.0.0.1:43127/*`: communicate with the local VibeBridge agent on the user's Mac.
- ChatGPT content script matches: `https://chatgpt.com/*` and `https://chat.openai.com/*`; required to detect prompts, attach project context, and recognize explicit checkpoint blocks.

## Required before submission

- [ ] Confirm the production extension package has no secrets or development-only files.
- [ ] Publish a publicly accessible privacy policy URL, using `PRIVACY.md` as the reviewed policy source.
- [ ] Create and verify store icon, screenshots, and any required promotional artwork.
- [ ] Confirm the current manifest and all requested permissions match actual behavior.
- [ ] Test clean installation, permission prompts, agent-not-running recovery, invalid token recovery, update behavior, and uninstall.
- [ ] Test checkpoint writes with public and private repositories and confirm failures are visible.
- [ ] Verify Chrome Web Store's current policies and data-use disclosures for content read from ChatGPT pages.
- [ ] Submit from the owner's Chrome Web Store developer account and complete any required one-time registration/payment.
- [ ] After publication, replace the unpacked-extension setup instructions with the official Web Store installation URL.

## Important limitations

- This is a draft listing, not an approved store listing.
- The repository's privacy policy Markdown file must be made available at a stable public URL appropriate for the store listing.
- Chrome Web Store publication requires account-owner action and review; repository code changes cannot publish the extension by themselves.
