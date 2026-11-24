# Learning Software

**Practice, Review, Apply**

Repetorium is an offline-first learning application for practicing material
from user-provided libraries of skills, relationships, explanations, and
questions. It organizes that content into a structured learning sequence and
tracks the learner's practice.

## The Learning Loop

1. **Choose a useful next task.** The tutor checks remediation needs, mixed-quiz
   timing, due reviews, prerequisites, and recent practice before selecting a
   lesson or review. Among prerequisite-ready lessons, it favors a less-recently
   practiced category and, when authored links support it, a cross-category
   application or contrast to a recently learned skill. This is a sequencing
   heuristic, not proof that transfer occurred.
   The Dashboard Learning Plan normally previews seven lessons, using selected
   pack-level weekly goals for its mix. If the weekly goal is below seven, the
   remaining preview slots extend that mix proportionally; above seven, each
   selected pack with unfinished lessons is shown at least once before the
   remaining preview slots are distributed.
2. **Retrieve, then get feedback.** The learner answers a generated or authored
   question before seeing the answer and explanation. An optional self-check
   records whether the learner could explain the reasoning, felt unsure, or
   guessed. It does not change objective grading, but a correct lesson
   answer marked unsure or guessed—or answered after opening the lesson—does
   not advance the mastery streak. Low-confidence answers and answers given
   after opening the lesson in reviews and quizzes are treated as weak retrieval
   evidence and bring the skill back sooner. In the placement diagnostic, a
   low-confidence answer or an answer given after opening the lesson is
   inconclusive rather than evidence for or against the skill. Feedback connects
   the answer to the skill guide, and selected authored questions offer a short
   ungraded variation prompt. Numeric work is checked automatically; choice and
   ordering items use deterministic grading.
3. **Build readiness.** By default, a lesson is mastered after three
   consecutive correct answers; **Settings → Advanced learning settings** lets
   learners choose a streak of two to five. Errors reset the streak and can
   queue prerequisite remediation.
4. **Revisit over time.** Spaced reviews, mixed quizzes, and prerequisite credit
   bring earlier skills back into practice instead of treating a completed lesson
   as permanent mastery. Failed objective questions in a case or mock test can
   queue the relevant unlearned skill and its missing prerequisites; success on
   one exam question never marks an unlearned skill mastered. Advanced settings
   also tune review-interval growth and its cap, the retry delay after a missed
   review, and mixed-quiz cadence and size. Changes affect future scheduling;
   existing review due dates are not rewritten. Easy, Balanced, and Hard
   presets provide starting configurations: Easy reduces mastery and quiz
   demands and spaces reviews farther apart, while Hard raises mastery and quiz
   demands and brings reviews back sooner. Reset to defaults restores Balanced,
   and each setting can then be adjusted individually.
5. **Apply and reflect.** Learners create mock tests by searching for and
   adding skills; the app generates one question per selected skill. Tests use
   the same deterministic grading as practice and show results by skill.
   Learners choose difficulty and can adjust the suggested duration in
   five-minute increments. Question levels map to Easy (2 minutes, 1 XP),
   Medium (3 minutes, 2 XP), and Hard
   (5 minutes, 3 XP); mixed quizzes adapt their level to demonstrated
   repetition. Consulting cases retain their separate case flow and rubric.

## Placement Diagnostic

The optional first-use diagnostic is a skill-map screening check, not a
psychometrically calibrated computerized adaptive test. It asks at most 15
questions. A sampled skill first gets a medium-level item; a correct response
routes to a harder confirmation and a miss routes to an easier check, using a
different item where the library has one. Only two consistent responses credit
the sampled skill. A confirmed skill can also credit its explicitly mapped
prerequisites, but a miss does not mark descendant skills as unknown. Mixed or
insufficient evidence is left inconclusive, and the completion summary reports
skills that were inconclusive or not assessed. Uncredited skills remain
available through the ordinary lesson sequence.

This conservative route is an explainable heuristic: the content format has no
empirically calibrated item parameters or validated skill-by-item matrix, so the
app does not claim item-response-theory estimates, posterior mastery
probabilities, or a complete diagnosis. Question selection and stopping limits
are designed together, following concerns raised in computerized
classification-testing research; consistent repeated evidence and caution
about binary mastery classifications draw on knowledge-tracing and
partial-mastery diagnostic-model research. A correct response marked as a guess
is treated as inconclusive and does not contribute placement evidence; this
conservative use of a self-report is a design rule, not a calibrated confidence
model, and learners can still omit or misstate it. See the diagnostic sources in
[Learning Software: Design and Evidence](LEARNING_DESIGN.md).

## Knowledge Model

The library organizes learning as a directed prerequisite graph. Skills can declare
prerequisites, weighted encompassing relationships, and similarity relationships.
Prerequisites control which new lessons are available; weighted relationships let
practice on a broader skill contribute partial review credit to component skills;
similarity helps avoid teaching easily confused skills back-to-back. The
Skill Map makes this structure visible and provides each skill's guide.
Concepts can belong to multiple domains and cite source references and locations.
Separate explained, weighted links capture applications, analogies, contrasts and
related ideas. They are navigable in both directions and never gate lessons or
grant implicit review credit. An analogy is a tool for exploration, not evidence
that two subjects are interchangeable.

Each concept also offers optional saved reflections for explanations,
comparisons, counterexamples and applications. These notes do not change XP,
readiness or review timing. About describes the software's features and data
handling; Credits lists learning research and project tools. The
[Learning Software: Design and Evidence](LEARNING_DESIGN.md) document
describes the learning mechanisms and their limitations.

Skills select registered generators and may reference authored banks. This keeps
the tutor's scheduling and grading mechanisms reusable across subjects,
category names, explanations, questions and assessments.

Lessons and authored questions can combine prose with rendered math, data
tables, bar/line/scatter charts, and display-only monospace code. These are
content presentation formats, not promises of full LaTeX, code execution, or
automatic grading for every discipline. The answer model grades numeric,
single-choice, multi-select, matching, ordering, and true/false responses. It
does not grade free-form text, essays, proofs, or programs; short-answer and
fill-in-the-blank bank entries are no longer supported. Content authors should
choose outcomes that can be assessed faithfully with the available formats and
disclose source or assessment gaps rather than claiming complete coverage of a
subject.

## What Progress Means

Mastery is an operational signal that a learner has recently answered a short
lesson streak correctly. It is not proof of durable retention, transfer, or
professional competence. Diagnostics estimate a starting point; scheduled review
and mixed quizzes provide additional retrieval practice. Mock-exam and case
responses also feed review scheduling for mastered skills and prerequisite-aware
remediation for missed unmastered skills. Delayed unassisted checks
and unfamiliar problems are stronger evidence of retention and transfer, and are
future evaluation needs.

XP rewards practice effort and consistency. It is not a measure of intelligence,
knowledge, or learning effectiveness. In case-based practice, self-ratings
can influence review scheduling, but they are not independently verified mastery
evidence. Cross-domain connections likewise do not prove transfer. Unfamiliar
applications, delayed retrieval and practical synthesis are the intended next
evaluation surfaces; they are not yet fully implemented.

Practice confidence is an optional self-report, not independently verified
evidence of understanding. It is displayed separately from objective accuracy,
but unsure or guessed answers—and answers submitted after opening the lesson—
are treated as weaker evidence for mastery and review. In placement, those
answers are inconclusive; this does not make confidence a calibrated estimate
of understanding. The learner's explanation and performance on unfamiliar
applications remain distinct questions.

## Product Constraints

- Local-first learning: content and learner progress are local; tutoring does not
  require a runtime language model or network access.
- Deterministic practice: a seeded generator and explicit grading rules make
  generated items reproducible and answers checkable.
- Visible assumptions: applied problems should state material assumptions, units,
  time periods, and constraints in learner-facing prompts and solutions.
- Content packs: learners choose what they want to study and supply a library
  in the documented format.
- Honest measurement: report what was practiced and assessed without presenting
  XP, question counts, or short-term correctness as stronger evidence than they are.

The software ships without a learning library. Learners import a pack they have
prepared; the tutor does not generate content or process source documents. See
[README.md](../README.md) and
[KNOWLEDGE_LIBRARY.md](../KNOWLEDGE_LIBRARY.md). The Credits screen separates
learning philosophy and project tools.

## Session and Persistence Guarantees

Ordinary navigation preserves active practice and assessments. Content reloads
and progress resets explicitly clear all sessions, including timers and pending
answers. Failed actions keep their current phase and display an error.
Validated exercise banks and case templates are retained in the active library;
rejected reloads cannot replace them with invalid files from disk.

A learning action writes its attempts, XP, scheduling and completion information
as one transaction. On failure, in-memory learner and practice state is restored
as well, so a retry does not duplicate credit. Historical attempts for skills no
longer in the library are grouped as archived skills.

Case history deletion restores the complete before-case state of affected skills,
including acquisition status. Per-skill activity revisions detect later evidence
even if it leaves acquisition status unchanged. Undo is refused when subsequent
learning involved those skills or changed the case's remediation queue; later nonlinear review
updates cannot safely be undone by subtracting repetition credit. Deleting an
older case does not silently rewrite later learning.