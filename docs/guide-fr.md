# Installer ton propre Majordome 🎩

*Guide pas à pas, sans aucune connaissance en informatique. Compte environ 30 minutes.*

[English version](guide-en.md)

---

## Sommaire

1. [C'est quoi, Majordome ?](#1-cest-quoi-majordome-)
2. [Ce qu'il te faut](#2-ce-quil-te-faut)
3. [Combien ça coûte](#3-combien-ça-coûte)
4. [Étape 1 : créer ton bot sur Telegram](#étape-1--créer-ton-bot-sur-telegram-5-min)
5. [Étape 2 : la clé OpenAI (pour les messages vocaux)](#étape-2--la-clé-openai-pour-les-messages-vocaux-5-min)
6. [Étape 3 : la clé Anthropic (pour comprendre tes messages)](#étape-3--la-clé-anthropic-pour-comprendre-tes-messages-5-min)
7. [Étape 4 : mettre ton Majordome en ligne sur Railway](#étape-4--mettre-ton-majordome-en-ligne-sur-railway-10-min)
8. [Étape 5 : faire connaissance avec ton Majordome](#étape-5--faire-connaissance-avec-ton-majordome-2-min)
9. [Étape 6 (facultatif) : ajouter ton agenda Google](#étape-6-facultatif--ajouter-ton-agenda-google)
10. [Au quotidien : tout ce que tu peux lui dire](#au-quotidien--tout-ce-que-tu-peux-lui-dire)
11. [Surveiller tes dépenses](#surveiller-tes-dépenses)
12. [Ça ne marche pas ?](#ça-ne-marche-pas-)
13. [Tes données et ta vie privée](#tes-données-et-ta-vie-privée)
14. [Tout arrêter](#tout-arrêter)

---

## 1. C'est quoi, Majordome ?

Majordome est un assistant personnel qui vit dans **Telegram**, l'application de messagerie. Tu lui parles comme à une personne, **par écrit ou par message vocal**, en français ou en anglais :

- « Rappelle-moi d'appeler la banque vendredi à 15h »
- « J'ai pris mes compléments »
- « Salle de sport le lundi et le mardi à 18h »
- « Qu'est-ce qu'il me reste aujourd'hui ? »

Et lui, de son côté :

- t'envoie **chaque matin** le programme de ta journée ;
- te **rappelle** les choses prévues à une heure précise ;
- fait **le point le soir** et te propose de reporter ce qui reste ;
- t'envoie **un bilan le dimanche** ;
- tient ta liste de courses, tes notes, et ta liste d'envies pour « un jour ».

**Ton Majordome est à toi seul.** Tu vas en installer ta propre copie, qui ne répond qu'à toi. Personne d'autre (pas même la personne qui t'a envoyé ce guide) ne peut voir ce que tu lui dis.

---

## 2. Ce qu'il te faut

- ✅ Un **téléphone** avec l'application **Telegram** installée et un compte créé.
  Pas encore Telegram ? Installe-le depuis l'App Store (iPhone) ou le Play Store (Android) et crée un compte avec ton numéro de téléphone.
- ✅ Un **ordinateur** avec un navigateur internet (Chrome, Safari, Firefox…). C'est plus simple pour copier-coller les codes. Tout est faisable sur téléphone, mais c'est moins confortable.
- ✅ Une **carte bancaire** (trois services à payer, voir ci-dessous).
- ✅ Une **adresse e-mail**.
- ✅ Un endroit pour **noter temporairement trois codes secrets** : une note sur ton ordinateur fera l'affaire. Tu l'effaceras à la fin.

> 💡 **Conseil** : fais tout d'une traite, sur ordinateur, avec ce guide ouvert à côté.

---

## 3. Combien ça coûte

Majordome lui-même est gratuit. Tu paies directement les trois services qu'il utilise :

| Service | À quoi il sert | Coût habituel |
| --- | --- | --- |
| **Railway** | L'ordinateur en ligne où ton Majordome tourne jour et nuit | environ **5 $ / mois** |
| **Anthropic** (Claude) | L'intelligence qui comprend tes messages | environ **2 à 4 $ / mois** |
| **OpenAI** (Whisper) | Transforme tes messages vocaux en texte | quelques **centimes / mois** |

👉 **Total : environ 7 à 10 € par mois.**

Pour Anthropic et OpenAI, tu achètes du **crédit à l'avance** (5 $ minimum chacun). Ces 5 $ durent généralement **plusieurs mois**. Tu ne seras jamais prélevé au-delà de ce que tu as acheté si tu laisses la recharge automatique désactivée (on t'expliquera comment).

À tout moment, envoie **/usage** à ton Majordome pour voir ce qu'il t'a coûté ce mois-ci.

---

## Étape 1 : créer ton bot sur Telegram (5 min)

Ton Majordome a besoin de son propre « compte » sur Telegram. C'est ce qu'on appelle un **bot**. On le crée en discutant avec un bot officiel de Telegram, **@BotFather** (« le père des bots »).

1. Ouvre **Telegram** sur ton téléphone (ou sur ordinateur sur [web.telegram.org](https://web.telegram.org)).
2. Touche la **loupe 🔍** (recherche) et tape **BotFather**.
3. Choisis celui qui a une **coche bleue ✔️** à côté du nom. ⚠️ Il en existe des faux : prends bien celui qui est vérifié.
4. Touche **Démarrer** (ou **Start**) en bas de l'écran.
5. Envoie-lui ce message : **/newbot**
6. Il te demande un **nom** pour ton bot. C'est le nom affiché, tu peux mettre ce que tu veux, par exemple :
   `Mon Majordome`
7. Il te demande ensuite un **nom d'utilisateur** (son identifiant unique). Règles :
   - il doit **finir par `bot`** ;
   - pas d'espaces ni d'accents ;
   - il doit être libre (si BotFather répond qu'il est déjà pris, essaie une variante).

   Exemples : `marie_majordome_bot`, `MajordomeDeLucasBot`.
8. BotFather te répond par un message qui contient une ligne comme celle-ci :

   ```
   Use this token to access the HTTP API:
   7123456789:AAH-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

   Ce long code est le **token** de ton bot. **Copie-le** (touche-le longuement → Copier) et colle-le dans ta note, avec à côté : `TELEGRAM_BOT_TOKEN`.

> 🔒 **Ce token est secret.** Quiconque l'a peut contrôler ton bot. Ne l'envoie à personne, ne le publie nulle part.

✅ **Étape 1 terminée.** Ta note contient : `TELEGRAM_BOT_TOKEN = 7123456789:AAH…`

---

## Étape 2 : la clé OpenAI (pour les messages vocaux) (5 min)

1. Va sur **[platform.openai.com](https://platform.openai.com)** et clique sur **Sign up** (créer un compte) ou **Log in** si tu as déjà un compte ChatGPT : c'est le même compte.
2. Suis les étapes (e-mail, mot de passe, parfois vérification par SMS).
3. **Ajoute du crédit :**
   1. Clique sur l'icône ⚙️ **Settings** (en haut à droite), puis sur **Billing** dans le menu de gauche.
   2. Clique sur **Add payment details** (ajouter un moyen de paiement) et entre ta carte.
   3. Clique sur **Add to credit balance** (ajouter du crédit) et mets **5 $**.
   4. Si on te propose **Auto recharge** (recharge automatique), **laisse-la désactivée**. Comme ça, tu ne dépenseras jamais plus que ce que tu as mis.
4. **Crée ta clé :**
   1. Va sur **[platform.openai.com/api-keys](https://platform.openai.com/api-keys)**.
   2. Clique sur **+ Create new secret key**.
   3. Donne-lui un nom, par exemple `Majordome`, et clique sur **Create secret key**.
   4. Une clé qui commence par `sk-` s'affiche. **Copie-la tout de suite** et colle-la dans ta note avec : `OPENAI_API_KEY`.

> ⚠️ OpenAI n'affiche cette clé **qu'une seule fois**. Si tu l'as perdue, pas grave : supprime-la et crées-en une nouvelle.

✅ **Étape 2 terminée.** Ta note contient : `OPENAI_API_KEY = sk-…`

*(Les intitulés exacts des boutons peuvent varier un peu : les sites changent parfois leur présentation.)*

---

## Étape 3 : la clé Anthropic (pour comprendre tes messages) (5 min)

Anthropic est l'entreprise qui fait **Claude**, l'intelligence artificielle qui comprend ce que tu dis à ton Majordome.

1. Va sur **[console.anthropic.com](https://console.anthropic.com)** et crée un compte (**Sign up**). C'est un compte différent de l'application Claude grand public.
2. Suis les étapes (e-mail, nom, etc.).
3. **Ajoute du crédit :**
   1. Dans le menu, va dans **Billing** (ou **Plans & Billing**).
   2. Ajoute ta carte et achète **5 $** de crédit (**Buy credits**).
   3. Laisse la **recharge automatique désactivée** (**Auto-reload** : off).
4. **Crée ta clé :**
   1. Va dans **API Keys** (dans le menu, ou sur [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)).
   2. Clique sur **Create Key**, nomme-la `Majordome`, puis valide.
   3. Une clé qui commence par `sk-ant-` s'affiche. **Copie-la** et colle-la dans ta note avec : `ANTHROPIC_API_KEY`.

> ⚠️ Là aussi, la clé n'est affichée **qu'une fois**.

✅ **Étape 3 terminée.** Ta note contient maintenant tes **trois codes** :

```
TELEGRAM_BOT_TOKEN = 7123456789:AAH…
OPENAI_API_KEY     = sk-…
ANTHROPIC_API_KEY  = sk-ant-…
```

---

## Étape 4 : mettre ton Majordome en ligne sur Railway (10 min)

**Railway** est un service qui fait tourner ton Majordome sur un ordinateur en ligne, 24h/24, même quand ton téléphone est éteint.

1. **Clique sur ce bouton :**

   [![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template/REPLACE_ME)

2. Railway te demande de te connecter. Le plus simple : **Login with GitHub** si tu as un compte GitHub, sinon **Login with Email** (tu recevras un lien de connexion par e-mail).
3. Choisis l'offre **Hobby** (environ 5 $/mois) et entre ta carte bancaire si on te le demande.
   *(L'offre d'essai gratuite peut suffire pour tester, mais elle s'arrête au bout de quelques jours : prends Hobby pour un Majordome qui tourne en continu.)*
4. Tu arrives sur une page qui te demande de remplir des **variables**. Ce sont les cases où tu colles tes trois codes :

   | Case | Ce que tu y colles |
   | --- | --- |
   | `TELEGRAM_BOT_TOKEN` | le token de BotFather (étape 1) |
   | `OPENAI_API_KEY` | la clé OpenAI `sk-…` (étape 2) |
   | `ANTHROPIC_API_KEY` | la clé Anthropic `sk-ant-…` (étape 3) |

   ⚠️ Fais attention à **ne pas ajouter d'espace** avant ou après en collant.
   Les autres cases éventuelles (comme `TIMEZONE`) sont **facultatives** : laisse-les telles quelles.
5. Clique sur **Deploy** (Déployer).
6. **Patiente 2 à 3 minutes.** Railway installe ton Majordome. Tu vois un carré qui représente ton service : attends qu'il affiche **Active** ou **Success** (en vert ✅).

**Pour vérifier que tout va bien :**

1. Clique sur le carré de ton service.
2. Va dans l'onglet **Deployments**, puis clique sur **View logs** (voir le journal) du déploiement le plus récent.
3. Tu dois voir une ligne qui contient **`Majordome starting`**, puis **`Application started`**. 🎉

Si tu vois une ligne qui commence par **`ERROR`**, va voir la section [Ça ne marche pas ?](#ça-ne-marche-pas-).

> 🧹 **Maintenant, efface ta note** avec les trois codes. Ils sont en sécurité dans Railway.

---

## Étape 5 : faire connaissance avec ton Majordome (2 min)

> ⏱️ **Fais cette étape tout de suite après l'étape 4.** La **première personne** qui écrit **/start** à ton bot en devient la **propriétaire**, et il ignore ensuite tous les autres. Il faut donc que ce soit toi !

1. Dans **Telegram**, touche la loupe 🔍 et tape le **nom d'utilisateur** de ton bot (celui qui finit par `bot`, choisi à l'étape 1).
   *Astuce : dans ta conversation avec BotFather, il y a aussi un lien direct `t.me/ton_bot`.*
2. Ouvre la conversation et touche **Démarrer** (ou envoie **/start**).
3. Ton Majordome se présente 🎩, puis t'envoie un second message avec ses réglages de départ :
   - fuseau horaire : Paris ;
   - brief du matin : 8h00 ;
   - point du soir : 21h00 ;
   - rappels : 30 minutes avant.
4. **Pour changer ces réglages, réponds-lui simplement en une phrase**, par exemple :

   > J'habite à Lyon, brief à 7h, point du soir à 21h30, pas de rappels entre 22h et 7h

   S'ils te conviennent, tu n'as rien à faire.
5. **Essaie !** Envoie-lui :

   > Appeler la banque demain à 10h

   Il doit te répondre : `📝 Ajouté : • Appeler la banque (demain, 10:00)`. 🎉

Bravo, ton Majordome est opérationnel !

> 📋 Touche le bouton **Menu** (ou tape **/**) dans la conversation pour voir toutes les commandes.

---

## Étape 6 (facultatif) : ajouter ton agenda Google

Ton Majordome peut afficher les rendez-vous de ton agenda dans le **brief du matin**.

1. **Sur un ordinateur**, ouvre **[Google Agenda](https://calendar.google.com)**.
2. Clique sur la roue dentée ⚙️ en haut à droite, puis sur **Paramètres**.
3. Dans la colonne de gauche, sous **Paramètres de mes agendas**, clique sur **ton agenda** (souvent ton nom).
4. Descends jusqu'à **« Adresse secrète au format iCal »** et clique sur l'icône pour **copier**.
5. Dans Telegram, **colle ce lien** dans la conversation avec ton Majordome.
6. Il répond : `📅 Agenda connecté ! …` ✅

C'est tout. Envoie **/brief** pour voir le résultat.

- Ce lien permet seulement de **lire** ton agenda. Ton Majordome ne l'envoie jamais à l'intelligence artificielle.
- Pour le déconnecter : envoie **/calendar off**.
- Tu utilises un agenda **Apple (iCloud)** ou **Outlook** ? Ça marche aussi : cherche dans leurs réglages l'option pour **partager** ou **publier** l'agenda, et colle le lien qui commence par `webcal://` ou `https://`.

---

## Au quotidien : tout ce que tu peux lui dire

Pas besoin de formules magiques : parle-lui normalement, **à l'écrit ou en message vocal** (garde le micro appuyé dans Telegram), en français ou en anglais.

### 📝 Tâches
- « Appeler la banque vendredi à 15h »
- « Acheter des fleurs demain »
- « J'ai appelé la banque » → la tâche est cochée ✅
- « Déplace la banque à lundi »
- « Supprime la tâche fleurs »
- « Non, c'est la banque, pas Blanche » → corrige un mot mal compris
- « Qu'est-ce qu'il me reste aujourd'hui ? », « Et demain ? », « Qu'est-ce que j'ai cette semaine ? »

### 🔁 Routines (les choses qui reviennent)
- « Salle de sport le lundi et le mardi à 18h »
- « Compléments tous les jours »
- « Payer le loyer le 1er de chaque mois »
- « Ménage un vendredi sur deux »
- « Dentiste tous les 6 mois, le 15 »
- « En fait la salle plutôt à 19h »
- « Quelles sont mes routines ? » → avec tes séries 🔥 (« 4 d'affilée »)

### ✨ Liste « Un jour » (les envies sans date)
- « Un jour j'aimerais apprendre la guitare »
- « Livres à lire : Dune et Le Petit Prince »
- « Montre ma liste un jour »
- « Allez, la guitare samedi à 10h » → devient une vraie tâche
- « J'ai fini Dune ! »

### 🛒 Listes et notes
- « Ajoute lait, œufs et pain à la liste de courses »
- « Note : idée de cadeau pour maman, une écharpe »
- « Montre ma liste de courses » → avec un bouton ✅ par article, pratique au magasin
- « J'ai acheté le lait »
- « Vide la liste de courses »

### ⚙️ Réglages (dis-le simplement)
- « Envoie le brief à 7h30 » · « Plus de brief le matin »
- « Fais le point du soir à 20h »
- « Rappelle-moi 15 minutes avant » · « Plus de rappels »
- « Pas de rappels entre 22h et 7h »
- « J'habite à Montréal maintenant »
- « Bilan du dimanche à 18h »

### 🙊 Une erreur ?
- « Annule » (ou **/undo**) → annule la dernière modification. Tu peux annuler plusieurs fois de suite.

### Ce qu'il fait tout seul
| Quand | Quoi |
| --- | --- |
| Chaque matin | ☀️ Le **brief** : tes rendez-vous, tes tâches, tes routines, avec un bouton ✅ sous chacune |
| 30 min avant | ⏰ Un **rappel** pour ce qui est prévu à une heure précise |
| 1h après une routine | 🔁 « Tu as fait ta salle de sport ? » si tu ne l'as pas cochée |
| Chaque soir | 🌙 Le **point du soir** : ce qui reste, avec un bouton « Tout reporter à demain » |
| Le dimanche soir | 🗓️ Le **bilan de la semaine**, avec une idée de ta liste « Un jour » |
| Après 3 reports | 🤔 « Tu as reporté ça 3 fois. On fait quoi ? » |

### Les commandes (menu « / »)
| Commande | Ce qu'elle fait |
| --- | --- |
| /today | Ce qu'il te reste aujourd'hui, avec des boutons ✅ |
| /brief | Le brief du matin, tout de suite |
| /review | Le bilan de la semaine |
| /undo | Annuler la dernière modification |
| /settings | Tes réglages et comment les changer |
| /calendar | Relier ton agenda |
| /usage | Ce que l'IA t'a coûté ce mois-ci |
| /reset | Tout effacer et repartir de zéro (demande confirmation) |

---

## Surveiller tes dépenses

- **Dans Telegram :** envoie **/usage** pour voir le coût de l'IA ce mois-ci.
- **Anthropic :** sur [console.anthropic.com](https://console.anthropic.com), la page **Usage** montre ta consommation, et **Billing** ton crédit restant. Tu peux aussi fixer une **limite mensuelle** dans **Limits**.
- **OpenAI :** [platform.openai.com/usage](https://platform.openai.com/usage).
- **Railway :** dans ton projet, onglet **Usage**.

**Quand ton crédit Anthropic ou OpenAI est épuisé**, ton Majordome te le dit clairement (« Ton compte Anthropic n'a plus de crédit… »). Il suffit alors de racheter du crédit sur le site concerné ; pas besoin de toucher à Railway.

---

## Ça ne marche pas ?

### Le bot ne répond pas du tout
1. Va sur [railway.com](https://railway.com), ouvre ton projet, clique sur ton service.
2. Regarde son état : s'il n'est pas **Active**, ouvre **Deployments** → **View logs**.
3. Cherche une ligne qui commence par **`ERROR`** :

| Le message dit… | Ce qu'il faut faire |
| --- | --- |
| `Missing required setting(s): …` | Une des trois clés manque. Onglet **Variables** → ajoute-la. |
| `Telegram rejected TELEGRAM_BOT_TOKEN` | Le token est mal copié. Recopie-le depuis BotFather (envoie-lui **/mybots** → ton bot → **API Token**). |

Après avoir modifié une variable, Railway **redémarre ton bot tout seul** (1 à 2 minutes).

### Il répond, mais avec un message d'erreur
- **« Ma clé Anthropic est refusée »** (ou OpenAI) : la clé est mal copiée ou a été supprimée. Crée une nouvelle clé (étape 2 ou 3) et remplace-la dans Railway → **Variables**.
- **« Ton compte … n'a plus de crédit »** : rachète du crédit sur le site concerné.
- **« Claude est surchargé »** : ça arrive rarement ; réessaie dans une minute.

### Quelqu'un d'autre a pris ton bot (il ne te répond pas, mais Railway est Active)
Quelqu'un a envoyé /start avant toi. Pour reprendre la main :
1. Dans Telegram, cherche **@userinfobot** et envoie-lui n'importe quel message : il te répond avec ton **Id** (un nombre).
2. Dans Railway → ton service → **Variables** → **New Variable** : nom `OWNER_TELEGRAM_ID`, valeur : ton Id.
3. Attends le redémarrage : ton bot ne répond plus qu'à toi.

### Les heures sont décalées
Dis-lui simplement où tu habites : « J'habite à Montréal ». Vérifie avec **/settings**.

### Il n'a pas compris un message vocal
Il te montre toujours ce qu'il a entendu (🎙️ « … »). Si c'est faux, dis « annule » et répète, ou écris-le.

### Je veux tout recommencer à zéro
Envoie **/reset** : il te demande confirmation, puis efface tâches, routines, listes et notes. Tes réglages sont gardés.

---

## Tes données et ta vie privée

- Tes tâches, routines, listes et notes sont stockées **dans ta propre copie** de Majordome, sur **ton** compte Railway. **Personne d'autre n'y a accès**, pas même la personne qui t'a envoyé ce guide.
- Ton bot **ignore tout le monde sauf toi** : un inconnu qui le trouverait ne peut ni lire tes données, ni dépenser ton crédit.
- Pour fonctionner, tes messages sont envoyés à **Anthropic** (pour les comprendre) et tes messages vocaux à **OpenAI** (pour les transcrire). Ces deux entreprises indiquent ne pas utiliser les données envoyées par leur API pour entraîner leurs modèles.
- Le lien de ton agenda reste dans ta base de données et n'est **jamais** envoyé à l'IA.

---

## Tout arrêter

Si un jour tu ne veux plus de ton Majordome :

1. **Railway** : ouvre ton projet → **Settings** → tout en bas, **Delete project**. Le bot s'arrête et toutes ses données sont effacées. Tu n'es plus facturé.
2. **Anthropic** et **OpenAI** : supprime tes clés (pages **API Keys**). Le crédit restant reste sur ton compte.
3. **Telegram** (facultatif) : envoie **/deletebot** à @BotFather pour supprimer le bot.

---

*Une question ? Demande à la personne qui t'a envoyé ce guide. 🎩*
