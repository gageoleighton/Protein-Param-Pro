# Protein Param Pro

A local PySide6 protein-sequence library and concentration calculator.

## Run

```bash
.venv/bin/python src/main.py
```

## What it does

- Stores named protein sequences in expandable folders on the local machine.
- Calculates sequence length, average molecular weight, extinction coefficients, calculated isoelectric point, aromaticity, GRAVY hydropathy, instability index, and amino-acid count/percentage composition.
- Converts an entered A280 or A214 absorbance to molar concentration and mg/mL using the Beer–Lambert law (1 cm path length).
- Exports the library and derived properties to CSV.

The A280 calculation uses 5500 × Trp + 1490 × Tyr + 125 × Cys. A214 is labelled as an estimate (923 per peptide bond); use an experimentally determined coefficient where accuracy is critical. The saved library lives in `~/.protein_param_pro/sequences.json`.
