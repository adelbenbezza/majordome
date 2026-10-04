# Majordome 🎩

A personal assistant that lives in Telegram. Talk to it by voice or text, in French or English.

Un assistant personnel qui vit dans Telegram. Parle-lui à la voix ou par écrit, en français ou en anglais.

> 🚧 **Work in progress / En construction** — for now the bot handles tasks by text or voice (add, complete, "what's left today?"). / Pour l'instant le bot gère les tâches à l'écrit ou à la voix (ajouter, cocher, « qu'est-ce qu'il me reste ? »).

**[🇬🇧 English](#-english) · [🇫🇷 Français](#-français)**

---

## 🇬🇧 English

### What it costs

About **€7–10 per month**: Railway hosting (~€5) plus a few euros of AI usage (OpenAI and Anthropic). You pay these services directly; nobody else can use your bot.

### Set up your own Majordome (about 15 minutes, no coding)

You'll need a phone with Telegram and a computer with a web browser.

**1. Create your bot on Telegram**
1. In Telegram, search for **@BotFather** and open the chat.
2. Send `/newbot`, then choose a name (e.g. "My Majordome") and a username ending in `bot` (e.g. `marie_majordome_bot`).
3. BotFather replies with a **token** (looks like `123456789:ABCdef...`). Copy it somewhere safe. This is `TELEGRAM_BOT_TOKEN`.

**2. Get an OpenAI key** (used to understand voice notes)
1. Create an account on [platform.openai.com](https://platform.openai.com/).
2. Add a payment method and a few euros of credit under *Billing*.
3. Go to [API keys](https://platform.openai.com/api-keys), click *Create new secret key* and copy it. This is `OPENAI_API_KEY`.

**3. Get an Anthropic key** (used to understand what you say)
1. Create an account on [console.anthropic.com](https://console.anthropic.com/).
2. Add a few euros of credit under *Billing*.
3. Go to *API keys*, create a key and copy it. This is `ANTHROPIC_API_KEY`.

**4. Deploy on Railway**
1. Click this button: [![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template/REPLACE_ME)
2. Create a Railway account if asked (signing in with GitHub is easiest), and choose the Hobby plan.
3. Paste your three keys in the boxes `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`, then click **Deploy**.
4. Wait a minute or two until the service shows **Active** / **Success**.

**5. Claim your bot**
Open your bot in Telegram (search for its username) and send `/start` **right away**. The first person to do this becomes its owner; it will ignore everyone else from then on. It should greet you. Then try "call the bank on Friday at 3pm".

### Something's wrong?
- **The bot doesn't answer:** in Railway, open your service, then *Deployments* → *View logs*. A line starting with `ERROR` explains the problem in plain words (for example a missing or mistyped key). Fix it in the *Variables* tab; Railway restarts the bot automatically.
- **Someone else claimed your bot:** in Railway's *Variables* tab, set `OWNER_TELEGRAM_ID` to your Telegram user ID (send any message to **@userinfobot** to find it). That always wins.

### Optional settings
All set in Railway's *Variables* tab. See [`.env.example`](.env.example) for the full list.

| Variable | What it does | Default |
| --- | --- | --- |
| `OWNER_TELEGRAM_ID` | Your Telegram user ID, to lock the bot to you | first person to send `/start` |
| `TIMEZONE` | Your timezone | `Europe/Paris` |
| `CLAUDE_MODEL` | Which Claude model to use | `claude-haiku-4-5` |
| `ENABLE_DASHBOARD` | `true` for the web dashboard (coming later) | `false` |

---

## 🇫🇷 Français

### Combien ça coûte

Environ **7 à 10 € par mois** : l'hébergement Railway (~5 €) plus quelques euros d'IA (OpenAI et Anthropic). Tu paies ces services directement ; personne d'autre ne peut utiliser ton bot.

### Installer ton propre Majordome (environ 15 minutes, sans coder)

Il te faut un téléphone avec Telegram et un ordinateur avec un navigateur.

**1. Crée ton bot sur Telegram**
1. Dans Telegram, cherche **@BotFather** et ouvre la conversation.
2. Envoie `/newbot`, puis choisis un nom (ex. « Mon Majordome ») et un nom d'utilisateur qui finit par `bot` (ex. `marie_majordome_bot`).
3. BotFather te répond avec un **token** (ça ressemble à `123456789:ABCdef...`). Copie-le en lieu sûr. C'est `TELEGRAM_BOT_TOKEN`.

**2. Obtiens une clé OpenAI** (pour comprendre les notes vocales)
1. Crée un compte sur [platform.openai.com](https://platform.openai.com/).
2. Ajoute un moyen de paiement et quelques euros de crédit dans *Billing*.
3. Va dans [API keys](https://platform.openai.com/api-keys), clique sur *Create new secret key* et copie la clé. C'est `OPENAI_API_KEY`.

**3. Obtiens une clé Anthropic** (pour comprendre ce que tu dis)
1. Crée un compte sur [console.anthropic.com](https://console.anthropic.com/).
2. Ajoute quelques euros de crédit dans *Billing*.
3. Va dans *API keys*, crée une clé et copie-la. C'est `ANTHROPIC_API_KEY`.

**4. Déploie sur Railway**
1. Clique sur ce bouton : [![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template/REPLACE_ME)
2. Crée un compte Railway si on te le demande (le plus simple : se connecter avec GitHub), et choisis l'offre Hobby.
3. Colle tes trois clés dans les cases `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY` et `ANTHROPIC_API_KEY`, puis clique sur **Deploy**.
4. Attends une ou deux minutes que le service affiche **Active** / **Success**.

**5. Deviens propriétaire de ton bot**
Ouvre ton bot dans Telegram (cherche son nom d'utilisateur) et envoie `/start` **tout de suite**. La première personne qui le fait en devient propriétaire ; il ignorera tous les autres ensuite. Il doit te saluer. Essaie ensuite « appeler la banque vendredi à 15h ».

### Ça ne marche pas ?
- **Le bot ne répond pas :** dans Railway, ouvre ton service, puis *Deployments* → *View logs*. Une ligne qui commence par `ERROR` explique le problème (par exemple une clé manquante ou mal copiée). Corrige-la dans l'onglet *Variables* ; Railway redémarre le bot tout seul.
- **Quelqu'un d'autre a pris ton bot :** dans l'onglet *Variables* de Railway, mets ton identifiant Telegram dans `OWNER_TELEGRAM_ID` (envoie n'importe quel message à **@userinfobot** pour le connaître). Ce réglage passe toujours en priorité.

### Réglages facultatifs
Tous dans l'onglet *Variables* de Railway. La liste complète est dans [`.env.example`](.env.example).

| Variable | À quoi ça sert | Par défaut |
| --- | --- | --- |
| `OWNER_TELEGRAM_ID` | Ton identifiant Telegram, pour réserver le bot à toi seul | la première personne qui envoie `/start` |
| `TIMEZONE` | Ton fuseau horaire | `Europe/Paris` |
| `CLAUDE_MODEL` | Le modèle Claude utilisé | `claude-haiku-4-5` |
| `ENABLE_DASHBOARD` | `true` pour le tableau de bord web (bientôt) | `false` |

---

## For developers

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env        # then fill in your keys (use a separate test bot!)
.venv/bin/python -m majordome
.venv/bin/pytest
```

Code lives in `majordome/`: `config.py` (environment variables), `db.py` (SQLite + migrations), `bot.py` (Telegram handlers and owner lock), `brain.py` (Claude reads the message and picks a tool), `actions.py` (Python carries out the tool call on the database), `voice.py` (Whisper transcription). Railway runs `python -m majordome` (see `railway.json`) and redeploys on every push to `main`.

**Railway template (for the Deploy button):** create the service from this repo, attach a **volume** (any mount path; the database goes there automatically via `RAILWAY_VOLUME_MOUNT_PATH`), mark the three API keys as required variables, then publish it as a template and replace `REPLACE_ME` in the links above.

License: [MIT](LICENSE).
