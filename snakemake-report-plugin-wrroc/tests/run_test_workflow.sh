#!/bin/bash

# This will run only once, setting up the conda environment and running the workflow.
# Running the test script the second time, all results are already presend and snakemake does nothing
echo "Run workflow in test_crate"
cd test_workflow
snakemake --use-conda --cores all

echo ""
echo "Create report for test_crate"
tmpdir=$(mktemp -d)
echo "Creating test crate: ${tmpdir}" 
snakemake --reporter wrroc \
  --report-wrroc-crate $tmpdir \
  --report-wrroc-force \
  --report-wrroc-user-orcid https://orcid.org/0000-0000-0000-0000 \
  --report-wrroc-user-name "John Doe" \
  --report-wrroc-user-email john.doe@example.org \
  --report-wrroc-user-affiliation "Some Random University"

# ro-crate-1.1
echo ""
echo "Validate as RO-Crate-1.1 (REQUIRED)"
tmp_validation_report=$(mktemp)
echo "Report: ${tmp_validation_report}"
rocrate-validator validate \
  --requirement-severity REQUIRED \
  --profile-identifier ro-crate-1.1 \
  --output-format json \
  --output-file ${tmp_validation_report}  \
  ${tmpdir}


# process-run-crate-0.5
echo ""
echo "Validate as Process Run Crate 0.5 (REQUIRED)"
tmp_validation_report=$(mktemp)
echo "Report: ${tmp_validation_report}"
rocrate-validator validate \
  --requirement-severity REQUIRED \
  --profile-identifier ro-crate-1.1 \
  --output-format json \
  --output-file ${tmp_validation_report}  \
  ${tmpdir}

# workflow-ro-crate-1.0
echo ""
echo "Validate as Workflow RO-Crate 1.0 (REQUIRED)"
tmp_validation_report=$(mktemp)
echo "Report: ${tmp_validation_report}"
rocrate-validator validate \
  --requirement-severity REQUIRED \
  --profile-identifier workflow-ro-crate-1.0 \
  --output-format json \
  --output-file ${tmp_validation_report}  \
  ${tmpdir}

# workflow-run-crate-0.5
echo ""
echo "Validate as Workflow Run RO-Crate 0.5 (REQUIRED)"
tmp_validation_report=$(mktemp)
echo "Report: ${tmp_validation_report}"
rocrate-validator validate \
  --requirement-severity REQUIRED \
  --profile-identifier workflow-run-crate-0.5 \
  --output-format json \
  --output-file ${tmp_validation_report}  \
  ${tmpdir}

# provenance-run-crate-0.5
echo ""
echo "Validate as Provenance Run RO-Crate 0.5 (REQUIRED)"
tmp_provenance_run_crate_validation=$(mktemp)
echo "Validator report: ${tmp_provenance_run_crate_validation}"
rocrate-validator validate \
  --requirement-severity REQUIRED \
  --profile-identifier provenance-run-crate-0.5 \
  --output-format json \
  --output-file $tmp_provenance_run_crate_validation  \
  ${tmpdir}
