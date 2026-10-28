# JUAPI / TokenRouter Integration Research

Research date: 2026-10-27

## Verified official documentation

1. [JUAPI first API request](https://www.juapi.net/docs/quickstart/first-api-request) states that the default Base URL is `https://www.juapi.net/v1`, keys are created in the user's console, and the exact model ID must be copied from the current token group. It sends `POST /v1/chat/completions` with `Authorization: Bearer ...` and a `model` field. The page explicitly warns not to guess model IDs and to avoid duplicating `/v1`.
2. [JUAPI token/API configuration](https://www.juapi.net/docs/quickstart/token-api-config) distinguishes protocol endpoints: OpenAI-compatible clients normally use `https://www.juapi.net/v1`; Claude Code normally uses the root `https://www.juapi.net` because the client appends `/v1/messages`; Chat Completions uses `/v1/chat/completions`; Responses uses `/v1/responses`; native Anthropic Messages uses `/v1/messages`. The document says model access, quota, concurrency, pricing, and protocol support depend on the selected token group.
3. [JUAPI Claude macOS/Linux guide](https://www.juapi.net/docs/quickstart/claude-mac-linux) says Claude Code needs the TokenRouter Base URL and API Key, and recommends retrieving the available model list rather than hard-coding an unverified model. It also says the Claude Base URL should follow the token/API configuration page and generally has no `/v1` suffix.
4. [JUAPI Codex macOS/Linux guide](https://www.juapi.net/docs/quickstart/codex-mac-linux) says Codex uses `~/.codex/config.toml` plus `~/.codex/auth.json`, with `base_url = "https://www.juapi.net/v1"`, `model_provider = "tokenrouter"`, and the API key in `auth.json`. It also warns that the exact model and access depend on the token group.
5. [JUAPI OpenAI-compatible chat API](https://www.juapi.net/docs/quickstart/page-1786638873756) documents `POST https://www.juapi.net/v1/chat/completions` and `POST https://www.juapi.net/v1/responses`; Chat Completions uses `messages`, while Responses uses `input`.
6. [JUAPI TokenRouter tutorial](https://www.juapi.net/docs/quickstart/tokenrouter) describes TokenRouter as the coding-tool relay and links to the manual configuration and platform-specific Codex/Claude guides. The manual page itself does not publish a stable model registry.

## Configuration decision

K.H.A.V.I.S. should store JUAPI as an OpenAI-compatible provider with Base URL `https://www.juapi.net/v1` for Codex and generic OpenAI-compatible calls. Claude Code uses the provider's Anthropic-compatible root URL `https://www.juapi.net` and the same JUAPI API key, with its selected model passed as the CLI model. The page must expose model strings as editable values and should not claim that `gemini4` or `kimi-k3.1-pro` is valid until the user's `/v1/models` response confirms those exact IDs for the token group.

The requested defaults are therefore recorded as requested aliases/configuration values:

- Claude Code requested model: `gemini4` (existing K.H.A.V.I.S. canonical alias may map this to `gemini-4-argon` only when the token group's model list confirms that mapping).
- Codex requested model: `kimi-k3.1-pro` (must be verified against JUAPI `/v1/models` before a real request).

No API key is stored in this research file.
