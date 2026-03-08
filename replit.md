# Yakety Yak

A split-pane TUI tool that translates terminal/CLI output into plain-language explanations in real time. Built with Python's Textual framework and pty for real shell integration. Includes a landing page for downloads and supports both local AI (Ollama) and cloud AI (OpenAI). Features two switchable visual themes (Terminal and Glass). Hybrid monetization with Free + Pro ($7/month or $49/year) tiers.

## Architecture

- **Textual TUI** with split-pane layout (shell left, translations right)
- **Real shell** spawned via `pty` + `os.fork()` — no copy-paste needed
- **Four-tier translation**: local knowledge base → Pro cloud proxy → Ollama (local AI) → OpenAI (cloud AI)
- **Ollama integration**: auto-detects local Ollama with Qwen2.5-Coder model
- **Dual themes**: Terminal (hacker green) and Glass (glassmorphic purple/blue), toggled via Ctrl+S
- **Standalone app** built with PyInstaller — macOS .app bundle, Linux .desktop launcher
- **Landing page + API server** served by Flask with Stripe integration
- **Pro monetization**: Stripe subscriptions, license key validation, cloud AI proxy, usage tracking

## Key Files

- `app.py` — Main Textual TUI application (v1.3.0) with shell integration, Pro feature gating, activate/account commands, polished Rich markup welcome screen with box-drawing borders, Unicode section headers, and circled number icons
- `themes.py` — Theme CSS definitions (Terminal + Glass) with double borders, deep backgrounds, accent-colored inputs, bold separator bars; theme/license key persistence to `~/.yakety-yak/preferences.json`
- `translator.py` — Translation engine: local KB → Pro proxy → Ollama → OpenAI fallback chain; validates Pro keys
- `knowledge_base.py` — 507 commands, 52 error patterns, 6 output patterns; stores user KB at `~/.yakety-yak/` when bundled
- `terminal_knowledge_base.json` — User-editable JSON (auto-generated on first run)
- `build.py` — PyInstaller build script with --lite and --full modes; creates macOS .app, Linux .desktop, Ollama setup scripts
- `server.py` — Flask API server: landing page, Stripe checkout, webhook, cloud AI proxy, license validation, usage tracking
- `db.py` — PostgreSQL database layer: pro_users and api_usage tables, CRUD operations
- `stripe_client.py` — Stripe API client using Replit connectors for credential management
- `pro_api.py` — Cloud AI proxy logic, license key generation, rate limiting, GPT-5 translation
- `seed_products.py` — Script to create Stripe products/prices (run once)
- `tui_preview.py` — Interactive UI preview with animated demo content
- `templates/index.html` — Landing page with animated terminal demo, 3-tier pricing (Lite/Full/Pro), Stripe checkout
- `templates/success.html` — Post-checkout page with download buttons and email-based login instructions
- `templates/account.html` — Account management page with email lookup, usage stats, download links, and Stripe billing portal
- `static/style.css` — Landing page styles with Pro tier gold theme; cache buster at `?v=15`

## GitHub Repo

- **URL**: https://github.com/myiephero/Yaketyyak
- **Branch**: main

## Database Schema (PostgreSQL)

```sql
pro_users: id, email, stripe_customer_id, stripe_subscription_id, license_key, plan, status, created_at, updated_at
api_usage: id, license_key, tokens_used, endpoint, created_at
```

## API Endpoints

- `GET /` — Landing page
- `GET /success?session_id=X` — Post-checkout success page
- `GET /account` — Account management page
- `GET /api/config` — Stripe publishable key and price IDs
- `POST /api/checkout` — Create Stripe Checkout session (body: {plan, email})
- `GET /api/checkout/success?session_id=X` — Retrieve account info after payment
- `POST /api/webhook` — Stripe webhook for subscription events
- `POST /api/activate-by-email` — Activate Pro by email (body: {email}), rate-limited 5 attempts per 5 min
- `POST /api/validate-key` — Validate license key (body: {license_key})
- `POST /api/translate` — Cloud AI proxy for Pro users (body: {license_key, text, mode, language})
- `POST /api/usage` — Get usage stats (body: {license_key})
- `POST /api/portal` — Create Stripe billing portal session (body: {license_key})

## Stripe Integration

- Connected via Replit Stripe connector (OAuth)
- Products: "Yakety Yak Pro" with monthly ($7) and yearly ($49) prices
- Price IDs stored in env vars: STRIPE_MONTHLY_PRICE_ID, STRIPE_YEARLY_PRICE_ID
- License keys: YAK-XXXX-XXXX-XXXX-XXXX format (UUID-based)
- Rate limit: 500 cloud AI translations/month per Pro user

## Monetization Tiers

- **Lite (Free)**: 507-command knowledge base, 4 skill modes, Git Translator, 2 themes, 100% offline
- **Full + AI (Free)**: Everything in Lite + local Ollama AI, 8 languages, private
- **Pro ($7/mo or $49/yr)**: Cloud AI proxy (GPT-5, no API key needed), 500 translations/month, email-based login (or license key)

## Themes

- **Terminal**: Dark background (#0a0e17), green accents (#10b981), sharp borders — classic hacker aesthetic
- **Glass**: Deep indigo background (#0f0a2e), purple/blue accents (#6366f1, #a78bfa), rounded borders — iOS glassmorphic aesthetic
- Toggle with Ctrl+S, preference saved to `~/.yakety-yak/preferences.json`

## Translation Priority

1. **Local knowledge base** (instant, always works, 507 commands + 52 error patterns)
2. **Pro cloud proxy** (if Pro license key is active — GPT-5 via server-side proxy)
3. **Ollama** (local AI via qwen2.5-coder:1.5b, free, private, no internet)
4. **OpenAI cloud** (GPT-5 via Replit AI Integrations or OPENAI_API_KEY)

## Building

```bash
python build.py          # Both Lite and Full editions
python build.py --lite   # Lite only (~24 MB)
python build.py --full   # Full edition with Ollama setup scripts
```

## Workflows

- **Landing Page** — `python server.py` (port 5000) — serves landing page + API server

## In-App Commands

- `help` — Full help/instructions
- `activate <key>` — Activate Pro license key
- `account` — View Pro subscription status and usage
- `/git <url>` — Git Translator: analyze any GitHub repo
- `translate <command>` — Explain a command without running it
- `try` — List 25 beginner-friendly starter commands
- `try N` — Auto-run starter command N (1-25)

## Dependencies

- `textual` — TUI framework
- `pexpect` — Cross-platform pty utilities
- `openai` — AI API client (Ollama + OpenAI both use OpenAI-compatible API)
- `flask` — Landing page + API web server
- `stripe` — Stripe payment integration
- `psycopg2-binary` — PostgreSQL database driver
- `pyinstaller` — Build standalone executables (dev dependency)
