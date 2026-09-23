"""Domain model and calculations for protein sequences."""

from __future__ import annotations

from dataclasses import dataclass

from Bio.SeqUtils.ProtParam import ProteinAnalysis


WATER_MASS = 18.01528
RESIDUE_MASS = {
    "A": 71.0788, "R": 156.1875, "N": 114.1038, "D": 115.0886,
    "C": 103.1388, "E": 129.1155, "Q": 128.1307, "G": 57.0519,
    "H": 137.1411, "I": 113.1594, "L": 113.1594, "K": 128.1741,
    "M": 131.1926, "F": 147.1766, "P": 97.1167, "S": 87.0782,
    "T": 101.1051, "W": 186.2132, "Y": 163.1760, "V": 99.1326,
}
AMINO_ACIDS = tuple(RESIDUE_MASS)


@dataclass
class Protein:
    """A saved protein sequence and its library metadata."""

    name: str
    sequence: str
    group: str = "My proteins"
    color: str = ""
    notes: str = ""
    absorbance_280: float | None = None


def normalise_sequence(value: str) -> str:
    """Remove whitespace and stop characters from a one-letter sequence."""
    return "".join(value.upper().split()).replace("*", "")


def protein_properties(sequence: str) -> dict[str, float | int | dict[str, float | int]]:
    """Calculate composition and physicochemical properties for a valid sequence."""
    sequence = normalise_sequence(sequence)
    unknown = set(sequence) - set(RESIDUE_MASS)
    if not sequence or unknown:
        raise ValueError("Sequence must contain only the 20 standard amino-acid letters.")

    length = len(sequence)
    molecular_weight = sum(RESIDUE_MASS[aa] for aa in sequence) + WATER_MASS
    # Pace et al. convention: 5500 per Trp, 1490 per Tyr and 125 per Cys.
    extinction_280 = sequence.count("W") * 5500 + sequence.count("Y") * 1490 + sequence.count("C") * 125
    # A useful peptide-bond estimate for A214; presented as an approximation in the UI.
    extinction_214 = max(1, length - 1) * 923
    analysis = ProteinAnalysis(sequence)
    amino_acid_counts = {amino_acid: sequence.count(amino_acid) for amino_acid in AMINO_ACIDS}
    return {
        "length": length,
        "mw": molecular_weight,
        "e280": extinction_280,
        "e214": extinction_214,
        "w": sequence.count("W"),
        "y": sequence.count("Y"),
        "c": sequence.count("C"),
        "aa_counts": amino_acid_counts,
        "aa_percentages": {amino_acid: count / length * 100 for amino_acid, count in amino_acid_counts.items()},
        "pi": analysis.isoelectric_point(),
        "aromaticity": analysis.aromaticity(),
        "gravy": analysis.gravy(),
        "instability_index": analysis.instability_index(),
    }
