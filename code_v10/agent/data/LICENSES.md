# Data licenses & attribution

## DDXPlus (`agent/data/ddx_kb.json`)

- Source: Fansi Tchango A., Goel R., Wen Z., Martel J., Ghosn J.
  "DDXPlus: A New Dataset For Automatic Medical Diagnosis".
  NeurIPS 2022 Datasets and Benchmarks Track.
- License: Creative Commons Attribution 4.0 International (CC BY 4.0),
  https://creativecommons.org/licenses/by/4.0/
- Files used: `release_conditions.json`, `release_evidences.json` (offline build via `tools/build_ddx_kb.py`).
- What is derived: only the condition–evidence structure (which symptoms/antecedents are linked to which
  condition), condition severity, and the antecedent flag of each evidence.
- Changes: the Korean questions, Korean labels, system tags, red-flag flags, Korean disease names and synonyms
  are our own translation and adaptation; they are not part of DDXPlus. Some categorical evidences were dropped
  (listed in the `skipped` field of the JSON).
- Not included: DDXPlus synthetic patient files (`release_*_patients.zip`) are neither used nor redistributed.

## Clinical practice guidelines (runtime only)

Guideline texts are NOT bundled with this submission. They are read at runtime from `/opt/nova/guidelines`,
provided by the organizers. At runtime the agent only performs search over them and produces derived
checklists; no guideline text is copied into this package.
