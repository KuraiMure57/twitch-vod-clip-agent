# Twitch VOD Clip Agent

Automated system for analyzing completed Twitch VODs, detecting interesting moments using AI, generating video clips, and sending them to Telegram for manual approval.

## 🎯 Project Purpose

The purpose of this project is to automatically review a completed Twitch VOD and identify high-intensity or engaging moments that could work well as clips or short-form content.

> ⚠️ **Scope Boundary:** This agent does **not** perform final vertical cropping, does **not** add subtitles, and does **not** publish to social networks. Those tasks are delegated automatically to a separate dedicated project (`twitch-tiktok-agent`) once a clip is approved.

## 🔄 Core Workflow Diagram

```text
/start (Telegram)
        ↓
bot.py (Render Listener)
        ↓
Discovers & Downloads Twitch VOD
        ↓
Whisper Transcription (Timestamped)
        ↓
Gemini AI Content Analysis
        ↓
Candidate Filtering & Selection
        ↓
FFmpeg Clip Generation (MP4)
        ↓
Interactive Telegram Approval (Buttons)
        ↓
[ User Approves Clip ]
        ↓
Generates approved.json Manifest
        ↓
Repository Dispatch (Triggers Project 2: twitch-tiktok-agent)
```

## 🤖 Step-by-Step Agent Architecture

### 1. Twitch Authentication & Discovery
Connects to the Twitch API using client credentials to discover and monitor the latest available VOD for the configured channel.

### 2. Complete VOD Download
Downloads the complete source stream locally via `yt-dlp` so the entire media file can be evaluated with precision.

### 3. Whisper Transcription
Transcribes the audio track of the complete VOD using OpenAI's Whisper model. This outputs detailed timestamped segments allowing specific moments to be located programmatically.

### 4. Gemini AI Analysis
Sends the structured transcription to Google Gemini to identify potentially engaging highlights. Gemini evaluates segments based on contextual factors:
* High-intensity gameplay & clutch situations
* Jump scares & loud reactions
* Comedic timing & funny statements
* Unexpected plot twists or events

The model scores each candidate and returns its start/end boundaries, category, suggested title, confidence level, and rationale.

### 5. Clip Generation
The approved timestamps are passed to FFmpeg to cut the source VOD into distinct, perfectly synchronized high-quality MP4 video clips.

### 6. Interactive Telegram Review
Every candidate clip is sent directly to your private Telegram chat. Each payload includes:
* The raw MP4 video clip
* AI-Suggested Title & Score (0-100)
* Category & Duration
* Contextual Reason for Selection
* **[ ✅ APPROVE ]** and **[ ❌ REJECT ]** inline buttons

The system handles file sizes intelligently: clips under 50 MB are sent as native video streams, while heavier files (up to 2 GB) seamlessly fallback to structured document uploads to bypass Telegram's standard limits.

### 7. Automated Hand-off (Project 2 Integration)
When a clip is manually approved via Telegram, its metadata is written into an `approved.json` manifest. The agent then sends a secure `repository_dispatch` signal across repositories to instantly wake up the **TikTok & Shorts Editing Pipeline (`twitch-tiktok-agent`)**.

## 📁 Project Architecture & File Output

```text
├── src/
│   ├── twitch_auth.py             # Twitch API authentication
│   ├── twitch_vods.py             # VOD tracking and scanning
│   ├── twitch_vod_downloader.py   # Stream chunk downloading
│   ├── whisper_transcriber.py     # Audio transcription engine
│   ├── gemini_analyzer.py         # AI core analytics
│   ├── candidate_filter.py        # Logic and evaluation rules
│   ├── clip_generator.py          # FFmpeg video cutter
│   └── telegram_approval.py       # Bot interaction & Webhook handler
└── data/
    ├── analysis/                  # Raw Gemini JSON evaluations
    ├── transcriptions/            # VOD Text transcriptions
    ├── filtered_candidates/       # Passed highlights manifest
    ├── clips/                     # Generated MP4 media files
    └── telegram_approved/         # Final selection manifests for Project 2
```

## 🔐 Required GitHub Secrets

Configure the following secrets in your Repository Settings (`Settings -> Secrets and variables -> Actions`):

| Secret Name | Purpose |
| :--- | :--- |
| `TWITCH_CLIENT_ID` | Twitch developer portal Client ID |
| `TWITCH_CLIENT_SECRET` | Twitch developer portal Client Secret |
| `GEMINI_API_KEY` | Google AI Studio access key for analysis |
| `TELEGRAM_BOT_TOKEN` | HTTP API Token provided by `@BotFather` |
| `TELEGRAM_CHAT_ID` | Your unique numerical user ID from `@userinfobot` |
| `CROSS_REPO_TOKEN` | GitHub Personal Access Token (PAT) with full `Actions: Write` scopes to trigger Project 2 |

## 🧪 Operational Status

**Status: FULLY FUNCTIONAL & OPERATIONAL**

The core pipeline has been thoroughly tested, benchmarked, and verified end-to-end:
* Cloud Environment (Render Engine Deployment) ➔ **Active** ✅
* Multi-model Media Pipeline (Whisper & Gemini SDK) ➔ **Verified** ✅
* Cross-Repository Automation Dispatcher ➔ **Active** ✅

The cloud environment responds instantaneously to conversational inputs and triggers external worker tasks without delays.
