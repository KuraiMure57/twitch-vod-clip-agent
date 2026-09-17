# Twitch TikTok Agent

Automated post-production and editing pipeline that ingests approved Twitch clips, crops them into vertical (9:16) format, generates synchronized dynamic subtitles, and prepares them for social media short-form platforms.

## 🎯 Project Purpose

The purpose of this project is to take horizontal clips approved by the user via Telegram and automate the entire video editing workflow required for modern short-form content (TikTok, YouTube Shorts, Instagram Reels).

> 🔗 **Input Trigger:** This repository operates as a passive reactive system. It remains idle until it receives a secure `repository_dispatch` token signal from the main analyzer (`twitch-vod-clip-agent`).

## 🔄 Core Workflow Diagram

```text
Repository Dispatch (Signal from twitch-vod-clip-agent)
        ↓
test.yml (GitHub Actions Trigger)
        ↓
Ingests approved.json Metadata & Video URL
        ↓
Smart Vertical Cropping (16:9 Horizontal → 9:16 Vertical)
        ↓
Subtitles Generation (Audio Transcription alignment)
        ↓
FFmpeg / Video Compositor Rendering
        ↓
Final MP4 Short Export
        ↓
Telegram Notification (Success/Failure logs and alerts)
```

## 🤖 Step-by-Step Pipeline Architecture

### 1. Webhook Automation Ingestion
The agent wakes up via GitHub Actions workflows upon receiving an external repository event. It parses the incoming payload, fetching the explicit VOD ID, timestamps, and metadata of the approved clip.

### 2. Video Processing & Re-framing
The script handles the conversion from landscape (16:9) to portrait (9:16) format. It applies smart positioning to ensure the core action or webcam frame remains centered, making it ready for mobile viewing.

### 3. Audio Extraction & Word-Level Alignment
The audio channel is processed to map exactly what words are spoken at what millisecond. This metadata is structured into renderable script lines.

### 4. Dynamic Subtitle Compositing
Burn-in subtitles are rendered directly onto the video track. The script controls:
* Font family, sizing, and geometric safety positioning.
* Timing matching the active voice layer.
* Error checking: If a processed video track or asset composition fails constraints (e.g., file sizes crossing communication boundaries), an integrated error hook is dispatched.

### 5. Smart Telegram Fallback Alerting
If any clip payload exceeds Telegram's standard multimedia delivery limits during execution logs review, the internal communication module automatically switches from streaming video commands (`sendVideo`) to flat document data streams (`sendDocument`), keeping you notified without crashing the automation runner.

## 📁 Project Architecture

```text
├── .github/workflows/
│   └── test.yml                   # Core pipeline automation dispatcher
├── src/
│   ├── telegram_review.py         # Media communication and Telegram handler
│   ├── video_processor.py         # Vertical conversion and cropping engine
│   └── subtitle_generator.py      # Subtitle synchronization and burned-in text core
└── requirements.txt               # Dependencies (Video manipulation, alignment tools)
```

## 🔐 Required GitHub Secrets

Configure the following secrets in this Repository Settings (`Settings -> Secrets and variables -> Actions`):

| Secret Name | Purpose |
| :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | HTTP API Token provided by `@BotFather` to report run status |
| `TELEGRAM_CHAT_ID` | Your unique numerical user ID from `@userinfobot` to receive alerts |

*(Note: Other access scopes use the tokens dispatched by the parent repository environment during cross-talk execution).*

## 🧪 Operational Status

**Status: OPERATIONAL WITH LIVE ERROR HOOKS**

The pipeline is integrated with your core notifier:
* Multi-platform Format Conversion Engine ➔ **Active** ✅
* Automated Dynamic Burn-In Subtitles ➔ **Active** ✅
* Smart File Handling & Bypassing (>50 MB Document Fallback) ➔ **Active** ✅
