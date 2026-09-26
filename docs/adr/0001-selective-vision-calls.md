# ADR-0001: Use transcript-first, vision-on-demand video analysis

## Status

Accepted

## Context

FrameCutAI targets technical learning videos. These videos often have low
information density over time, but their screen content can be crucial: code,
terminal output, configuration files, architecture diagrams, UI state, and error
messages may appear visually even when the spoken transcript only gestures at
them.

A pure transcript summary is cheap, but it loses important screen evidence. Full
visual analysis is more complete, but it is too expensive and slow for normal
local-first use. Fixed-frame analysis is simpler than selective analysis, but it
spends vision calls on low-value sections and can still miss the precise visual
moment a technical explanation depends on.

The MVP needs to prove a narrower claim: FrameCutAI can preserve important
technical visual information while reducing unnecessary VLM calls.

## Decision

FrameCutAI will use transcript-first, vision-on-demand analysis.

The Workflow first turns speech or subtitle content into timestamped transcript
data, cuts it into Segments, and scores each Segment for technical density,
visual dependency, operation density, novelty, watch value, and confidence.
Only Segments with strong visual need are selected for Frame extraction and
OCR/VLM analysis.

Downstream Writer, Critic, QA, debug UI, and Eval Strategy code consume the
structured VideoContext created by this Workflow. They should not depend on
loose raw transcript text or untracked image files.

## Alternatives Considered

### Pure ASR

Pure ASR is the cheapest and simplest path. It can work for lecture-like videos
where spoken explanations contain nearly all important information.

It is insufficient for FrameCutAI's target technical videos because code,
commands, diagrams, UI states, and errors are often visible rather than spoken
in detail. Pure ASR also weakens traceability because generated claims about
screen content cannot be verified against Frame Evidence.

### Fixed-frame vision

Fixed-frame vision extracts Frames at a regular interval, such as every
30 seconds, and sends every selected Frame to OCR/VLM tools.

It is useful as a baseline because it is easy to implement and evaluate.
However, it spends visual calls on intros, repeated explanations, low-value
slides, and transitions. It can also miss the short interval where the important
configuration, command, or error appears.

### Full-frame or dense-frame vision

Full-frame or dense-frame vision samples very frequently or attempts to inspect
nearly all visual states.

It maximizes coverage, but its latency and cost are not acceptable for the MVP
and are not aligned with the product goal of cost-aware technical video
understanding.

### Selective vision

Selective vision uses transcript and Segment scoring to decide where visual
analysis is worth paying for.

It is more complex than pure ASR or fixed-frame analysis, but it directly fits
FrameCutAI's value proposition: use cheap text signals to choose expensive
visual calls, then preserve visual Evidence in VideoContext and generated
documents.

## Consequences

Positive consequences:

- The system can explain why a Segment was visually analyzed.
- Provider cost can be measured per Workflow and per Eval Strategy.
- Generated documents can cite both transcript and visual Evidence.
- The frontend debug panel can show Segment scores, Frames, OCR text, visual
  summaries, and Evidence summaries.
- The same Provider contracts support mock and real implementations.

Negative consequences and risks:

- Segment Scorer mistakes can skip important visual content.
- Fixed 60-second Segments can split context awkwardly.
- The Workflow is more complex than a pure transcript summarizer.
- Evaluation data is required to prove the strategy instead of relying on
  intuition.

Mitigations:

- Report missed visual Evidence in evaluation.
- Use Critic checks to flag missing Evidence and omitted high-value visual
  information.
- Keep fixed-frame analysis as a baseline strategy.
- Persist VideoContext after every major stage so failures and scorer decisions
  can be inspected.

## Validation Plan

The MVP will validate this decision with three Eval Strategies:

1. ASR-only.
2. Fixed-frame, using one Frame every 30 seconds and sending all selected
   Frames to vision.
3. Selective-vision, using Segment Scorer decisions.

Evaluation data should include questions with expected answers, Evidence
timestamps, a requires-vision flag, and a category. Reports should compare:

- Visual Evidence hit rate.
- Timestamp hit rate.
- VLM call count.
- Processing latency.
- Estimated cost.
- Manual correctness placeholders.
- Missed visual Evidence for selective-vision failures.

The decision is successful if selective vision covers the important visual
Evidence needed for technical questions while reducing unnecessary VLM calls
compared with fixed-frame analysis.
