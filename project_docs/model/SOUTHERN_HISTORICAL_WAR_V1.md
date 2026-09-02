# Southern historical WAR v1

Run: `WAR-SOUTH-HIST-V1-B9D0D0F44CA6F0E211BA`

The release scores 3,418 strict D-versus-R regular legislative races in the 14-state Southern scope from 2016 through 2022. Post-2016 races preserve the published Southern WAR v3 same-cycle structural residual. The 2016 races are scored by applying the selected post-2016 `decaying_lag` ridge model (alpha 100) backward, without using any 2016 outcome to fit the model.

`WAR = legislative-minus-ticket gap - fitted structural expected gap`.

Fundraising is displayed only where both major-party observations and identities are complete. It does not enter headline WAR because the prespecified nested time-forward finance test failed. Missouri and Mississippi are the principal finance gaps in this warehouse run; missing finance is unknown, never zero. Research-only context, uncontested races, and non-D/R races remain unscored.
