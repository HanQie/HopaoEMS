---
phase: 1
plan: 04-verification
name: Phase 1 Final Verification
goal: Ensure all Phase 1 changes are verified with smoke tests and i18n is synchronized.
depends_on: ["01-logic", "02-ui", "03-wash-detail"]
must_haves:
  truths:
    - name: zero_regression
      description: All existing quality gates must pass after Phase 1 changes.
  artifacts:
    - path: src/hopaoems/i18n/seed.en.json
      provides: English translations for new error messages.
      min_lines: 300
  key_links:
    - from: gate.bat
      to: smoke_tests.py
      via: automation
---

# Plan 04-verification: Phase 1 Final Verification

<task id="4.1" name="Synchronize i18n" status="todo">
<files>
  <file>src/hopaoems/i18n/seed.en.json</file>
  <file>src/hopaoems/i18n/seed.zh-TW.json</file>
  <file>src/hopaoems/i18n/seed.vi.json</file>
</files>
<action>
Add new translation keys for Phase 1 error messages and labels (e.g., `production.error.washed_log_locked`).
</action>
<verify>
<automated>python -m hopaoems.contracts.run_gates</automated>
Ensure the i18n parity gate passes.
</verify>
<done>
Translations are complete and synchronized across all supported languages.
</done>
</task>

<task id="4.2" name="Implement Integrity Smoke Tests" status="todo">
<files>
  <file>tests/test_phase1_integrity.py</file>
</files>
<action>
Create a new test file to perform end-to-end validation of the new log protection and revocation workflows.
</action>
<verify>
<automated>python -m pytest tests/test_phase1_integrity.py</automated>
All integrity tests pass.
</verify>
<done>
System integrity is empirically verified.
</done>
</task>

<task id="4.3" name="Run Unified Quality Gate" status="todo">
<files>
  <file>gate.bat</file>
</files>
<action>
Execute the full quality gate suite.
</action>
<verify>
<automated>.\gate.bat</automated>
All 33+ layers pass with 0 failures.
</verify>
<done>
Phase 1 is officially stable and verified.
</done>
</task>
