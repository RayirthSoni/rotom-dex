# Reviewed game knowledge

Structured imports remain the baseline. `data/knowledge/facts.json` is a small reviewed prose sidecar, and `glossary.json` contains concise mechanics explanations. These do not replace the structured database or establish comprehensive game coverage.

## Add a reviewed batch

1. Choose an exact game and capability from `services/content.py`. Inventory the questions a player should be able to ask, including prerequisites, locations, version differences, spoilers and negative answers. Record omissions explicitly.
2. Read supporting sources. Write concise original statements with the supporting URLs, source note, review date and review status. Distinguish source review from gameplay verification. Do not treat a search result snippet or a model answer as independent review.
3. Use one applicability level: exact games, version groups, generations or explicitly invariant. Remakes and paired versions require separate verification. DLC requirements belong in `applicability.dlc`; access must match the base version.
4. Set structured availability. `unavailable` needs affirmative source support; no row or missing knowledge is `unknown`. Set spoiler classification before publication.
5. Run `rotom content-audit --db DATABASE`. Unknown applicability or detected conflicts block publication. The current conflict detector catches differing claims with identical subject/capability/applicability; overlapping scopes and semantically conflicting passages still need human review.
6. Add question/regression cases, including the closest paired version and remake. Read the rendered answers and citations. A source-reviewed fact does not independently establish a useful answer.
7. Run `rotom content-audit --db DATABASE --publish DIRECTORY`. This writes a hash-named immutable JSON snapshot and refuses to overwrite an existing one. It does not modify the game database or deploy the snapshot. Commit the reviewed source file and its tests together.

The application currently loads the repository sidecar and includes its hash in facts. Publication creates an inspectable snapshot artifact; promoting external published snapshots to a deployment remains an explicit operational step.

## Deep support is a separate gate

The audit lists every main-series game and fourteen capabilities. `inventory_review_complete` and `question_suite_review_complete` are intentionally false until a reviewer-signoff workflow is implemented. No game is automatically promoted by having one fact, a nonempty table or passing deterministic tests.

Before promotion, complete and review Pokémon and item acquisition, shops, machines, tutors, evolution, breeding, transfers/events, progression, bosses, postgame, mechanics, story advice and competitive support where applicable. Explicitly document capabilities that do not exist in that game. Review live follow-ups, game switching, comparisons, spoiler-safe answers and supported negatives as well as direct factual questions.
