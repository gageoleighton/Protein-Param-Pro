"""Conservative sequence-motif detection; coordinates are 1-based and inclusive."""

from dataclasses import dataclass
import re

from protein import normalise_sequence


@dataclass(frozen=True)
class Feature:
    name: str
    kind: str
    start: int
    end: int
    sequence: str
    color: str
    substitutions: int = 0
    reference_length: int = 0

    @property
    def identity(self) -> float:
        return 100 * (1 - self.substitutions / self.reference_length) if self.reference_length else 100.0



# UniProt P0AEX9 residues 27–396 (mature MBP) and P08515 residues 2–218.
MBP_SEQUENCE = (
    "KIEEGKLVIWINGDKGYNGLAEVGKKFEKDTGIKVTVEHPDKLEEKFPQVAATGDGPDIIFWAHDRFGGYAQSGL"
    "LAEITPDKAFQDKLYPFTWDAVRYNGKLIAYPIAVEALSLIYNKDLLPNPPKTWEEIPALDKELKAKGKSALMFN"
    "LQEPYFTWPLIAADGGYAFKYENGKYDIKDVGVDNAGAKAGLTFLVDLIKNKHMNADTDYSIAEAAFNKGETAMT"
    "INGPWAWSNIDTSKVNYGVTVLPTFKGQPSKPFVGVLSAGINAASPNKELAKEFLENYLLTDEGLEAVNKDKPLG"
    "AVALKSYEEELAKDPRIAATMENAQKGEIMPNIPQMSAFWYAVRTAVINAASGRQTVDEALKDAQTRITK"
)
GST_SEQUENCE = (
    "SPILGYWKIKGLVQPTRLLLEYLEEKYEEHLYERDEGDKWRNKKFELGLEFPNLPYYIDGDVKLTQSMAIIRYIA"
    "DKHNMLGGCPKERAEISMLEGAVLDIRYGVSRIAYSKDFETLKVDFLSKLPEMLKMFEDRLCHKTYLNGDHVTHP"
    "DFMLYDALDVVLYMDPMCLDAFPKLVCFKKRIEAIPQIDKYLKSSKYIAWPLQGWQATFGGGDHPPK"
)

# References and detection limits are documented in README.md.
MOTIFS = (
    ("His tag (6+)", "Tag", r"H{6,}", "#cce5ff"),
    ("FLAG", "Tag", r"DYKDDDDK", "#ffdfb8"),
    ("HA", "Tag", r"YPYDVPDYA", "#d9efd0"),
    ("Myc", "Tag", r"EQKLISEEDL", "#ead7f5"),
    ("V5", "Tag", r"GKPIPNPLLGLDST", "#ffd6e3"),
    ("AviTag", "Tag", r"GLNDIFEAQKIEWHE", "#a8ddd1"),
    ("Strep-tag II", "Tag", r"WSHPQFEK", "#f5cba7"),
    ("Twin-Strep", "Tag", r"WSHPQFEKGGGSGGGSGGSAWSHPQFEK", "#c5b5e6"),
    ("T7", "Tag", r"MASMTGGQQMG", "#b8d8ec"),
    ("S-tag", "Tag", r"KETAAAKFERQHMDS", "#e6b8c7"),
    ("MBP", "Fusion tag", "M?" + MBP_SEQUENCE, "#c9d0f5"),
    ("GST", "Fusion tag", "M?" + GST_SEQUENCE, "#e5deb0"),
    ("TEV", "Protease motif", r"ENLYFQ[SGAMCH]", "#fff0ad"),
    ("Thrombin", "Protease motif", r"LVPRGS", "#bceae5"),
    ("Enterokinase", "Protease motif", r"DDDDK", "#e0e0e0"),
)


def similar_tag_matches(sequence: str, reference: str):
    """Find full-length, ungapped matches with at least 95% identity.

    With k substitutions, at least one of k+1 disjoint seeds must match
    exactly. Seeds limit candidate windows without dropping valid matches.
    """
    length = len(reference)
    allowed = length // 20
    candidates = set()
    for part in range(allowed + 1):
        left = part * length // (allowed + 1)
        right = (part + 1) * length // (allowed + 1)
        seed = reference[left:right]
        offset = sequence.find(seed)
        while offset != -1:
            start = offset - left
            if 0 <= start <= len(sequence) - length:
                candidates.add(start)
            offset = sequence.find(seed, offset + 1)
    for start in sorted(candidates):
        matched = sequence[start:start + length]
        substitutions = sum(a != b for a, b in zip(matched, reference))
        if substitutions <= allowed:
            yield start, substitutions


def detect_features(sequence: str) -> list[Feature]:
    sequence = normalise_sequence(sequence)
    features = []
    for name, kind, pattern, color in MOTIFS:
        reference = pattern[2:] if kind == "Fusion tag" else pattern
        if kind in ("Tag", "Fusion tag") and re.fullmatch("[A-Z]+", reference):
            for start, substitutions in similar_tag_matches(sequence, reference):
                end = start + len(reference)
                # The optional initiator methionine is outside the reference core.
                if kind == "Fusion tag" and start > 0 and sequence[start - 1] == "M":
                    start -= 1
                features.append(Feature(name, kind, start + 1, end,
                                        sequence[start:end], color, substitutions, len(reference)))
            continue
        # Variable His runs and protease motifs retain their original rules.
        non_overlapping = name.startswith("His")
        expression = pattern if non_overlapping else f"(?=({pattern}))"
        for match in re.finditer(expression, sequence):
            matched = match.group(0) if non_overlapping else match.group(1)
            features.append(Feature(name, kind, match.start() + 1,
                                    match.start() + len(matched), matched, color))
    return sorted(features, key=lambda feature: (feature.start, feature.end, feature.name))
