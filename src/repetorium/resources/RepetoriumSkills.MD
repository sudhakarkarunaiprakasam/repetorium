---
name: repetorium-content-format
description: "Extract textbook content, design semester-scale courses, and convert user-provided learning material into a validated Repetorium content-pack ZIP."
---

# Convert content to Repetorium format

Use this skill to turn the user's source material into a complete Repetorium
learning pack. Own the concept mapping, pedagogical sequencing, prerequisite
graph, format validation, and ZIP packaging. Do not stop at a list of chapters
or topics: organize the mapped material into a coherent learning progression.

Use the supplied source as the primary basis for the pack and preserve its
meaning, terminology, evidence, and level of certainty. Use source wording,
examples, and exercises verbatim as much as the source's license or explicit
permission allows, and follow its attribution and adaptation terms. For
materials without a clearly permissive license, ask the user to confirm they
own the material or have permission to reproduce it in the pack. The user is
responsible for ensuring that confirmation is accurate. The in-app copyright
acknowledgment is not a substitute for this confirmation and does not grant
rights. If reuse is not authorized or remains unclear, do not reproduce
substantial passages, distinctive examples, or exercise wording: explain the
ideas in original wording and author new questions grounded in the material.
Do not make superficial edits to disguise copied passages or exercises.
Do not invent concepts or add prerequisite topics absent from the inspected
sources. When a teaching gap requires background knowledge, use reliable
additional sources, cite them separately, and distinguish that material from
the supplied source.

Adapt explanations to the requested learner audience and discipline without
changing the source's claims. When a source is too terse or assumes missing
foundations, add only the explanation needed to teach the outcome, using
reliable additional references and citing them separately; do not present those
additions as claims from the supplied source. When source material is too broad
or advanced for the requested audience, scaffold and prioritize it, and report
omitted detail or prerequisites rather than claiming complete coverage. Do not
guess answers from headings or invent facts that inspected sources do not
establish.

Use source exercises as evidence of intended practice. Include an original
exercise only when the source's license or explicit permission allows it and
the exercise is pedagogically useful; otherwise author a new, answerable
question from source-supported concepts, examples, figures, tables, or learning
objectives. Verify every answer from the material and flag newly authored
practice in the completion note.

Use subject-matter reasoning to make the pack teachable, not merely to
transcribe the source's headings. Infer prerequisite relationships among mapped
skills using the source's order and examples together with reliable domain
knowledge. A dependency need not be explicitly labelled "prerequisite" when the
source's explanations, examples, tasks, or progression make it clear. Do not
add unmapped prerequisite topics or present outside facts as claims from the
supplied source; report genuine gaps.

## Workflow and revision guardrails

- Start with one scope checklist: source and rights, intended audience, included
  sections, outcomes, and deliverables. For a large source, process bounded
  chapter/section batches and maintain the coverage ledger; do not restart the
  whole source review to fix one local issue.
- Draft once, then do one grouped quality review and one grouped
  schema/validation repair pass. Make additional edits only for a concrete
  source, teaching, user-requirement, or validator defect—not for subjective
  rewording of already adequate content. Do not re-open passing items without
  new evidence.
- Batch related corrections before rerunning checks. Run the full app validator
  once against the final extracted pack. If it fails, fix the reported issues
  together and rerun once. If the same issue persists after that repair pass,
  stop and report it as unresolved; do not repeat the same edit/validation loop.
- Stop when the requested scope is covered, required checks pass, and the ZIP
  is verified. For work too large for one pass, deliver a clearly labeled WIP
  batch with done, pending, and blocked items instead of lowering quality or
  claiming completion.

## Deliverable

When the provided content can be represented faithfully, create one ZIP archive
named `repetorium-content-pack.zip`. Its root must
contain `library.yaml` and the content directories directly, not an extra
wrapping directory:

```text
library.yaml
INFO.md                           # required for newly created packs
graph/*.yaml
banks/*.yaml                      # when bank_* generators are used
lessons/*.yaml                    # optional guide sidecars
cases/*.yaml                      # optional applied cases
repetorium-export.json            # optional; generated by Repetorium exports
```

Create a root-level `INFO.md` for every new pack. This is the pack's durable
purpose and status document; do not omit it even when the manifest and skills
seem self-explanatory. Include these sections:

1. **Purpose** — what problem or learning need the pack is intended to solve,
   the intended learner, and the intended use.
2. **User intent** — why the user asked for this pack, based on their stated
   request. Do not invent a motivation. If it was not explicitly stated, say
   that and label any brief interpretation as inferred.
3. **Contents and scope** — subjects and learning outcomes covered, number of
   skills, lesson files/guides, applied cases, and other included learning
   materials. Note important omissions or source limitations.
4. **Metadata** — creation date and, when changed, last-updated date in
   `YYYY-MM-DD` format; pack version copied exactly from `library.yaml`; and
   status (`Complete` or `WIP`). Keep the version synchronized with the
   manifest.
5. **Lesson inventory** — report the number of lessons as the number of graph
   skills with nonempty `lesson` content (one skill lesson counts once,
   regardless of how many passages it contains). Report guide sidecars
   separately; they are not additional lessons.
6. **Quiz inventory** — report the total number of distinct authored question
   bank entries and counts by their actual item `type` (`choice`,
   `multi_select`, `matching`, `order`, `true_false`, or `numeric`). Also report
   the number of skills by registered
   generator. Do not count randomized runtime variants as authored questions;
   state when procedural generators create additional questions that cannot be
   given a finite question count.
7. **Work status** — for a WIP pack, include separate **Done**, **Yet to
   implement**, and **Needs attention** lists. Be specific about incomplete
   lessons, questions, source coverage, validation, or known uncertainty. For
   a complete pack, explicitly say if no known work remains or needs attention.

Recount these inventories once after the final content edit. Base claims and
counts on the actual files in the archive; distinguish verified facts from
inference and report unknowns instead of guessing. Include `INFO.md` and only the mapped
Repetorium library files in the archive, not unrelated source documents. The
archive is a Repetorium content library, not an installer. Import it from
Library.
Repetorium validates it and installs it in the local content-pack library.
Choose it in Settings to practice it alone or combine all installed packs for
mixed practice. Direct local authoring remains available by extracting a pack
and setting `REPETORIUM_CONTENT_DIR` before launch.

Use either an LLM interface (such as ChatGPT or Claude) or an AI coding agent
(such as Copilot or another IDE agent); the deliverable rules are the same:

- In an LLM interface, create the actual files and attach the ZIP only if the
  interface can create it. Use the format rules and manual checks in this file;
  this skill does not include a standalone `validate_library` tool, so do not
  expect an LLM interface to call that Repetorium project function. Run a YAML
  parser and ZIP integrity check only if suitable tools are available. State
  that app-level validation was not run; do not imply that a code block or
  proposed file listing is an attached, validated ZIP.
- In an AI coding agent, inspect the current Repetorium schema and run the
  project's validator on the final extracted ZIP once, if the project and its
  dependencies are available. Do not assume generator names or schemas from
  memory.
- In either workflow, report what was created, what validation actually ran,
  and any source or exercise gaps. Never report a successful import unless the
  pack was actually imported.

Do not create `repetorium-export.json` during conversion. Repetorium adds this
optional snapshot when the user exports from the app. It records a point-in-time
dashboard, mastery/review progress, streak, daily XP/study totals, lifetime
totals, Skill Map, and Learn view; it contains no question-level attempt
history, raw answers, or personal notes. After importing, the user can choose
to restore saved skill states and daily progress. Existing XP and lifetime
study-time totals are not reduced.

## Content requirements

- Map the important learnable concepts from the supplied material, preserving
  stable IDs when they still represent the same learning outcome. Do not reuse
  an old ID for a substantially different or newly narrowed outcome; progress is
  attached to skill IDs.
- Treat the book as a curriculum, not just a bibliography. Read the instructional
  material, examples, figures, tables, exercises, and chapter progression; order
  the mapped concepts so learners encounter foundational ideas before concepts
  that build on them. Use chapter order as evidence, but improve it when the
  source supports a clearer teaching sequence.
- A chapter is a container, not a skill. Do not collapse a chapter with several
  numbered sections, learning objectives, or distinct mechanisms into one
  chapter-sized skill. Split it into small, assessable outcomes: a learner
  should be able to tell what they can explain, distinguish, interpret, or do
  after mastering one skill. Give every substantive section at least one mapped
  outcome and split broader sections further when they teach separable ideas.
  Combine material only when it supports the same outcome; do not create tiny
  skills for every definition or heading.
- Infer `prereqs` between mapped skills when understanding or performing one
  depends on another skill taught in the source. This is an allowed pedagogical
  inference, not an invented concept. Keep edges within the pack and do not add
  missing prerequisite topics as skills. Avoid false dependencies: shared
  subject area or chapter proximity alone is not enough.
- Treat the prerequisite Skill Map as a required part of a useful multi-skill pack, not
  an optional visualization. A coherent book-derived curriculum must have a
  meaningful prerequisite progression: when the material contains a sequence
  of three or more dependent concepts, encode at least one prerequisite path
  spanning three or more mapped skills. Attach skills to that progression only
  through real prerequisite dependencies. Do not add Concept Links or other
  non-prerequisite edges to make the map look more connected. Preserve
  genuinely independent foundations and strands as separate roots or
  components, and explain them when useful; never invent a prerequisite just
  to connect the graph.
- Write each skill's `lesson` as a coherent, self-contained teaching session.
  Do not force every subject into the same lesson template or word count.
  First establish the learner audience, prior knowledge, discipline, and one
  assessable outcome; then choose the sequence, examples, practice, and level
  of detail that fit. Use as many ordered `lesson` passages as needed, with
  transitions that make the reasoning easy to follow. Keep each skill focused
  on one outcome; do not merge unrelated skills or add filler.
  Teach in a clear instructor's voice. Make the outcome understandable, define
  terms when needed, explain the core reasoning, and include a source-grounded
  demonstration or worked example when it suits the subject. Add guided
  practice, a retrieval check with feedback, contrast, counterexample, or
  misconception correction when each serves the outcome; none is a universal
  checklist. Connect genuine prerequisites and finish with an appropriate
  synthesis or application. For narrow outcomes, write the strongest complete
  lesson the evidence supports and report limitations.
  Mix prose with subject-appropriate, source-grounded illustrations whenever
  they clarify the idea: use the supported `math`, `code`, `table`, and `chart`
  blocks when they help learners inspect a derivation, example, data, or model.
  Explain what each visual shows and how to interpret it; do not add decorative
  or unsupported illustrations, claim to include image types the app cannot
  render, or invent evidence. Maintain transitions between passages so the
  lesson reads as one coherent teaching session rather than disconnected
  fragments. Preserve source distinctions and cite the sources used. Any
  independent background used to fill a teaching gap must be cited separately
  and not attributed to the supplied source.
  End every source-based lesson with a final prose item such as
  `Source: Author, *Book Title*, edition, Chapter 3, §3.2, pp. 45-48.` Include
  only verified details; use a section or heading instead of page numbers when
  the source has no stable pagination. Keep the same citation in the skill's
  `sources` list so it is available outside the lesson too.
  `lesson` remains an ordered list and may mix prose strings with typed display
  blocks (`text`, `math`, `code`, `table`, or `chart`). Use a math block for a
  central derivation, code block for source-grounded code or pseudocode, and
  tables/charts for evidence learners need to inspect. Add the surrounding
  explanation in prose: a visual is not a substitute for defining terms,
  guiding interpretation, or explaining what conclusion the evidence supports.
  Lesson prose supports inline `**bold**` for short section labels (for example,
  `**Worked example.**`); use it sparingly. Do not rely on other Markdown
  syntax such as heading markers or bullet lists inside a prose passage. Put
  separate prose passages in separate `lesson` list items and use typed blocks
  for structured content.
  Tables require `headers` and equally sized `rows`. Charts require a `chart`
  mapping with `type: bar`, `line`, or `scatter`, a `title`, nonempty `labels`,
  and one or more `series` mappings with a `name` and one finite numeric
  `values` entry per label; optional `unit` and `x_unit` should make the scales
  explicit. Scatter labels must be numeric. Negative values are supported.
  Code is displayed as inert, selectable monospace text and is never executed.
- Create at least 5 sound practice questions per skill when the source can
  support them. Aim toward 20 when the user's scope, available evidence, and
  work budget support that quality; 20 is a target, not a reason to delay a
  complete first pass or add filler. This is the reusable pool for regular
  practice and skill-aligned mock exams, not 20 questions in every exam. For a
  large pack, first complete each in-scope skill with its lesson and minimum
  sound pool, then expand pools in planned batches. Mark unfinished expansions
  WIP instead of generating a huge low-quality pool in one pass. Vary the thinking
  required: recall with explanation, interpretation of evidence or examples,
  application to a new scenario, comparison, misconception diagnosis, and
  transfer where the source supports it. Explanations should make the reasoning
  checkable, not merely repeat the answer. Give each bank-backed skill its own
  bank. Do not count cosmetic rewordings or trivial number changes as distinct.
  Do not treat the source book's exercises as a limit: when it contains fewer
  than five ready-made questions, write original questions from the mapped
  outcomes, explanations, worked examples, figures, and supported applications
  to build a useful pool toward 20.   Reuse textbook questions or explanations only when the source's terms or
  explicit permission allow it; otherwise author new questions and explanations
  without superficial paraphrase. Do not introduce unsupported facts. If the
  source cannot support five sound questions even with original, source-grounded prompts, combine
  the skill with a related outcome or report the coverage gap; never pad with
  guesses.
- Treat multiple-choice writing as assessment design, not answer-key formatting.
  Distractors must be plausible, distinct misconceptions grounded in the source;
  never use absurd, irrelevant, or obviously incomplete alternatives. Keep all
  options parallel in grammar, specificity, technical detail, and approximate
  length. Do not make the correct response systematically longer, more qualified,
  more precise, or more polished than its distractors. Avoid clues from grammar,
  repeated stem wording, absolutes, uniquely technical vocabulary, punctuation,
  formatting, or option position. Randomizing option order does not remove
  wording or length cues. Do not add meaningless filler just to equalize
  lengths; instead rewrite the whole option set so every option is comparably
  clear and plausible. This is especially important for diagnostic banks:
  guessing based on writing cues can falsely place a learner into skills they
  have not demonstrated.
- Before finalizing, run automated structure and option-length checks over all
  choice entries when suitable tooling is available. Perform one adversarial
  human review with explanations hidden: review every choice item in a pack of
  up to 60 choice entries; for larger packs, review a stratified sample of at
  most 60 across skills, subjects, and difficulty levels. Look for length,
  grammar, detail, prompt-wording, and absolute/technical-phrase cues. Expand
  the review only when the sample or automated check shows a repeated defect.
  Where practical, test longest-only and shortest-only strategies across the
  full bank and difficulty levels; compare performance with the chance baseline
  (mean of `1 / option_count`). Treat this as a warning check, not proof of
  validity. Batch concrete fixes once, then stop when checks pass; do not keep
  rewriting items for subjective variation.
- Preserve citations, licensing facts, and source locations when supplied.
  Record only known details; do not infer editions, licenses, page numbers, or
  coverage. A citation or in-app acknowledgment is not permission to reproduce
  material.
- Cases are an application method, not a subject area. Map a case only when the
  provided content and target schema contain the necessary information.
- Choose teaching and assessment from the discipline's actual methods of
  reasoning, evidence, and practice; do not reuse the same lesson voice or
  example pattern across subjects. Mathematics benefits from explicit
  assumptions, notation, derivations, worked examples, gradually reduced
  scaffolding, units, and reasonableness checks. Natural sciences should
  distinguish observation from inference and teach models, measurement,
  uncertainty, experimental methods, and interpretation of data. Statistics
  should make sampling, variability, assumptions, and limits of inference
  visible. Computer science should use source-grounded, display-only code for
  tracing state, invariants, debugging, or comparing complexity; Repetorium
  does not execute learner or pack code. Business and finance should state
  assumptions, periods, units, evidence, and scenario constraints, then connect
  calculations to interpretation and trade-offs. Humanities and social sciences
  should situate claims in time and context, examine evidence and methods,
  distinguish causation from association, and represent competing
  interpretations fairly. Language learning should use meaningful contexts,
  contrasts in form and meaning, and usage feedback; do not imply the app can
  assess pronunciation or listening. Product management and design should
  assess prioritization, trade-offs, user evidence, and critique against stated
  constraints. Writing instruction should teach audience, purpose, structure,
  and revision decisions without implying the app grades essays. Select
  `domains` honestly when an outcome spans fields.
- Match assessment to what the software can actually grade: numeric responses,
  single choice, ordering, multi-select, matching, and true/false. Free-form
  short-answer and fill-in-the-blank response types are not supported because
  their current grading is not reliable enough. Select formats to fit the
  discipline and learning outcome, and use `bank_mixed` when several formats
  are valid so practice does not default to all multiple choice. These formats
  can test interpretation and reasoning when prompts provide enough evidence,
  but they are not equivalent to grading an essay, proof, open-ended analysis,
  or executable program. Do not claim an unsupported outcome is covered merely
  because it can be approximated with a selected-response question; report
  such limitations for the pack.

## Textbook extraction and semester-scale course design

For a request to make a university-semester course, use the supplied book as the
source for a teachable course rather than making a chapter index. Unless the
user specifies a narrower scope:

1. Establish the book's title, edition, authors, stated license, page count, and
   full table of contents. Work from the actual text, not just its title,
   abstract, contents page, or chapter summaries. For a long PDF, process one
   chapter or a few sections at a time and keep a temporary coverage ledger
   outside the ZIP. Record each section/page range, its learning objectives and
   key concepts, the evidence/examples inspected, and the resulting skill IDs.
2. Plan about 12-16 weekly modules for a 12-16-week survey course. A useful
   initial planning range is roughly 3-5 assessable skills per week (about 50-80
   skills overall); adapt to actual scope and difficulty, and explain large
   deviations. This is a coverage sanity check, not a quota: never add filler
   skills to meet a number or claim that page count alone establishes a
   semester's workload.
3. Map each substantive numbered section's distinct learning outcomes. For a
   chapter with several sections, expect several skills, not one chapter-level
   node. Use short measurable titles such as "Separate Sensation and
   Perception" or "Separate Correlation and Causation"; put the explanatory
   detail in the lesson, not the title. Merge the course sequence into weekly
   modules in the completion summary; do not add unsupported fields or files
   to the ZIP schema.
4. For each skill, write the complete, source-grounded lesson described above
   and an initial pool of at least five sound questions when the source supports
   them; cite the
   precise chapter/section and page range in `sources`. Questions must be
   independently answerable from the inspected source, with plausible
   misconceptions as distractors and feedback that explains why the answer
   follows. Include cumulative or cross-section applications after the
   component concepts have been taught. Expand pools toward 20 in later planned
   batches when scope and evidence permit; do not generate every target pool in
   one pass at the cost of lesson quality or factual review.
5. Audit the ledger against the source: every in-scope section and major learning
   objective is accounted for; every skill has source evidence, lesson content,
   practice, and a defensible place in the sequence. Report excluded chapters,
   unreadable or uninspected portions, thinly supported topics, and any
   shortfall from the intended course scope plainly.

These targets improve course completeness; they do not certify that the pack is
equivalent to a university course, replace an instructor or syllabus, or prove
learning outcomes.

## Learning-science choices

Use the evidence to shape practice, not to decorate a pack with research terms:

- Put an attempt to retrieve or reason before revealing the answer, and give
  corrective feedback that explains the evidence and reasoning. Keep questions
  low-stakes and use varied, spaced returns to earlier skills rather than
  treating one short practice streak as durable mastery.
- Build each skill on prerequisite knowledge, then ask learners to explain
  mechanisms, compare close alternatives, inspect counterexamples, and apply
  ideas in a changed context. Retrieval and explanation support learning, but
  performance on familiar questions alone does not establish transfer.
- Follow source examples with new, original applications. State what changes
  from the worked example and what stays the same; do not make an analogy stand
  in for evidence that two concepts are identical.

These choices are informed by [Dunlosky et al. (2013)](https://doi.org/10.1177/1529100612453266),
which rates practice testing and distributed practice as useful techniques;
[Roediger and Karpicke (2006)](https://doi.org/10.1111/j.1467-9280.2006.01693.x),
whose prose-learning experiments found a delayed-retention advantage for
repeated testing; and National Academies syntheses on
[learning and transfer](https://doi.org/10.17226/9853) and
[knowledge and reasoning](https://doi.org/10.17226/24783). This is a selective
design synthesis, not a systematic review. These findings do not prescribe an
exact number of skills or questions, guarantee transfer, or prove that a pack is
a complete course.

## Manifest and skill files

`library.yaml` must be a YAML mapping with `format: 1`, a unique `id` (letters,
digits, dots, underscores, or hyphens; maximum 80 characters), nonempty `name`
and `version`, and a `sources` list of nonempty citation strings. Example:

```yaml
format: 1
id: sample-library
name: Sample Library
version: "1.0.0"
sources:
  - "Author, Title, edition, chapters reviewed; coverage notes."
```

Each `graph/<category>.yaml` is a YAML list of skills. Every skill needs a
unique stable `id`, nonempty `title`, and a registered `generator`. Keep
existing IDs and generator choices when supplied. Include
`domains` when a skill belongs to multiple subjects, `sources` for concept-level
citations, `prereqs` only for real learning dependencies, and `lesson` as an
ordered list of substantial prose sections and optional typed display blocks
that form the complete lesson. Existing packs using only lesson strings remain
valid.
Existing subject-specific generators or the built-in `bank_choice`,
`bank_order`, `bank_classify`, and `bank_mixed` generators may be used. Prefer
`bank_mixed` when a skill supports more than one defensible assessment format;
it lets the learning engine balance the available formats instead of repeating
one response style. Content cannot define generators or execute code. Never
choose a bank generator as a placeholder for a topic: it must have a real bank
file and complete, source-grounded exercises.
For every bank-backed skill, set `params.bank` to the exact bank filename stem;
the referenced file must exist under `banks/`. A skill with no usable exercise
is not import-ready, even if it has a title, lesson content, and citations.

Use only these skill fields: `id`, `title`, `generator`, `params`, `prereqs`,
`encompasses`, `similar`, `lesson`, `xp`, `guide`, `domains`, and `sources`.
The graph filename supplies the skill's `category`; do not add a `category`
field. Do not add `notes`, `description`, or other undocumented keys: the app
constructs skills from this schema and rejects unknown fields. Put conversion
notes, including whether exercises were newly authored, in the completion
message outside the ZIP. Put source citations in `sources`.

### Naming skills, lessons, and categories

Titles are short learner-facing labels in the Learning Plan, practice, and the
Skill Map; they are not descriptions. Make each one concise, specific, and
understandable on its own:

- Give a skill a compact label, usually an action verb and its object, such as
  "Compare business models," "Trace recursive calls," or "Revise for clarity."
  Aim for 2-4 words and no more than 35 characters; use a fifth word only when
  it is needed to distinguish the outcome. A title names what the skill is
  about; it must not read like an instruction, sentence, or summary. Do not
  include explanations, examples, conditions, or steps in the title; put those
  in the lesson. Distill long source headings instead of copying them. Avoid
  chapter numbers, generic openers like "Introduction to," and filler such as
  "Understanding of."
- Name each graph category with a short subject-area label, usually 1-3 words.
  Use a concise `snake_case` filename such as `corporate_finance.yaml`; the app
  displays it as "Corporate Finance." Avoid long hyphenated headings or
  repeating a shared book or course name in every category.
- Keep lesson section labels short (typically 2-5 words) and descriptive. The
  lesson itself should remain complete and detailed; concise labels are not a
  reason to omit explanation.
- Keep the library `name` and other learner-facing labels short enough to scan
  in the app. Preserve a stable skill ID when only refining its wording and the
  learning outcome has not changed.

Question levels, time, and XP are assigned by the app, not authored as
per-question estimates. Generated question difficulty is 1 (Easy), 2 (Medium),
or 3 (Hard); the app maps these to estimates/rewards of 2 minutes/1 XP,
3 minutes/2 XP, and 5 minutes/3 XP respectively. Mixed quizzes adapt their
difficulty to demonstrated repetition; mock tests let learners select a level.
Suggested test time sums the level estimate for each selected skill and rounds
up to a 5-minute increment; learners may change the duration.
Make generators and banks produce questions whose reasoning demand genuinely
matches the requested difficulty. For bank entries, set `difficulty` to 1, 2,
or 3; if using explicit difficulty tags, include questions at all three levels.
Vary distractor plausibility, number of reasoning steps, and transfer demand
without making harder questions depend on untaught material. The skill-level
`xp` field is a mastery reward, not a question-level XP value. Do not add
unsupported time or XP keys to skills or bank entries.

## Prerequisite graph

The Skill Map's learning sequence is defined by `prereqs`. `domains` only
classify and filter skills; they do not create learning dependencies. Do not
create `connections.yaml` or add Concept Links: this workflow uses justified
prerequisites to show what learners should master first. A prerequisite means
the learner benefits from mastering that mapped skill first; the book does not
need to literally label it as a prerequisite.

Build a coherent, acyclic progression across the book: foundational skills
should be roots, and each skill that builds on earlier material should name the
relevant earlier skill or skills in `prereqs`. Do not leave every skill as an
unconnected root when the source supports real dependencies. Do not make a
simple chapter-order chain either: add only meaningful dependencies, allow
parallel branches, and do not force unrelated topics into a false prerequisite
relationship. Keep genuinely independent strands as separate roots or
components. For a textbook with a coherent sequence of at least three
dependent skills, the prerequisite DAG must contain at least one explicit path
of three or more skills. This is a minimum check, not a target to stop at:
build the full branching progression supported by the material. A linear
chapter extraction with no edges, or a graph where every skill is a root despite
clear dependencies, is incomplete.

Example of the shape of a justified prerequisite spine in a chapter graph file:

```yaml
- id: identify-input-output
  title: Map Inputs and Outputs
  generator: unit_rates
  prereqs: []
- id: define-function
  title: Test for Functions
  generator: unit_rates
  prereqs: [identify-input-output]
- id: evaluate-function
  title: Evaluate Function Rules
  generator: unit_rates
  prereqs: [define-function]
```

This illustrates only the relationship shape; use a generator and content
appropriate to each real skill. Do not copy this example as subject content or
add an edge unless mastering its prerequisite genuinely supports the dependent
skill.

Before packaging, inspect the whole graph as a learner-facing map, not just as
valid YAML: every skill should either be a justified foundation or have at least
one real prerequisite; every mapped skill should appear in the intended learning
sequence; and disconnected strands should be intentional, not an omission.
Check the number of roots, prerequisite path lengths, and connected components
using prerequisite edges only. For a coherent multi-skill textbook curriculum,
confirm the three-skill prerequisite path above and that each dependent strand
is attached to the progression by real prerequisites. Separate components are
acceptable when they represent genuinely independent strands. Do not add
Concept Links or invent prerequisites to make a component appear connected.
Explain any independent strands or unresolved sequencing gap in the completion
message. Never add a prerequisite concept that is not in the source to make the
graph appear complete.

Bank-backed skills need `params.bank` naming a matching `banks/<name>.yaml`
file. Author original bank questions from the source's supported concepts and
mapped outcomes; the source does not need to provide ready-made exercises. Use
new scenarios and wording, and ground each answer, explanation, and distractor
in supported material. Do not copy textbook questions or invent facts, correct
answers, or options that the source cannot support:

```yaml
# bank_choice; `explain` is required even when the source textbook has no answer key
entries:
  - prompt: "A report finds an association between X and Y but no controlled intervention. Which claim follows?"
    correct: "X and Y vary together in the reported observations."
    distractors:
      - "X causes Y in the reported observations."
      - "Y causes X in the reported observations."
      - "X and Y are unrelated in the reported observations."
    explain: "The report establishes an association, not a causal direction or absence of relationship."
    follow_up_prompt: "Optional, distinct transfer question."
    difficulty: 2
    exhibits:
      - type: table
        caption: "A small, source-grounded data set"
        headers: ["Group", "Result"]
        rows: [["A", 12], ["B", 18]]
```

The optional `exhibits` list can also contain `text`, `math`, `code`, and `chart`
blocks. Use the same typed block shapes as in lessons:

```yaml
lesson:
  - "First explain the quantities and assumptions in prose."
  - type: math
    content: "y = mx + b"
  - type: code
    language: python
    code: |
      values = [2, 4, 6]
      mean = sum(values) / len(values)
  - type: table
    caption: "Observed values"
    headers: ["Trial", "Result"]
    rows: [[1, 2.1], [2, 3.9]]
  - type: chart
    chart:
      type: scatter
      title: "Result by trial"
      x_unit: "trial"
      unit: "units"
      labels: ["1", "2"]
      series:
        - name: "Measurement"
          values: [2.1, 3.9]
```

Put equations that are
central to a question in a `math` exhibit; use inline math in prompt/options
when it is short. A code exhibit is display-only and must not contain a request
to execute it. Charts use the validated `chart` mapping described above. Math
blocks use Repetorium's safe lightweight notation renderer, not full LaTeX; use
common supported operators/symbols, or explain unsupported notation in prose.

```yaml
# bank_order
entries:
  - prompt: "Order these steps for the stated task."
    steps: ["First step", "Second step", "Third step"]
    explain: "Explain why this order follows from the underlying method."
    difficulty: 2
```

```yaml
# bank_classify
prompt: "Classify each item using the stated categories."
categories: ["Category A", "Category B"]
items:
  - text: "A specific item"
    category: "Category A"
    explain: "The item has the defining property of Category A."
    difficulty: 2
```

For a subject or skill that supports several ways of demonstrating learning,
use `generator: bank_mixed` and give every entry a `type`. The engine favors
response types used less recently for that skill, while choosing only among
formats and difficulty levels actually present in its bank. Include formats
only when they test the outcome fairly; aim for at least three supported types
across a broad pool, distribute them across difficulty levels, and do not force
a format that does not suit the subject or source. Example entry shapes:

Every `bank_mixed` entry, including a multiple-choice entry, must have an
explicit `type`. A choice-shaped entry without `type: choice` is invalid. The
`bank_choice` generator accepts only choice questions; it cannot host
`multi_select`, `order`, or other response types just because those entries
have a `type` field. If one bank contains more than one response type, use
`bank_mixed` and declare the exact type on every entry. Do not mix the
`bank_choice`/`bank_order` schemas with the `bank_mixed` schema.

```yaml
entries:
  - type: choice
    prompt: "Which claim follows from the stated evidence?"
    correct: "The supported claim"
    distractors: ["A plausible overclaim", "A competing explanation"]
    explain: "The evidence supports the claim but not the stronger alternatives."
  - type: numeric
    prompt: "What is the percentage change?"
    answer: 12.5
    unit: "%"
    abs_tolerance: 0.2
    explain: "Subtract the starting value, divide by it, then convert to percent."
  - type: order
    prompt: "Order the steps in the stated method."
    steps: ["Establish the baseline", "Apply the change", "Check the result"]
    explain: "The baseline is needed before applying and checking the change."
  - type: multi_select
    prompt: "Select every assumption stated in the scenario."
    correct: ["Demand stays constant", "The period is one year"]
    distractors: ["The price doubles", "Costs are ignored"]
    explain: "Only the first two conditions are stated in the scenario."
  - type: matching
    prompt: "Match each term to its definition."
    pairs:
      - left: "Revenue"
        right: "Income from sales before costs"
      - left: "Profit"
        right: "Revenue after costs"
    explain: "Revenue is measured before costs; profit accounts for costs."
  - type: true_false
    prompt: "Under the stated assumptions, does the conclusion follow?"
    answer: false
    explain: "The evidence does not establish the required condition."
```

`short_answer` and `fill_blank` are no longer supported; validation rejects
banks that contain either type. Convert an outcome to a supported objective
format only when that format assesses it fairly; otherwise report that the
software cannot grade it faithfully. Multi-select entries require a nonempty `correct` list and distinct
`distractors`. Matching entries require at least two unique `left`/`right`
pairs. True/false `answer` values must be YAML booleans. Numeric answers must
be finite numbers; optional `unit`, `tolerance`, and `abs_tolerance` define
their display and grading. Field names depend on the response type: choice uses
a string `correct` and a list of `distractors`; numeric and true/false use
`answer`; order uses `steps`; multi-select uses
lists for both `correct` and `distractors`; matching uses `pairs`. Do not
substitute one type's fields for another's. Every mixed entry also needs
`prompt` and `explain`; the usual `difficulty`, `follow_up_prompt`, and typed
`exhibits` are supported.

Use a nonempty bank with distinct options/categories. Every bank question must
include a nonempty `explain`, whether based on an authorized answer key or
independently derived from source-supported principles and data. Do not copy
protected solution prose without permission. The source need not provide an
answer key: independently solve and verify each original question, show the
key reasoning (including assumptions, units, intermediate steps, and checks
where relevant), and cite the supporting source. Do not present an inferred
answer as source fact. If the inspected source cannot establish one defensible
answer, revise the prompt to supply the missing assumptions or evidence, or
omit and report it; never guess, fabricate an answer key, or silently skip
feedback. Set each entry's
`difficulty` to 1 (easy), 2 (medium), or 3 (hard); tagged entries are selected
only at their assigned level. Every level must have a usable question: if all
entries are tagged, include at least one entry at each of 1, 2, and 3. Untagged
entries are eligible as a fallback only for difficulty levels without a
matching tagged entry. If no entry has a difficulty tag, the full bank is used
at all levels. Preserve useful supplied
explanations and follow-up prompts, but author original ones when the source
supports them. Do not invent source facts to make a bank appear complete.
`bank_choice` entries need a prompt, correct answer, and at least one
distinct distractor. `bank_order` entries need a prompt and at least two
distinct steps. `bank_classify` needs a prompt, at least two distinct
categories, and items whose category matches one of them. `bank_mixed` entries
must use one of the documented types and its exact shape. Do not add an entry
with guessed answers merely to satisfy validation. Before packaging, check each
bank against the generator assigned to every skill that uses it; do not repair a
mixed-type bank by changing only its YAML entries while leaving a
`bank_choice` generator selected.

Guide sidecars in `lessons/*.yaml` map skill IDs to concise companion guides.
The field types are strict:

- `definition` and `when_to_use` are each a single, nonempty YAML string.
- `steps`, `example`, and `pitfalls` are each a nonempty YAML list of strings.
  Even one example must be written as a list item, not a scalar.
- `decision_tree` is a nonempty YAML list of mappings. Every mapping has
  nonempty string fields `question`, `yes`, and `no`.

For example, this guide has the required structure:

```yaml
pc-functions:
  definition: "A function assigns each input in its domain exactly one output."
  when_to_use: "Use this test when deciding whether a relation defines a function."
  steps:
    - "Identify the inputs and their paired outputs."
    - "Check whether any input is paired with more than one output."
    - "Check that every input in the stated domain has an output."
  example:
    - "In {(1, 2), (2, 2)}, each input has exactly one output, so the relation is a function."
  pitfalls:
    - "Different inputs may share an output; that alone does not violate the function definition."
  decision_tree:
    - question: "Does any input have more than one output?"
      "yes": "It is not a function."
      "no": "Check that every input in the stated domain has an output."
    - question: "Does every input in the stated domain have an output?"
      "yes": "Each input has exactly one output, so it is a function."
      "no": "It is not a function on the stated domain."
```

Do not write `when_to_use` as a YAML list or `example` as a scalar; both forms
fail import validation. Quote the `"yes"` and `"no"` keys: unquoted, YAML reads
them as booleans and import fails. Make every guide specific to its skill and consistent
with its full lesson: use the concept's actual notation, conditions, steps, and
a worked example with a checked result. Avoid repeating generic filler such as
"identify the relevant quantities" or "set up a small example" across skills.
Decision questions should test a real choice or condition for that concept,
not a generic yes/no prompt. Guides supplement rather than replace the full
lesson in `lesson`. If the source does not support a precise guide, omit that
guide instead of inventing one. All referenced skill IDs, prerequisites, cases,
and assessments must exist in the archive.

## Mock tests

Do not author a prebuilt mock-test list or require
`assessments/mock_tests.yaml`. Learners build each mock test in the app by
searching for and adding skills; the app generates one question per selected
skill at the chosen Easy, Medium, or Hard level. It suggests a duration by
summing the level's expected time per question and rounding up to a
five-minute increment, which the learner can change. Build a balanced,
source-grounded question pool for every skill as described above so learners
can create different tests and retake them with varied questions. Old
`assessments/mock_tests.yaml` files may remain in existing packs for import
compatibility, but they are not used to populate the mock-test builder.

## Validation and packaging

Before packaging, check that:

1. YAML is valid, filenames and IDs are safe, and the ZIP contains no extra
   wrapper directory, executable code, or unrelated files.
2. Every skill title is a short label (usually 2-4 words, no more than 35
   characters), not a description or sentence; move explanatory detail into
   the lesson. Every skill uses a suitable registered generator; every bank
   reference exists and uses the correct schema; each skill has a usable
   exercise and answer with a nonempty explanation. Validate every typed
   lesson and bank exhibit block, including table dimensions, chart
   labels/series, and code language/source strings. Specifically reject
   bank-backed skills missing `params.bank`, a matching bank file, or a
   complete bank entry. Confirm that every `bank_mixed` entry has a supported
   `type`, that each bank's entries match the generator used by its skills,
   and that each difficulty is covered by tagged questions or untagged
   fallbacks. Audit choice questions for length, grammar, wording,
   specificity, and position cues; try longest-only and shortest-only
   strategies against the option-count chance baseline for the whole bank and
   each difficulty level. Reject `short_answer` and `fill_blank` entries;
   they are not supported response types. Convert an outcome to a supported
   format only when that format assesses it fairly, or report the grading
   limitation. Check for at least five sound questions per concept when
   supported; work toward 20 where feasible and report shortfalls without
   padding.
3. For every `lessons/*.yaml` guide, check the exact field types above: two
   nonempty strings (`definition`, `when_to_use`), three nonempty string lists
   (`steps`, `example`, `pitfalls`), and a nonempty `decision_tree` list whose
   entries each have nonempty string `question`, `yes`, and `no` fields. Check
   that guide examples and decision branches are specific to the skill and
   agree with its lesson.
4. Prerequisites are acyclic and represent a coherent learning progression,
   with foundational roots and prerequisite edges for concepts that build on
   earlier mapped skills. For any coherent progression containing at least
   three dependent skills, verify a prerequisite path spanning at least three
   mapped skills. Check roots, path lengths, and connected components using
   prerequisite edges only; independent strands may remain separate, but
   unexplained omissions are not acceptable. Do not add Concept Links or
   prerequisites merely to connect components. The question pools support
   the intended Easy, Medium, and Hard levels. There is no required prebuilt
   exam or assessment skill list; learners select their test skills in the app.
5. The manifest and skill citations contain only source facts provided or
   verified by the user, with no invented licensing or coverage claims.
6. Text is valid UTF-8 and has no replacement characters (`�`); manifest,
   skill IDs, and bank references agree exactly.
7. The ZIP opens successfully and has the required root-level layout.
8. For a semester-scale request, the coverage ledger accounts for each
   in-scope section and major objective; chapter-sized skills have been split
   where the source teaches distinct outcomes; each lesson uses discipline-
   appropriate pedagogy, is calibrated to its intended audience, and teaches
   the mapped outcome rather than following a generic template. Report
   source-limited shortfalls rather than padding or merging unrelated skills.
   Question counts meet their targets or are reported as explicit shortfalls.
   Compare the actual scope with the planned weekly modules and do not claim
   course equivalence.
9. `INFO.md` exists at the ZIP root, matches the manifest version, and
   accurately describes the purpose, user intent (or that it was not stated),
   contents, dates, lesson count, authored quiz counts by type, and generator
   skills. WIP packs list what is done, yet to implement, and needing attention.

Apply the relevant checks above once as a final pass. If the Repetorium project
is available, extract the final ZIP to a fresh staging directory and run
`validate_library` there once; it must load the graph and generate a valid
exercise and answer for every skill at difficulties 1, 2, and 3. If validation
fails, batch the reported fixes and rerun once. If the same failures remain,
stop and deliver as WIP with the exact errors instead of repeating the loop.
Do not deliver a pack that fails an available app validator as complete.

If the project is not available (as is usual in an LLM interface), perform one
manual pass over the relevant requirements, parse YAML with available tools,
and check ZIP integrity. Do not claim these checks are equivalent to running
the app. Report exactly which checks ran and label the result as a manual
self-check, not app-validated or import-tested. A successful YAML parse or ZIP
integrity test alone is insufficient. If the inspected source cannot establish
an answer or support a learning outcome, omit it and report the exact gap; do
not ask before authoring original practice grounded in the supplied material.
If you cannot create or attach a ZIP, provide the complete files or a
reproducible local packaging command instead of claiming the archive was
validated or attached.
