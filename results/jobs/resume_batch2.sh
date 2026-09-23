#!/bin/bash
# Resume the E2-5 batch once the orphaned jobs of the killed runner have written their JSON.
cd "$(dirname "$0")/../.."
while pgrep -f '^.venv/bin/python tools/chb_cop_from_schema.py.*e25' >/dev/null; do sleep 30; done
exec tools/run_jobs.sh results/jobs/batch2.txt 8
