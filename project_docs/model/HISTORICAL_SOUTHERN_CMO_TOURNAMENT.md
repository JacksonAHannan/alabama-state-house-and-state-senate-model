# Historical Southern CMO tournament

This experiment asks how much legislative performance beyond a same-cycle
federal or statewide baseline can be predicted using generic downballot lag,
symmetric incumbency, geography, chamber, and time. It uses only the 1,805
strictly eligible races in the independently validated historical Southern
panel. Rows with partial precinct-context allocation are excluded.

The tournament retains a baseline-only guardrail and tests progressively more
structured ridge models. Evaluation has two independent forms:

- forward-year validation trains only on earlier cycles;
- leave-state-out validation trains on every state except the state predicted.

Selection uses leave-state-out RMSE among models no more than one margin point
worse than the best forward-year RMSE. Whole-precinct leave-state-out error and
model simplicity break ties. This makes geographic transportability primary
without accepting a model that materially fails the temporal test.
Candidate-quality residuals use only the
selected model's leave-state-out predictions. Democratic and Republican
candidate residuals are exact sign reversals for the same race.

These are transportability-oriented descriptive residuals, not causal effects.
They do not replace Alabama CMO or the production forecast. Coverage currently
begins in 2002; official and OpenElections ingestion remains necessary for the
1994–2000 target period.
