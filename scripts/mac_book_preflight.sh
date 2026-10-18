#!/usr/bin/env bash
# Read-only local handoff. Never starts training or opens the sealed test cases in the model.
set -u
cd "$(dirname "$0")/.." || exit 2
stamp="$(date +%Y%m%d-%H%M%S)"
out="work/phase1-host-preflight-$stamp"
mkdir -p "$out" || exit 2
python3 scripts/doctor.py --verify-model --output "$out/host.json" > "$out/doctor.log" 2>&1
doctor_rc=$?
PYTHONPATH=src python3 -m unittest discover -s tests -v > "$out/regression.log" 2>&1
tests_rc=$?
python3 - "$out" "$doctor_rc" "$tests_rc" <<'PY'
import json, pathlib, sys
folder = pathlib.Path(sys.argv[1])
report = {'scope': 'mac_local_preflight_not_model_training',
          'doctor_exit_code': int(sys.argv[2]),
          'regression_exit_code': int(sys.argv[3]),
          'model_training_performed': False,
          'sealed_test_model_inference': False,
          'github_model_uploaded': False}
(folder / 'handoff.json').write_text(json.dumps(report, indent=2) + '\n')
PY
zip -q -r "$out.zip" "$out" || exit 2
printf '\nHost preflight package: %s.zip\n' "$out"
printf 'Doctor exit: %s; full test suite exit: %s\n' "$doctor_rc" "$tests_rc"
printf 'Send only this diagnostic ZIP through our conversation, not to the public repository.\n'
if [ "$doctor_rc" -ne 0 ] || [ "$tests_rc" -ne 0 ]; then exit 1; fi
