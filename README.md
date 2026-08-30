# Twitch VOD Clip Agent

Automated system for analyzing completed Twitch VODs, detecting interesting moments, generating video clips and sending them to Telegram for manual approval.

## 🎯 Project purpose

The purpose of this project is to automatically review a completed Twitch VOD and identify moments that could work well as Twitch clips or short-form content.

The project does **not** publish directly to TikTok and does **not** add subtitles or perform final TikTok editing.

Those tasks belong to a separate project.

## 🔄 Current workflow

```text
Twitch VOD
    ↓
Twitch authentication
    ↓
Find latest VOD
    ↓
Download complete VOD
    ↓
Whisper transcription
    ↓
Gemini analysis
    ↓
Interesting moments / candidates
    ↓
Candidate filtering
    ↓
Generate MP4 clips
    ↓
Create clips manifest
    ↓
Send clips to Telegram
    ↓
Manual approval
    ├── ✅ Approve
    └── ❌ Reject
```

## 🤖 What the agent does

### 1. Twitch authentication

Connects to Twitch using the configured Twitch API credentials.

### 2. VOD discovery

Finds the latest available Twitch VOD for the configured channel.

### 3. Complete VOD download

Downloads the complete VOD locally so the entire stream can be analyzed.

### 4. Whisper transcription

Transcribes the complete VOD using Whisper.

The transcription contains timestamped segments that allow interesting moments to be located precisely.

### 5. Gemini analysis

Sends the transcription to Gemini to identify potentially interesting moments.

Gemini evaluates moments based on factors such as:

* Suspense
* Scares
* Reactions
* Funny moments
* Unexpected events
* High-intensity situations
* Other potentially engaging moments

Each candidate receives information such as:

* Start time
* End time
* Score
* Category
* Suggested title
* Reason
* Confidence

### 6. Candidate filtering

Candidates are filtered before clip generation according to the project's configured criteria.

### 7. Clip generation

The selected candidates are converted into MP4 video clips using FFmpeg.

The generated clips retain the original video and audio synchronization.

### 8. Telegram approval

Generated clips are sent to the configured Telegram chat.

Each clip includes:

* Video
* Suggested title
* Score
* Category
* Duration
* Reason for selection
* Approval button
* Rejection button

The workflow waits indefinitely until all clips have been reviewed.

There is no fixed approval timeout.

This means the workflow can remain waiting while the streamer is unavailable.

### 9. Approval result

The project records which clips were:

* `approved`
* `rejected`
* `pending`

The approval state is stored as JSON.

## 📁 Project output

Important generated files include:

```text
data/
├── analysis/
│   └── <vod_id>_candidates.json
│
├── transcriptions/
│   └── <vod_id>.json
│
├── filtered_candidates/
│   └── <vod_id>_selected.json
│
├── clips/
│   └── <vod_id>/
│       ├── clip_*.mp4
│       └── clips_manifest.json
│
└── telegram_approved/
    ├── <vod_id>_telegram_state.json
    └── <vod_id>_approved.json
```

## 🔐 Required GitHub Secrets

The workflow requires the following GitHub Actions secrets:

```text
TWITCH_CLIENT_ID
TWITCH_CLIENT_SECRET
GEMINI_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

### Twitch

`TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` are used for Twitch API authentication and VOD discovery.

### Gemini

`GEMINI_API_KEY` is used to analyze the Whisper transcription and identify interesting moments.

### Telegram

`TELEGRAM_BOT_TOKEN` identifies the Telegram bot.

`TELEGRAM_CHAT_ID` identifies the Telegram chat where clips are sent for approval.

## 🧪 Current status

The complete VOD pipeline has been successfully tested.

The tested pipeline includes:

```text
Python                  ✅
FFmpeg                  ✅
FFprobe                 ✅
Git                     ✅
Whisper                 ✅
Gemini SDK              ✅
Twitch authentication   ✅
Twitch VOD discovery    ✅
Complete VOD download   ✅
Whisper transcription   ✅
Gemini analysis         ✅
Candidate filtering     ✅
Clip generation         ✅
Clips manifest          ✅
Telegram delivery       ✅
Telegram approval       ✅
```

A complete test was successfully performed using Twitch VOD:

```text
2846005700
```

The generated clips were successfully sent to Telegram and could be approved or rejected.

## 📱 Telegram approval

Telegram is currently the final step of this project.

The agent sends every generated candidate to Telegram and waits for the user to manually decide whether the clip is useful.

Example:

```text
🎬 CLIP DE TWITCH

VOD: 2846005700
Clip #1

📌 ¡Nos está atacando!
⭐ Score: 85
📂 Categoría: sustos o reacciones fuertes
⏱️ Duración: 40s

[ ✅ APROBAR ] [ ❌ RECHAZAR ]
```

Once a decision is made, the Telegram message is updated and the result is stored.

## 🚫 What this project does not do

This project intentionally stops after Telegram approval.

It does **not** currently:

* Create official Twitch Clips through the Twitch platform
* Add subtitles
* Identify speakers for subtitles
* Convert videos to TikTok format
* Perform TikTok-specific editing
* Publish to TikTok
* Automatically publish approved clips to social networks

Those functions belong outside the scope of this project.

## ▶️ Current execution

The current complete pipeline test is manually started through GitHub Actions using:

```text
workflow_dispatch
```

This allows the complete pipeline to be tested without automatically processing every VOD.

## 🏗️ Project architecture

The main processing components are:

```text
src/
├── twitch_auth.py
├── twitch_vods.py
├── twitch_vod_downloader.py
├── whisper_transcriber.py
├── gemini_analyzer.py
├── candidate_filter.py
├── clip_generator.py
└── telegram_approval.py
```

Each component has a specific responsibility in the pipeline.

## 📌 Project scope

The final responsibility of this project is:

> **Take a completed Twitch VOD, identify potentially interesting moments, generate MP4 clips and let the user approve or reject those clips through Telegram.**

Once a clip is approved, this project considers its job complete.

## ✅ Status

**Project 1 — Twitch VOD Clip Agent: FUNCTIONAL**

The core VOD → analysis → clip generation → Telegram approval pipeline is operational and tested.
