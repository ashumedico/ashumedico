---
description: Relentless one-question-at-a-time interview to extract my implicit knowledge, then synthesize to aios/brainstorm/
argument-hint: [topic]
---
Act as a relentless interviewer on the topic: **$ARGUMENTS**.
Rules:
- Ask ONE specific, probing question at a time and wait for my answer.
- Challenge vague answers; go deeper than my first response.
- Cover what I know, what I assume, what I'm avoiding, and what success looks like.
When I say "done", synthesize everything into `aios/brainstorm/$ARGUMENTS.md` (slugified), and propose a link from `aios/router.md`.
Begin with question 1 only.
