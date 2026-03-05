---
phase: 3
plan: 03-validation
name: Final Validation & E2E
goal: Perform a final exhaustive validation of the entire system before completion.
depends_on: ["01-audit-trail", "02-activity-view"]
must_haves:
  truths:
    - name: system_stability
      description: The project must be 100% compliant with all quality gates.
  artifacts:
    - path: gate.bat
      provides: Final pass evidence.
      min_lines: 5
  key_links:
    - from: smoke_tests.py
      to: audit_logs
      via: integrity check
---

# Plan 03-validation: Final Validation & E2E

<task id="3.7" name="Comprehensive Smoke Test Pass" status="todo">
<files>
  <file>src/hopaoems/contracts/smoke_tests.py</file>
</files>
<action>
Run the full smoke test suite multiple times to ensure zero intermittent failures and verify audit trail capture.
</action>
<verify>
<automated>python src/hopaoems/contracts/smoke_tests.py</automated>
SMOKE TESTS PASSED message in console.
</verify>
<done>
System logic is robust and verified.
</done>
</task>

<task id="3.8" name="Full Quality Gate Sweep" status="todo">
<files>
  <file>gate.bat</file>
</files>
<action>
Run `.\gate.bat` and address any final warnings or minor issues discovered during the sweep.
</action>
<verify>
<automated>.\gate.bat</automated>
All 33+ gate layers return PASS.
</verify>
<done>
System meets all strict UI and architectural contracts.
</done>
</task>

<task id="3.9" name="Final i18n Synchronization" status="todo">
<files>
  <file>src/hopaoems/i18n/seed.en.json</file>
  <file>src/hopaoems/i18n/seed.zh-TW.json</file>
  <file>src/hopaoems/i18n/seed.vi.json</file>
</files>
<action>
Ensure all new strings for Activity view and Audit trail are correctly translated and synced.
</action>
<verify>
<automated>python -m hopaoems.contracts.run_gates</automated>
i18n Key Parity Gate passes.
</verify>
<done>
Application is 100% ready for multi-lingual users.
</done>
</task>
