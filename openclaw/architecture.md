<!-- Last updated: 2026-03-07 -->
# OpenClaw Architecture

## Overview

OpenClaw is a personal AI assistant that runs on your own devices and responds across 20+ messaging channels (WhatsApp, Telegram, Slack, Discord, Signal, iMessage, etc.). The Gateway is the control plane; the product is the assistant. Built as a TypeScript ESM monorepo managed with pnpm.

## System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   Messaging Channels                      │
│  WhatsApp  Telegram  Slack  Discord  Signal  iMessage ... │
│  (core: src/<channel>)  (extensions: extensions/<name>)   │
└────────────────────────┬─────────────────────────────────┘
                         │ incoming messages
                         ▼
┌──────────────────────────────────────────────────────────┐
│                    Gateway Server                         │
│  src/gateway/server.ts  (Express HTTP + WebSocket)        │
│                                                           │
│  ┌─────────────┐  ┌──────────┐  ┌───────────────────┐   │
│  │  Routing     │  │  Auth &  │  │  Control UI       │   │
│  │  src/routing │  │  Pairing │  │  (web dashboard)  │   │
│  └──────┬──────┘  └──────────┘  └───────────────────┘   │
│         │                                                 │
│         ▼                                                 │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              Agent (Pi Embedded Runner)              │ │
│  │  src/agents/pi-embedded-runner.ts                   │ │
│  │                                                      │ │
│  │  - Model selection & auth profiles                   │ │
│  │  - Tool execution (bash, file ops, skills)           │ │
│  │  - Subagent spawning & lifecycle                     │ │
│  │  - Session management & history                      │ │
│  │  - Memory search (vector/keyword)                    │ │
│  │  - Sandbox isolation (Docker)                        │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐ │
│  │  Plugins  │  │  Hooks   │  │  Cron / Scheduling     │ │
│  │  src/     │  │  src/    │  │  src/cron              │ │
│  │  plugins  │  │  hooks   │  └────────────────────────┘ │
│  └──────────┘  └──────────┘                              │
└──────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌──────────────────────┐
│  LLM Providers  │          │  Native Apps         │
│  OpenAI, Claude │          │  apps/macos (Swift)  │
│  Gemini, Ollama │          │  apps/ios   (Swift)  │
│  Bedrock, etc.  │          │  apps/android (Kt)   │
└─────────────────┘          └──────────────────────┘
```

## Directory Structure

```
openclaw/
├── openclaw.mjs              # CLI entry point (Node version check → dist/entry.js)
├── src/                      # Core source (TypeScript ESM)
│   ├── entry.ts              # Main entry: CLI bootstrap → runCli()
│   ├── cli/                  # CLI wiring, commands, progress UI
│   ├── commands/             # CLI command implementations
│   ├── gateway/              # Gateway server (HTTP, WS, auth, chat, config)
│   ├── agents/               # Agent runtime (Pi embedded runner, tools, skills,
│   │                         #   model selection, subagents, sandbox, sessions)
│   ├── routing/              # Message routing & account resolution
│   ├── channels/             # Shared channel abstractions
│   ├── telegram/             # Core channel: Telegram
│   ├── discord/              # Core channel: Discord
│   ├── slack/                # Core channel: Slack
│   ├── signal/               # Core channel: Signal
│   ├── imessage/             # Core channel: iMessage
│   ├── web/                  # Core channel: WhatsApp Web
│   ├── line/                 # Core channel: LINE
│   ├── providers/            # LLM provider integrations
│   ├── memory/               # Memory system (vector search, keyword)
│   ├── media/                # Media pipeline (images, audio, video)
│   ├── media-understanding/  # Media analysis (vision, transcription)
│   ├── tts/                  # Text-to-speech
│   ├── hooks/                # Lifecycle hooks system
│   ├── plugins/              # Plugin loader & runtime
│   ├── plugin-sdk/           # Plugin SDK exports
│   ├── config/               # Configuration management
│   ├── secrets/              # Credential storage
│   ├── security/             # Security policies & sandboxing
│   ├── pairing/              # Device pairing
│   ├── sessions/             # Session persistence
│   ├── infra/                # Infrastructure utilities (env, fs, crypto)
│   ├── canvas-host/          # Live Canvas rendering (A2UI)
│   ├── browser/              # Browser automation (Playwright)
│   ├── daemon/               # System daemon (launchd/systemd)
│   ├── cron/                 # Scheduled tasks
│   ├── tui/                  # Terminal UI
│   ├── wizard/               # Onboarding wizard
│   ├── acp/                  # Agent Communication Protocol
│   ├── terminal/             # Terminal utilities (palette, table)
│   ├── i18n/                 # Internationalization
│   └── shared/               # Shared types & utilities
│
├── extensions/               # Channel & feature plugins (pnpm workspace packages)
│   ├── msteams/              # Microsoft Teams
│   ├── matrix/               # Matrix
│   ├── googlechat/           # Google Chat
│   ├── bluebubbles/          # BlueBubbles (iMessage bridge)
│   ├── voice-call/           # Voice calling
│   ├── memory-core/          # Memory plugin core
│   ├── memory-lancedb/       # LanceDB vector memory
│   ├── feishu/               # Feishu/Lark
│   ├── nostr/                # Nostr
│   ├── irc/                  # IRC
│   ├── twitch/               # Twitch
│   ├── zalo/                 # Zalo
│   └── ... (40 extensions)
│
├── apps/                     # Native companion apps
│   ├── macos/                # macOS app (SwiftUI, Sparkle updates)
│   ├── ios/                  # iOS app (SwiftUI)
│   ├── android/              # Android app (Kotlin)
│   └── shared/               # Shared native code (OpenClawKit)
│
├── packages/                 # Internal workspace packages
│   ├── clawdbot/             # Legacy bot package
│   └── moltbot/              # Legacy bot package
│
├── ui/                       # Web UI (Vite + Lit)
│   ├── src/                  # Web components
│   └── vite.config.ts
│
├── skills/                   # Agent skills (50+ tool integrations)
│   ├── github/               # GitHub operations
│   ├── slack/                # Slack tools
│   ├── discord/              # Discord tools
│   ├── coding-agent/         # Coding agent skill
│   ├── obsidian/             # Obsidian notes
│   ├── spotify-player/       # Spotify control
│   ├── weather/              # Weather lookup
│   └── ... (50+ skills)
│
├── docs/                     # Documentation (Mintlify-hosted)
├── scripts/                  # Build, release, and utility scripts
├── vendor/                   # Vendored dependencies
├── Dockerfile                # Production Docker image
├── docker-compose.yml        # Gateway + CLI containers
├── fly.toml                  # Fly.io deployment config
├── tsdown.config.ts          # Build config (tsdown bundler)
├── vitest.*.config.ts        # Test configs (unit, e2e, gateway, live, channels)
└── .agents/                  # Agent workflow configs & skills
```

## Core Components

### 1. Gateway (`src/gateway/`)
The central server process. Runs Express HTTP + WebSocket, manages channel connections, authenticates requests, routes messages to the agent, and serves the Control UI dashboard. Ports: 18789 (gateway), 18790 (bridge).

### 2. Agent Runtime (`src/agents/`)
The Pi embedded runner drives LLM conversations. Handles model selection with auth profile rotation/failover, tool execution (bash, file read/write, browser, skills), subagent spawning with depth limits, session history with compaction, and sandbox isolation via Docker.

### 3. Channel System
**Core channels** live in `src/<channel>/` (Telegram, Discord, Slack, Signal, iMessage, WhatsApp, LINE). **Extension channels** live in `extensions/<name>/` as separate pnpm workspace packages using the Plugin SDK (`src/plugin-sdk/`).

### 4. Skills (`skills/`)
50+ tool integrations the agent can invoke. Each skill is a directory with tool definitions. Skills are loaded at runtime and gated by configuration.

### 5. Native Apps (`apps/`)
Companion apps for macOS (SwiftUI + Sparkle), iOS (SwiftUI), and Android (Kotlin). Share code via `apps/shared/OpenClawKit`. Communicate with the gateway over its HTTP/WS API.

### 6. Web UI (`ui/`)
Lit-based web frontend served by the gateway's Control UI. Provides chat interface, configuration, and session management.

## Data Flow

```
User sends message (e.g., WhatsApp)
      │
      ▼
Channel adapter (src/web/ or extensions/whatsapp/)
      │
      ▼
Routing (src/routing/) → resolve account, session key
      │
      ▼
Gateway server → auth check → rate limit
      │
      ▼
Agent (pi-embedded-runner)
      ├── Select model + auth profile
      ├── Build system prompt (identity, skills, context)
      ├── LLM call → stream response
      ├── Tool calls (bash, files, skills, subagents)
      ├── Memory search if relevant
      └── Return response
      │
      ▼
Channel adapter → deliver reply to user
```
