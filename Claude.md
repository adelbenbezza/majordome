# Majordome

A bilingual (French / English) personal life assistant that lives in Telegram. The owner talks to it by voice or text throughout the day; it keeps track of tasks, routines and "someday" wishes, and nudges them at the right moments.

## About the owner

- Owner: Adel, based in Paris (timezone Europe/Paris).
- Adel is a **junior developer**. He can read code, use Git and the terminal, and wants to learn while building. Briefly explain the reasoning behind design choices and any concept he may not have met yet (async, job scheduling, tool use, migrations…), without over-explaining basics. Prefer small, reviewable commits and pull requests he can read through.
- His **friends may not be developers**: anything they have to do (README, setup guide, onboarding chat) must assume no technical knowledge.
- Adel speaks French and English and mixes both. The bot must handle either language in any message and reply in the language the user wrote in.

## Goals

1. A reliable personal assistant for Adel.
2. **Reusable by his friends**: anyone can deploy their own copy without touching code. Every design decision must keep this possible.

## Two editions, one codebase

- **Lite**: the Telegram bot only (everything in Features below). This is the default.
- **Full**: Lite plus a visual dashboard, a website that can also be installed on a phone like an app (PWA).

Both editions are the **same code**. The dashboard is switched on with `ENABLE_DASHBOARD=true`; when it's off, none of the dashboard code runs. Never fork the project into two repositories, so every bot improvement reaches both editions.

## Architecture

| Part | Choice |
| --- | --- |
| Interface | Telegram bot (voice notes, text, inline buttons) |
| Code | Python 3.12+, `python-telegram-bot` (async, with JobQueue for scheduling) |
| Voice transcription | OpenAI Whisper API (language auto-detected, never forced) |
| Understanding and writing | Claude API, model `claude-haiku-4-5` by default (configurable) |
| Storage | SQLite (single file, path configurable, on a persistent volume) |
| Hosting | Railway, deployed from GitHub on every push to `main` |

How a message flows: voice note → Whisper transcription → Claude interprets it and returns a structured action (tool use / JSON) → Python executes it on the database → bot replies with a short confirmation.

Claude decides *what* the user means; Python does the actual work. Never let the model write to the database directly.

## Features

**Capture**
- Add tasks by voice or text, with optional date and time extracted from natural language ("call the bank on Friday at 3pm").
- Mark tasks done by voice or text ("I took my supplements"), matched to the right task.
- "Someday" list: wishes with no date (read a book, learn guitar), kept separate from daily tasks, grouped by type. Can be promoted to a dated task.
- Quick notes and lists (ideas, shopping list), retrievable on request.

**Organise**
- Recurring routines (e.g. supplements daily, gym on given weekdays at a given time), automatically added to each relevant day's list.
- "What's left today?" on demand: undone tasks and routines for today.
- Later: Google Calendar events included in the morning brief.

**Accompany**
- Morning brief at a configurable time, with a ✅ inline button under each task.
- Timed reminders (e.g. "Gym in 30 minutes"), and a follow-up if a routine isn't checked off.
- Evening check-in listing what's left, offering to move it to tomorrow.
- Habit streaks ("Gym: 4 days in a row").
- Weekly review on Sunday evening, including one suggestion from the Someday list.

## Full edition: dashboard

A web dashboard served by the **same Railway service** as the bot, reading and writing the **same SQLite database**, so anything done in Telegram shows up in the dashboard and the other way round.

- **Pages:** Today (tasks and routines, tick them off), Week (calendar view of dated tasks), Routines and streaks (charts of habits over time), Someday (board grouped by type), Notes and lists, Settings (brief time, language, routines).
- **App on the phone:** a Progressive Web App (installable from the browser to the home screen, with an icon). No App Store: a native app would need a paid Apple developer account and review, and friends could not deploy their own copy.
- **Login without passwords:** the bot sends the owner a one-time login link on request (e.g. `/dashboard`). Only the owner can sign in, same owner lock as the bot.
- **Tech:** FastAPI (or similar) running alongside the bot in the same process, simple server-rendered pages or a light front end. Keep it lightweight; no separate database or second hosting service.
- Mobile-first design, bilingual (French / English), light and dark mode.

## Build order

Each stage must leave a working, deployed bot. Finish and test a stage before starting the next.

1. **Setup**: project skeleton, Railway deployment, environment variables, owner lock. Bot replies "received".
2. **Core**: voice transcription, add / complete tasks, "what's left today?", morning brief.
3. **Routines and buttons**: recurring routines, ✅ buttons, dates and times on tasks.
4. **Reminders**: timed reminders, evening check-in with rescheduling.
5. **Someday list and notes**.
6. **Motivation and overview**: streaks, weekly review, Google Calendar. *(Lite edition complete.)*
7. **Dashboard foundations** (Full): web server alongside the bot, login link via the bot, Today page.
8. **Dashboard pages** (Full): Week, Routines and streaks, Someday, Notes, Settings.
9. **Phone app** (Full): installable PWA with icon and offline-friendly Today page.

Design the database in stages 1–6 so the dashboard can be added later without reworking it.

## Rules for reusability

- **No personal data or secrets in the code.** Everything personal comes from environment variables or from the database:
  - `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (required)
  - `OWNER_TELEGRAM_ID` (optional; if unset, the first user to send `/start` becomes the owner and is saved in the database)
  - `TIMEZONE` (default `Europe/Paris`), `DATABASE_PATH`, `CLAUDE_MODEL`
  - `ENABLE_DASHBOARD` (default `false`; `true` = Full edition)
- Keep a `.env.example` listing every variable with a comment. Never commit `.env`.
- **Owner lock:** the bot ignores everyone except its owner, so strangers cannot spend the owner's API credit.
- **Settings by conversation:** brief time, language preference and routines are set up through a `/start` onboarding chat and can be changed later by just telling the bot. No config files for end users.
- Provide a **"Deploy on Railway"** button and a step-by-step setup guide in the README, in both French and English, including expected monthly cost (roughly €7–10: Railway plus a few euros of AI usage).
- License: MIT.

## Conventions

- Keep the code simple and readable; prefer a few clear modules (e.g. `bot.py`, `brain.py` for Claude, `voice.py`, `db.py`, `scheduler.py`) over clever abstractions.
- All times stored in UTC, displayed in the owner's timezone.
- Handle API failures gracefully: tell the user something went wrong in plain words instead of crashing or staying silent.
- Keep API costs low: short prompts, Haiku by default, send Claude only the tasks it needs.
- Add tests for the database logic and for parsing Claude's structured actions.
- Commit messages in English, clear and short.

## Previous version (for context)

The first prototype ran on Make.com (Telegram → Whisper → Claude → Make data store). It will be switched off once the Python bot reaches stage 2.
