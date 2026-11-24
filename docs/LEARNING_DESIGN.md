# Learning Software: Design and Evidence

Repetorium is an offline-first learning application for studying user-provided
content. It organizes content as skills, prerequisite relationships, questions
and explanations, then uses those structures to guide lessons and reviews.

## Learning Features

- **Structured lessons:** prerequisite relationships control which new skills
  are ready to study.
- **Practice and feedback:** generated or authored questions support retrieval
  practice, while mock tests and mixed quizzes provide additional practice.
- **Progress and review:** the app records practice, schedules reviews and shows
  skill status in progress summaries and the Skill Map.
- **Optional reflections:** learners can save explanations, comparisons and
  notes. Reflections do not affect XP, readiness or review timing.
- **User-managed content:** the app ships without a learning library. Learners
  import and manage their own content packs.

## Design Boundaries

Review timing is a transparent heuristic, not a personalized model trained on
large response datasets. Mastery status and XP reflect app activity; they do not
guarantee long-term retention. A correct response on an unlearned skill does not
grant mastery. Mixed evidence in placement diagnostics can remain inconclusive.
The app does not automatically grade reflections or assess transfer.

The research below informs specific learning mechanisms. It does not establish
the effectiveness of Repetorium as a whole; results depend on the materials,
tasks and implementation.

## Selected Research

- [Dunlosky et al. (2013), Improving Students' Learning With Effective Learning Techniques](https://doi.org/10.1177/1529100612453266):
  reviews evidence for practice testing and distributed practice.
- [Roediger & Karpicke (2006), Test-Enhanced Learning](https://doi.org/10.1111/j.1467-9280.2006.01693.x):
  compares retrieval practice and repeated study for delayed retention.
- [Rohrer & Taylor (2007), The Shuffling of Mathematics Problems Improves Learning](https://doi.org/10.1007/s11251-007-9015-8):
  studies interleaving of distinguishable mathematical procedures.
- [Settles & Meeder (2016), A Trainable Spaced Repetition Model for Language Learning](https://aclanthology.org/P16-1174/):
  describes recall prediction from large-scale language-learning histories;
  Repetorium does not fit this model to sparse personal data.
- [Justin Skycak, The Math Academy Way, advised by Jason Roberts](https://www.justinmath.com/the-math-academy-way/):
  a design influence for granular skills, prerequisites, mastery checks and
  review. Repetorium is an independent implementation.
- [Justin Skycak, Advice on Upskilling](https://www.justinmath.com/advice-on-upskilling/):
  practical guidance on foundations, consistent practice and producing useful
  work that informed Repetorium's learning-software design.
- [National Academies (2018), How People Learn II, Chapter 5: Knowledge and Reasoning](https://www.nationalacademies.org/read/24783/chapter/7):
  discusses explanation and learning through teaching.
- [Corbett & Anderson (1995), Knowledge Tracing](https://doi.org/10.1007/BF01099821):
  describes estimating skill acquisition from learner response histories.
- [Thompson (2009), Item Selection in Computerized Classification Testing](https://doi.org/10.1177/0013164408324460):
  discusses item selection and stopping criteria for diagnostic assessments.
