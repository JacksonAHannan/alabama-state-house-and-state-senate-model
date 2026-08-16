param(
    [int]$AmendmentProcessId = 0
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$log = Join-Path $repo "research/cmo_ideology/remaining_research_run.log"
$err = Join-Path $repo "research/cmo_ideology/remaining_research_run.err.log"

Set-Location -LiteralPath $repo

try {
    if ($AmendmentProcessId -gt 0) {
        $running = Get-Process -Id $AmendmentProcessId -ErrorAction SilentlyContinue
        if ($null -ne $running) {
            "Waiting for amendment classification process $AmendmentProcessId" | Out-File $log -Append
            Wait-Process -Id $AmendmentProcessId
        }
    }

    # Rewrite final amendment outputs from the validated bill-link universe.
    # Existing valid model results are cached, so this pass is fast.
    & python scripts/classify_focal_amendments_ollama.py *>> $log

    "Validating sponsorship bill-text provenance: $(Get-Date -Format o)" | Out-File $log -Append
    & python scripts/repair_sponsorship_bill_text_overrides.py *>> $log
    & python scripts/validate_sponsorship_bill_text_links.py *>> $log

    "Starting sponsorship bill classification: $(Get-Date -Format o)" | Out-File $log -Append
    & python scripts/classify_sponsorship_review_bills_ollama.py *>> $log

    "Refreshing candidate biographies: $(Get-Date -Format o)" | Out-File $log -Append
    & python scripts/build_overperformer_biographies.py *>> $log

    "Rebuilding reviewed legislative evidence: $(Get-Date -Format o)" | Out-File $log -Append
    & python scripts/build_candidate_amendment_position_evidence.py *>> $log
    & python scripts/build_candidate_sponsorship_positions.py *>> $log

    "Rebuilding matrices and queues: $(Get-Date -Format o)" | Out-File $log -Append
    & python scripts/build_cmo_state_issue_matrix.py *>> $log
    & python scripts/build_campaign_position_research_queue.py *>> $log
    & python scripts/build_candidate_public_position_review_queue.py *>> $log
    & python scripts/audit_candidate_issue_research.py *>> $log

    "Running focused validation: $(Get-Date -Format o)" | Out-File $log -Append
    & python -m pytest scripts/tests/test_candidate_legislative_activity.py scripts/tests/test_cmo_state_issue_matrix.py -q *>> $log
    "Remaining automated research stages completed: $(Get-Date -Format o)" | Out-File $log -Append
}
catch {
    $_ | Out-String | Out-File $err -Append
    exit 1
}
