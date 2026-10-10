# Copilot MA Agent — Setup Guide

## What you have

```
.github/
  copilot-instructions.md          <- Auto-loaded context (always active)
  copilot/
    slide-kit.prompt.md            <- Build scientific decks
    compliance-audit.prompt.md     <- UCPMP/OPPI audit
    kol-engagement.prompt.md       <- Advisory boards & KOL plans
    evidence-search.prompt.md      <- Literature search & synthesis
    impact-evaluator.prompt.md     <- T-Bone test on any initiative
    cme-design.prompt.md           <- CME / training design
    value-story.prompt.md          <- Payer value narrative
    strategy-brief.prompt.md       <- Portfolio strategy
  COPILOT-SETUP-GUIDE.md          <- This file
```

---

## Option 1: VS Code + GitHub Copilot (Recommended)

### Step 1 — Install
- VS Code with **GitHub Copilot** and **GitHub Copilot Chat** extensions
- Sign in with your GitHub account (Copilot subscription required)

### Step 2 — Copy files to your work repo
```bash
# From this repo, copy the .github folder to any work repo
cp -r .github/ /path/to/your-work-repo/.github/
```

Or create them fresh in any repo — just copy the file contents.

### Step 3 — Custom Instructions (auto-loaded)
The file `.github/copilot-instructions.md` is **automatically loaded** by Copilot Chat in VS Code when you open the repo. No configuration needed.

This means every Copilot Chat in that repo already has:
- Full RMMH portfolio knowledge
- 7 specialist modes
- T-Bone test framework
- UCPMP/OPPI compliance baseline
- Routing rules

### Step 4 — Using Prompt Files
In VS Code Copilot Chat, reference prompt files with `#`:

```
# In Copilot Chat, type:
#slide-kit Build a deck on Menopur POR data for the India advisory board

#compliance-audit Review this content: [paste your draft]

#kol-engagement Plan an advisory board on Rekovelle AMH-based dosing with 6 KOLs

#evidence-search Find all RCTs comparing hMG vs recombinant FSH in poor responders

#impact-evaluator Evaluate: "Monthly KOL newsletter programme"

#cme-design Design a case-based training on individualized dosing for IVF nurses

#value-story Build a budget impact model for Rekovelle vs Gonal-F in India

#strategy-brief Should we lead with Rekovelle or Menopur in Thailand launch?
```

### Step 5 — Copilot Agent Mode (VS Code)
In VS Code, switch Copilot Chat to **Agent mode** (the `@` dropdown):
- Agent mode lets Copilot read files, run terminal commands, and iterate
- Combined with your custom instructions, it becomes the MA agent
- It can search your repo for evidence files, build content, and check compliance

---

## Option 2: GitHub.com Copilot Chat

### Step 1
Push the `.github/` folder to your repo on GitHub.

### Step 2
Open **Copilot Chat** on github.com (sidebar or top bar).

### Step 3
The `copilot-instructions.md` is auto-loaded. Copilot Chat on github.com
will use the MA context for all responses in that repo.

### Step 4
Prompt files work with `#file:.github/copilot/slide-kit.prompt.md` syntax.

---

## Option 3: Any Other LLM (ChatGPT, Gemini, Claude)

### As Custom Instructions / System Prompt
1. Open `copilot-instructions.md`
2. Copy the entire contents
3. Paste into:
   - **ChatGPT**: Settings → Custom Instructions → "What would you like ChatGPT to know?"
   - **Gemini**: Use as system instruction in AI Studio or paste at start of conversation
   - **Claude.ai**: Use as project instructions or paste at start
   - **Any API**: Pass as `system` message

### As Per-Task Prompts
Copy any prompt file content and paste before your task description.

---

## Option 4: Copilot Extension (Advanced — Custom @agent)

For a dedicated `@menopur-ma` agent in Copilot Chat, you need a **Copilot Extension**.

### Architecture
```
GitHub Copilot Chat
  └── @menopur-ma (your extension)
        └── Your server (receives prompt, returns response)
              └── Reads prompt files + instructions
              └── Calls LLM API with MA context injected
```

### Minimal server (Node.js)

```javascript
// server.js — Copilot Extension endpoint
import { createServer } from "http";

const SYSTEM_PROMPT = `... contents of copilot-instructions.md ...`;

const PROMPT_FILES = {
  "slide-kit": `... contents of slide-kit.prompt.md ...`,
  "compliance": `... contents of compliance-audit.prompt.md ...`,
  // ... load all prompt files
};

createServer(async (req, res) => {
  if (req.method !== "POST") {
    res.writeHead(405);
    return res.end();
  }

  const body = await new Promise((resolve) => {
    let data = "";
    req.on("data", (chunk) => (data += chunk));
    req.on("end", () => resolve(JSON.parse(data)));
  });

  // Extract user message
  const userMessage = body.messages?.[body.messages.length - 1]?.content || "";

  // Detect which prompt file to activate
  let activePrompt = "";
  for (const [key, prompt] of Object.entries(PROMPT_FILES)) {
    if (userMessage.toLowerCase().includes(key)) {
      activePrompt = prompt;
      break;
    }
  }

  // Build messages for your LLM
  const messages = [
    { role: "system", content: SYSTEM_PROMPT + "\n\n" + activePrompt },
    { role: "user", content: userMessage },
  ];

  // Call your preferred LLM API (Claude, GPT, etc.)
  const llmResponse = await callLLM(messages);

  // Return as Copilot expects
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify({
    choices: [{ message: { role: "assistant", content: llmResponse } }],
  }));
}).listen(3000);

async function callLLM(messages) {
  // Replace with your preferred API
  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": process.env.ANTHROPIC_API_KEY,
      "content-type": "application/json",
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: "claude-sonnet-4-6",
      max_tokens: 4096,
      system: messages[0].content,
      messages: messages.slice(1).map((m) => ({
        role: m.role,
        content: m.content,
      })),
    }),
  });
  const data = await response.json();
  return data.content[0].text;
}
```

### Register as Copilot Extension
1. Go to **GitHub Settings → Developer Settings → GitHub Apps**
2. Create a new GitHub App
3. Enable **Copilot Extension** under the app settings
4. Set the endpoint URL to your server
5. Install the app on your account/org
6. In Copilot Chat, type `@your-app-name` to invoke

Full docs: https://docs.github.com/en/copilot/building-copilot-extensions

---

## Quick Start (fastest path)

1. Copy `.github/` folder to your work repo
2. Open repo in VS Code with Copilot
3. Open Copilot Chat
4. Type: `#slide-kit Build a Menopur POR deck for India KOLs`
5. It works. The MA context is already loaded.

---

## Updating

When portfolio knowledge changes (new trial data, new product, market entry):
1. Edit `.github/copilot-instructions.md` — update the Portfolio section
2. Add/edit prompt files in `.github/copilot/` for new workflows
3. Commit and push — all collaborators get the update automatically
