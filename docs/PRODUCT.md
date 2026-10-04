# Product

## Register

product

## Users

The primary user is an **NLP lecturer or grader**. They open the GUI once or twice, often in Colab or a local browser, to check that:

- every stage of the text-analysis and retrieval pipeline works;
- each stage's intermediate results can be seen and understood.

They know information-retrieval concepts, but not this project's code. They have limited time and will judge mostly from what the screen tells them, without reading the report alongside.

Secondary users are classmates and GitHub visitors trying the system briefly.

## Product Purpose

The GUI is the working front end of a classical search engine for video-game Wikipedia articles: tokenization, normalisation, a positional inverted index, a Boolean searcher, ranking and evaluation. It must:

1. work as a real searcher;
2. show the intermediate output of every stage (the "X-ray" of the pipeline);
3. compare the two pipeline designs, A and B;
4. expose the evaluation numbers.

**Success:** within a few minutes a grader understands what each tab demonstrates, can run a query end to end, and can see why the final pipeline was chosen.

## Brand Personality

Precise, calm, explanatory: a lab instrument that explains itself.

- **Copy states exactly what a control does and what the output means.** Every number is exact, and units are always shown.
- **No hype.** Plain-language hints sit next to technical labels, so a reader who knows IR is never talked down to and a reader who doesn't is never lost.

## Anti-references

- **The default Gradio demo.** Stock blue accents, and generic labels like "Text", "Show", "Encode", "Refresh" that say nothing about what happens.
- **A dense academic dump.** Walls of raw tables with no heading, no explanation of what the columns mean, and no indication of what to look at.

## Design Principles

1. **Show the pipeline working.** Intermediate results are the product; never hide a stage behind a single final answer.
2. **Every screen answers "what is this, and what should I notice?"** in one short line before the controls.
3. **One idea per tab, in the order the system runs.** Navigation follows the pipeline: input → processing → index → search → evaluation.
4. **Honest numbers.** Label preliminary results as preliminary, show measured times, and never decorate data.
5. **Consistent instrument language.** The same accent for the same pipeline everywhere (A terracotta, B slate, final ink), and the same component for the same kind of output.

## Accessibility & Inclusion

- **Contrast.** WCAG 2.1 AA: body text at least 4.5:1, large text at least 3:1.
- **Motion.** All motion respects `prefers-reduced-motion` (fades instead of movement).
- **Colour is never the only signal.** Pipelines are also named in text, and relevance marks have a legend.
- **Keyboard.** Every control is reachable by keyboard; Enter submits search fields.
