# FrameCutAI Context

FrameCutAI is a multimodal technical video understanding Agent. Its purpose is
to turn low-density technical learning videos into traceable technical documents
and current-video QA. It is not a generic video summarization platform.

The core product decision is transcript first, vision on demand: FrameCutAI uses
speech/transcript data to decide which parts of a video need visual
understanding, then calls OCR or VLM tools only for those high-value visual
segments. This keeps the important screen evidence from code, terminal output,
configuration files, diagrams, and UI state while avoiding full-frame visual
analysis cost.

## MVP Boundary

- Local video upload or mock samples first.
- Technical learning videos first, especially code, slides, terminal, browser,
  architecture diagrams, and operation walkthroughs.
- Current-video QA only.
- Mock Providers are acceptable for the first Workflow, but they must follow
  the same contracts as future real Providers.
- URL ingestion, browser extensions, long-term memory, historical-video
  retrieval, web retrieval, login, billing, and large-scale processing are out
  of scope for the MVP.

## Domain Vocabulary

### Video

A source video task owned by the local workspace. A Video has metadata,
processing status, local storage artifacts, task events, generated Documents,
QA logs, Provider call records, and a VideoContext.

Use `Video` when referring to the source media and its task identity. Avoid
using "file" or "upload" when the concept includes processing state and
derived artifacts.

### Segment

A time-bounded slice of a Video transcript. In the MVP, Segments are created
with fixed 60-second windows. Each Segment can carry transcript text, scoring
results, visual-selection decisions, Frame references, and Evidence summaries.

Use `Segment` for the unit that the Workflow scores, selects for vision, cites
in QA, and evaluates for timestamp coverage.

### Frame

A still image extracted or simulated from a Video at a specific timestamp. A
Frame belongs to a Segment. It can carry OCR text, a visual summary, and storage
path metadata.

Use `Frame` only for visual evidence captured from the Video timeline. Avoid
using it for arbitrary images that are not tied to a timestamp.

### VideoContext

The structured intermediate representation of a processed Video. VideoContext
combines Video metadata, Segments, Segment scores, Frames, OCR text, visual
summaries, Evidence summaries, Provider call references, and document-quality
signals.

Downstream Writer, Critic, QA, debug UI, and Eval Strategy code should consume
VideoContext rather than raw transcript text or loose image files. This keeps
the system traceable and testable.

### Evidence

Traceable support for a generated claim or QA answer. MVP Evidence should point
back to at least a Segment and timestamp. Important technical claims should also
include transcript snippets and, when visual information was used, a Frame path
or visual summary.

Use `Evidence` when the user can verify a statement against the source Video.
Do not present model guesses as Evidence.

### Provider

A swappable tool implementation used by the Workflow. Initial Provider families
are ASRProvider, LLMProvider, and VisionProvider. Mock Providers are first-class
implementations and must return the same structured shapes as future real
Providers.

Provider calls should be recorded so latency, tokens, audio/image units, and
estimated cost can be compared across strategies.

### Workflow

The controlled analysis process for a Video. The MVP Workflow is:

1. Upload or select a Video.
2. Run ASR or use mock transcript data.
3. Create Segments.
4. Score Segments.
5. Select visual Segments.
6. Extract or simulate Frames.
7. Run OCR/VLM or mock vision.
8. Persist VideoContext after each major stage.
9. Generate a traceable Markdown document.
10. Run Critic checks.
11. Serve current-video QA.
12. Feed Eval Strategies.

Use `Workflow` for this controlled sequence. Avoid describing the project as a
free-form autonomous agent that can choose arbitrary tools.

### Eval Strategy

A repeatable way to process the same evaluation data for comparison. MVP Eval
Strategies are ASR-only, fixed-frame, and selective-vision.

Eval Strategies should report visual Evidence hit rate, timestamp hit rate,
VLM call count, latency, estimated cost, and manual correctness placeholders.
Missed visual Evidence must be visible in reports.

## Source Provenance Rule

MVP QA answers come from current VideoContext only. If there is not enough
current-video Evidence, the answer should refuse clearly.

Future historical-video, memory, or web retrieval answers must label their
source type explicitly. Do not blend outside knowledge into a current-video
answer without provenance.
