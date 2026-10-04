# Set up your own Majordome 🎩

*A step-by-step guide that needs no technical knowledge. It takes about 30 minutes.*

[Version française](guide-fr.md)

---

## Contents

1. [What is Majordome?](#1-what-is-majordome)
2. [What you need](#2-what-you-need)
3. [What it costs](#3-what-it-costs)
4. [Step 1: create your bot on Telegram](#step-1-create-your-bot-on-telegram-5-min)
5. [Step 2: the OpenAI key (for voice notes)](#step-2-the-openai-key-for-voice-notes-5-min)
6. [Step 3: the Anthropic key (to understand your messages)](#step-3-the-anthropic-key-to-understand-your-messages-5-min)
7. [Step 4: put your Majordome online with Railway](#step-4-put-your-majordome-online-with-railway-10-min)
8. [Step 5: meet your Majordome](#step-5-meet-your-majordome-2-min)
9. [Step 6 (optional): add your Google Calendar](#step-6-optional-add-your-google-calendar)
10. [Every day: everything you can say](#every-day-everything-you-can-say)
11. [Keeping an eye on costs](#keeping-an-eye-on-costs)
12. [Something's wrong?](#somethings-wrong)
13. [Your data and privacy](#your-data-and-privacy)
14. [Stopping everything](#stopping-everything)

---

## 1. What is Majordome?

Majordome is a personal assistant that lives in **Telegram**, the messaging app. You talk to it like you would to a person, **by text or by voice note**, in English or French:

- "Remind me to call the bank on Friday at 3pm"
- "I took my supplements"
- "Gym on Mondays and Tuesdays at 6pm"
- "What's left today?"

And on its side, it:

- sends you **every morning** the plan for your day;
- **reminds** you of things planned at a set time;
- **checks in in the evening** and offers to move what's left to tomorrow;
- sends you **a weekly review on Sundays**;
- keeps your shopping list, your notes, and your list of things to do "someday".

**Your Majordome is yours alone.** You'll set up your own copy, which only answers you. Nobody else (not even the person who sent you this guide) can see what you tell it.

---

## 2. What you need

- ✅ A **phone** with the **Telegram** app installed and an account created.
  No Telegram yet? Install it from the App Store (iPhone) or the Play Store (Android) and sign up with your phone number.
- ✅ A **computer** with a web browser (Chrome, Safari, Firefox…). It makes copying and pasting codes easier. Everything can be done on a phone, just less comfortably.
- ✅ A **bank card** (three services to pay for, see below).
- ✅ An **email address**.
- ✅ Somewhere to **temporarily write down three secret codes**: a note on your computer is fine. You'll delete it at the end.

> 💡 **Tip:** do it all in one go, on a computer, with this guide open next to you.

---

## 3. What it costs

Majordome itself is free. You pay the three services it uses directly:

| Service | What it does | Usual cost |
| --- | --- | --- |
| **Railway** | The online computer where your Majordome runs day and night | about **$5 / month** |
| **Anthropic** (Claude) | The intelligence that understands your messages | about **$2–4 / month** |
| **OpenAI** (Whisper) | Turns your voice notes into text | a few **cents / month** |

👉 **Total: about €7–10 a month.**

For Anthropic and OpenAI, you buy **credit in advance** ($5 minimum each). That $5 usually lasts **several months**. You'll never be charged more than what you bought as long as automatic recharge stays off (we'll show you how).

At any time, send **/usage** to your Majordome to see what it has cost you this month.

---

## Step 1: create your bot on Telegram (5 min)

Your Majordome needs its own "account" on Telegram, called a **bot**. You create it by chatting with Telegram's official bot, **@BotFather**.

1. Open **Telegram** on your phone (or on a computer at [web.telegram.org](https://web.telegram.org)).
2. Tap the **magnifying glass 🔍** (search) and type **BotFather**.
3. Pick the one with a **blue tick ✔️** next to its name. ⚠️ There are fakes: make sure it's the verified one.
4. Tap **Start** at the bottom of the screen.
5. Send it this message: **/newbot**
6. It asks for a **name** for your bot. This is the display name; use anything you like, for example:
   `My Majordome`
7. It then asks for a **username** (its unique handle). Rules:
   - it must **end in `bot`**;
   - no spaces or accents;
   - it must be free (if BotFather says it's taken, try a variation).

   Examples: `sarah_majordome_bot`, `LucasMajordomeBot`.
8. BotFather replies with a message containing a line like this:

   ```
   Use this token to access the HTTP API:
   7123456789:AAH-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

   That long code is your bot's **token**. **Copy it** (long-press it → Copy) and paste it into your note, next to: `TELEGRAM_BOT_TOKEN`.

> 🔒 **This token is secret.** Anyone who has it can control your bot. Don't send it to anyone or post it anywhere.

✅ **Step 1 done.** Your note contains: `TELEGRAM_BOT_TOKEN = 7123456789:AAH…`

---

## Step 2: the OpenAI key (for voice notes) (5 min)

1. Go to **[platform.openai.com](https://platform.openai.com)** and click **Sign up**, or **Log in** if you already have a ChatGPT account: it's the same account.
2. Follow the steps (email, password, sometimes a text-message check).
3. **Add credit:**
   1. Click the ⚙️ **Settings** icon (top right), then **Billing** in the left menu.
   2. Click **Add payment details** and enter your card.
   3. Click **Add to credit balance** and add **$5**.
   4. If you're offered **Auto recharge**, **leave it off**. That way you'll never spend more than you put in.
4. **Create your key:**
   1. Go to **[platform.openai.com/api-keys](https://platform.openai.com/api-keys)**.
   2. Click **+ Create new secret key**.
   3. Give it a name, for example `Majordome`, and click **Create secret key**.
   4. A key starting with `sk-` appears. **Copy it straight away** and paste it into your note with: `OPENAI_API_KEY`.

> ⚠️ OpenAI shows this key **only once**. If you lose it, no problem: delete it and create a new one.

✅ **Step 2 done.** Your note contains: `OPENAI_API_KEY = sk-…`

*(Button labels may differ slightly: websites change their layout from time to time.)*

---

## Step 3: the Anthropic key (to understand your messages) (5 min)

Anthropic is the company that makes **Claude**, the artificial intelligence that understands what you tell your Majordome.

1. Go to **[console.anthropic.com](https://console.anthropic.com)** and create an account (**Sign up**). This is a different account from the consumer Claude app.
2. Follow the steps (email, name, etc.).
3. **Add credit:**
   1. In the menu, go to **Billing** (or **Plans & Billing**).
   2. Add your card and buy **$5** of credit (**Buy credits**).
   3. Leave **automatic reload off** (**Auto-reload**: off).
4. **Create your key:**
   1. Go to **API Keys** (in the menu, or at [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)).
   2. Click **Create Key**, name it `Majordome`, and confirm.
   3. A key starting with `sk-ant-` appears. **Copy it** and paste it into your note with: `ANTHROPIC_API_KEY`.

> ⚠️ Here too, the key is shown **only once**.

✅ **Step 3 done.** Your note now has your **three codes**:

```
TELEGRAM_BOT_TOKEN = 7123456789:AAH…
OPENAI_API_KEY     = sk-…
ANTHROPIC_API_KEY  = sk-ant-…
```

---

## Step 4: put your Majordome online with Railway (10 min)

**Railway** runs your Majordome on an online computer, around the clock, even when your phone is off.

1. **Click this button:**

   [![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template/REPLACE_ME)

2. Railway asks you to sign in. Easiest: **Login with GitHub** if you have a GitHub account, otherwise **Login with Email** (you'll get a sign-in link by email).
3. Choose the **Hobby** plan (about $5/month) and enter your card if asked.
   *(The free trial is enough to try things out, but it stops after a few days: pick Hobby for a Majordome that runs all the time.)*
4. You reach a page asking you to fill in **variables**. These are the boxes where you paste your three codes:

   | Box | What to paste |
   | --- | --- |
   | `TELEGRAM_BOT_TOKEN` | the token from BotFather (step 1) |
   | `OPENAI_API_KEY` | the OpenAI key `sk-…` (step 2) |
   | `ANTHROPIC_API_KEY` | the Anthropic key `sk-ant-…` (step 3) |

   ⚠️ Be careful **not to add a space** before or after when pasting.
   Any other boxes (such as `TIMEZONE`) are **optional**: leave them as they are.
5. Click **Deploy**.
6. **Wait 2–3 minutes.** Railway is installing your Majordome. You'll see a box representing your service: wait until it shows **Active** or **Success** (in green ✅).

**To check everything is fine:**

1. Click your service's box.
2. Go to the **Deployments** tab, then click **View logs** on the most recent deployment.
3. You should see a line containing **`Majordome starting`**, then **`Application started`**. 🎉

If you see a line starting with **`ERROR`**, see [Something's wrong?](#somethings-wrong).

> 🧹 **Now delete your note** with the three codes. They're safely stored in Railway.

---

## Step 5: meet your Majordome (2 min)

> ⏱️ **Do this step right after step 4.** The **first person** to send **/start** to your bot becomes its **owner**, and it ignores everyone else from then on. So it has to be you!

1. In **Telegram**, tap the magnifying glass 🔍 and type your bot's **username** (the one ending in `bot` you chose in step 1).
   *Tip: your chat with BotFather also has a direct link, `t.me/your_bot`.*
2. Open the chat and tap **Start** (or send **/start**).
3. Your Majordome introduces itself 🎩, then sends a second message with its starting settings:
   - timezone: Paris;
   - morning brief: 08:00;
   - evening check-in: 21:00;
   - reminders: 30 minutes before.
4. **To change these settings, just reply in one sentence**, for example:

   > I live in London, brief at 7, check-in at 9:30pm, no reminders between 10pm and 7am

   If they suit you, there's nothing to do.
5. **Try it!** Send:

   > Call the bank tomorrow at 10am

   It should reply: `📝 Added: • Call the bank (tomorrow, 10:00)`. 🎉

Well done, your Majordome is up and running!

> 📋 Tap the **Menu** button (or type **/**) in the chat to see all the commands.

---

## Step 6 (optional): add your Google Calendar

Your Majordome can show your calendar's appointments in the **morning brief**.

1. **On a computer**, open **[Google Calendar](https://calendar.google.com)**.
2. Click the gear ⚙️ at the top right, then **Settings**.
3. In the left column, under **Settings for my calendars**, click **your calendar** (often your name).
4. Scroll down to **"Secret address in iCal format"** and click the icon to **copy** it.
5. In Telegram, **paste this link** into the chat with your Majordome.
6. It replies: `📅 Calendar connected! …` ✅

That's it. Send **/brief** to see the result.

- This link only lets your Majordome **read** your calendar. It is never sent to the artificial intelligence.
- To disconnect it: send **/calendar off**.
- Using an **Apple (iCloud)** or **Outlook** calendar? It works too: look in their settings for the option to **share** or **publish** the calendar, and paste the link starting with `webcal://` or `https://`.

---

## Every day: everything you can say

No magic words needed: talk to it normally, **in text or by voice note** (hold the microphone button in Telegram), in English or French.

### 📝 Tasks
- "Call the bank on Friday at 3pm"
- "Buy flowers tomorrow"
- "I called the bank" → the task is ticked off ✅
- "Move the bank to Monday"
- "Delete the flowers task"
- "No, it's the bank, not Blanche" → fixes a misheard word
- "What's left today?", "And tomorrow?", "What do I have this week?"

### 🔁 Routines (things that repeat)
- "Gym on Mondays and Tuesdays at 6pm"
- "Supplements every day"
- "Pay rent on the 1st of every month"
- "Cleaning every other Friday"
- "Dentist every 6 months, on the 15th"
- "Actually, gym at 7pm instead"
- "What are my routines?" → with your streaks 🔥 ("4 in a row")

### ✨ Someday list (wishes with no date)
- "One day I'd like to learn guitar"
- "Books to read: Dune and The Little Prince"
- "Show my Someday list"
- "Let's do the guitar thing on Saturday at 10am" → becomes a real task
- "I finished Dune!"

### 🛒 Lists and notes
- "Add milk, eggs and bread to the shopping list"
- "Note: gift idea for mum, a scarf"
- "Show my shopping list" → with a ✅ button per item, handy in the shop
- "I bought the milk"
- "Empty the shopping list"

### ⚙️ Settings (just say it)
- "Send the brief at 7:30" · "No more morning brief"
- "Check in at 8pm"
- "Remind me 15 minutes before" · "No more reminders"
- "No reminders between 10pm and 7am"
- "I live in Montreal now"
- "Sunday review at 6pm"

### 🙊 A mistake?
- "Undo" (or **/undo**) → undoes the last change. You can undo several times in a row.

### What it does on its own
| When | What |
| --- | --- |
| Every morning | ☀️ The **brief**: your appointments, tasks and routines, with a ✅ button under each |
| 30 min before | ⏰ A **reminder** for things planned at a set time |
| 1h after a routine | 🔁 "Did you go to the gym?" if you haven't ticked it off |
| Every evening | 🌙 The **evening check-in**: what's left, with a "Move all to tomorrow" button |
| Sunday evening | 🗓️ The **weekly review**, with an idea from your Someday list |
| After 3 postponements | 🤔 "You've postponed this 3 times. What shall we do?" |

### Commands (the "/" menu)
| Command | What it does |
| --- | --- |
| /today | What's left today, with ✅ buttons |
| /brief | The morning brief, now |
| /review | This week's review |
| /undo | Undo the last change |
| /settings | Your settings and how to change them |
| /calendar | Link your calendar |
| /usage | What the AI has cost you this month |
| /reset | Delete everything and start fresh (asks for confirmation) |

---

## Keeping an eye on costs

- **In Telegram:** send **/usage** to see this month's AI cost.
- **Anthropic:** at [console.anthropic.com](https://console.anthropic.com), the **Usage** page shows what you've used and **Billing** your remaining credit. You can also set a **monthly limit** under **Limits**.
- **OpenAI:** [platform.openai.com/usage](https://platform.openai.com/usage).
- **Railway:** in your project, the **Usage** tab.

**When your Anthropic or OpenAI credit runs out**, your Majordome tells you clearly ("Your Anthropic account is out of credit…"). Just buy more credit on that site; there's no need to touch Railway.

---

## Something's wrong?

### The bot doesn't answer at all
1. Go to [railway.com](https://railway.com), open your project and click your service.
2. Check its status: if it isn't **Active**, open **Deployments** → **View logs**.
3. Look for a line starting with **`ERROR`**:

| The message says… | What to do |
| --- | --- |
| `Missing required setting(s): …` | One of the three keys is missing. **Variables** tab → add it. |
| `Telegram rejected TELEGRAM_BOT_TOKEN` | The token was copied wrong. Copy it again from BotFather (send it **/mybots** → your bot → **API Token**). |

After you change a variable, Railway **restarts your bot by itself** (1–2 minutes).

### It answers, but with an error message
- **"My Anthropic key was rejected"** (or OpenAI): the key was copied wrong or deleted. Create a new key (step 2 or 3) and replace it in Railway → **Variables**.
- **"Your … account is out of credit"**: buy more credit on that site.
- **"Claude is overloaded"**: this is rare; try again in a minute.

### Someone else took your bot (it ignores you, but Railway is Active)
Someone sent /start before you. To take it back:
1. In Telegram, search for **@userinfobot** and send it any message: it replies with your **Id** (a number).
2. In Railway → your service → **Variables** → **New Variable**: name `OWNER_TELEGRAM_ID`, value: your Id.
3. Wait for the restart: your bot now only answers you.

### The times are off
Just tell it where you live: "I live in Montreal". Check with **/settings**.

### It misunderstood a voice note
It always shows what it heard (🎙️ "…"). If it's wrong, say "undo" and repeat, or type it.

### I want to start over from scratch
Send **/reset**: it asks for confirmation, then deletes tasks, routines, lists and notes. Your settings are kept.

---

## Your data and privacy

- Your tasks, routines, lists and notes are stored **in your own copy** of Majordome, on **your** Railway account. **Nobody else has access**, not even the person who sent you this guide.
- Your bot **ignores everyone but you**: a stranger who found it can neither read your data nor spend your credit.
- To work, your messages are sent to **Anthropic** (to understand them) and your voice notes to **OpenAI** (to transcribe them). Both companies state that they don't use data sent through their API to train their models.
- Your calendar link stays in your database and is **never** sent to the AI.

---

## Stopping everything

If one day you no longer want your Majordome:

1. **Railway:** open your project → **Settings** → at the very bottom, **Delete project**. The bot stops and all its data is deleted. You're no longer billed.
2. **Anthropic** and **OpenAI:** delete your keys (**API Keys** pages). Any remaining credit stays on your account.
3. **Telegram** (optional): send **/deletebot** to @BotFather to delete the bot.

---

*Any questions? Ask the person who sent you this guide. 🎩*
