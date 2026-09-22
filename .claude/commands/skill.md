---
description: Extract the logic of a just-completed task into a reusable Skill
argument-hint: [skill-name]
---
Turn what we just did into a reusable Skill named **$ARGUMENTS**.
1. Extract the core, reusable logic (strip the one-off specifics).
2. Write it to `aios/skills/$ARGUMENTS.md` with: purpose, inputs, steps, owner archetype, gotchas.
3. If it's mature and repeatable, ALSO scaffold `.claude/skills/$ARGUMENTS/SKILL.md` so it gains autonomous invocation.
4. Note in `aios/router.md` under the Skills table.
