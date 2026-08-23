# Project: Logic-Puzzle Translator + Solver

## Who I am
Freshman CS + Math student. Strong in Python and DSA (LeetCode/NeetCode
mediums+). This is my first real software project — I have no prior
experience with full-stack development, web frameworks, databases, or
deployment. I'm using this project specifically to learn full-stack and
general dev skills, not just to get it finished. Whenever you apply changes
relating to full-stack, give me a mini-lesson regarding how it works, etc.

## What I'm building
A web app where a user types an Einstein/Zebra-style logic puzzle in
plain English. An AI translates the messy sentences into precise,
formal constraints. A solver I build myself (guaranteed-correct,
algorithmic — not AI-based) solves the puzzle and shows a step-by-step
deduction chain explaining why each conclusion follows.

The core idea: AI handles language, a real solver handles logic. The AI
never solves the puzzle itself — it only translates English into a
structured format my solver can consume — because language models
can't be trusted to reliably solve multi-step constraint logic on
their own.

## Rough shape of the project (not locked in yet)
1. A pure-logic solver core, in Python: represent a puzzle, check
   whether an assignment breaks any constraints, search for valid
   assignments, and produce a step-by-step deduction trace.
2. Some way to expose that solver so a person can use it through a
   browser (I want to research and choose the specific web framework
   /tools myself — don't assume or default to a specific one unless I
   bring it up).
3. A layer that takes plain-English puzzle descriptions and turns them
   into the structured constraints my solver understands.
4. Eventually: deployed somewhere real, so other people can use it.

Treat this shape as a rough outline, not a fixed spec — I'm still
learning what my options are at each layer, and I want to make those
calls deliberately rather than have them decided for me.

## How I want you to work with me

### Simple Language: Speak to me like I'm a 5th grader
I cannot focus when reading a bunch of complex words, so I like very
simple english language used. Always default to clear explanations and
simple words when I need clarification on anything about the project.

### Priority: I need to understand everything, not just have it work
My goal is to be able to explain every part of this project in depth
in a technical interview. A working feature I don't understand is
worse than no feature at all. Please optimize for my understanding,
not for speed of completion. Also, after changes are made explain them 
in simple language and the implications of them.

### Before committing code
Before committing changes to core logic, make sure I've confirmed I
understand what's being committed and why. Don't commit core-logic
changes silently on my behalf. Setup/plumbing commits don't need this
check.

### New concepts and tools
When something new comes up (a library, a tool, a web dev concept,
a CS concept), explain it briefly in plain language before or as we
use it. I learn best by doing — minimum theory, then get me building,
then fill in more depth as needed through the work itself. Don't
front-load long explanations before I've touched the thing.

### Explaining code
Whenever you write or generate any code on my behalf (setup, boilerplate,
config, etc.), explain what it does in plain language as part of the
same response, so I'm never looking at code I can't account for.

### Code comments
- Add a concise comment above each function stating what it does
- Comment non-obvious lines briefly; skip comments on lines that are
  self-explanatory
- Keep comments short — a phrase or short sentence, not paragraphs