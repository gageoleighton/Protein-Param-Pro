import unittest

from sequence_features import detect_features


class FeatureTests(unittest.TestCase):
    def test_positions_and_normalization(self):
        hits = detect_features('m hh hhhh\n*ENLYFQG')
        self.assertEqual([(h.name, h.start, h.end) for h in hits],
                         [('His tag (6+)', 2, 7), ('TEV', 8, 14)])

    def test_repeated_and_overlapping(self):
        hits = detect_features('DYKDDDDKDYKDDDDK')
        self.assertEqual([(h.name, h.start, h.end) for h in hits],
                         [('FLAG', 1, 8), ('Enterokinase', 4, 8),
                          ('FLAG', 9, 16), ('Enterokinase', 12, 16)])

    def test_long_his_run_is_one_feature(self):
        hits = detect_features('HHHHHHHHHH')
        self.assertEqual(len(hits), 1)
        self.assertEqual((hits[0].start, hits[0].end), (1, 10))

    def test_no_partial_matches(self):
        self.assertEqual(detect_features('HHHHHENLYFQP'), [])
        self.assertEqual(detect_features(''), [])

    def test_supported_tags(self):
        for name, sequence in [('HA', 'YPYDVPDYA'), ('Myc', 'EQKLISEEDL'),
                               ('V5', 'GKPIPNPLLGLDST'), ('Thrombin', 'LVPRGS')]:
            hits = detect_features(sequence)
            self.assertEqual([(h.name, h.start, h.end) for h in hits],
                             [(name, 1, len(sequence))])

    def test_fusion_tags_and_coordinates(self):
        from sequence_features import MBP_SEQUENCE, GST_SEQUENCE
        for name, sequence in [('MBP', MBP_SEQUENCE), ('GST', GST_SEQUENCE)]:
            for prefix in ['', 'M']:
                tag = prefix + sequence
                hits = [h for h in detect_features('AAA' + tag + 'GGG' + tag) if h.name == name]
                self.assertEqual([(h.start, h.end) for h in hits],
                                 [(4, 3 + len(tag)), (7 + len(tag), 6 + 2 * len(tag))])
                self.assertEqual([h.sequence for h in hits], [tag, tag])
            self.assertFalse(any(h.name == name for h in detect_features(sequence[:40])))
            self.assertFalse(any(h.name == name for h in detect_features(sequence[:-1])))

    def test_mbp_precursor_marks_mature_chain(self):
        from sequence_features import MBP_SEQUENCE
        signal = 'MKIKTGARILALSALTTMMFSASALA'
        hits = [h for h in detect_features(signal + MBP_SEQUENCE) if h.name == 'MBP']
        self.assertEqual([(h.start, h.end) for h in hits], [(27, 396)])

    def test_additional_common_tags(self):
        tags = {
            'AviTag': 'GLNDIFEAQKIEWHE',
            'Strep-tag II': 'WSHPQFEK',
            'Twin-Strep': 'WSHPQFEKGGGSGGGSGGSAWSHPQFEK',
            'T7': 'MASMTGGQQMG',
            'S-tag': 'KETAAAKFERQHMDS',
        }
        for name, sequence in tags.items():
            with self.subTest(tag=name):
                pasted = 'aa ' + sequence.lower() + '\n*aaa' + sequence.lower()
                hits = [h for h in detect_features(pasted) if h.name == name]
                self.assertEqual([(h.start, h.end, h.sequence) for h in hits],
                                 [(3, 2 + len(sequence), sequence),
                                  (6 + len(sequence), 5 + 2 * len(sequence), sequence)])
                self.assertFalse(any(h.name == name for h in detect_features(sequence[:-1])))
                changed = ('A' if sequence[0] != 'A' else 'G') + sequence[1:]
                self.assertEqual(any(h.name == name for h in detect_features(changed)),
                                 len(sequence) >= 20)

    def test_twin_strep_contains_two_strep_motifs(self):
        hits = detect_features('WSHPQFEKGGGSGGGSGGSAWSHPQFEK')
        self.assertEqual([(h.name, h.start, h.end) for h in hits],
                         [('Strep-tag II', 1, 8), ('Twin-Strep', 1, 28),
                          ('Strep-tag II', 21, 28)])

    def test_identity_threshold_boundaries(self):
        from sequence_features import MBP_SEQUENCE, GST_SEQUENCE
        for name, ref in [('MBP', MBP_SEQUENCE), ('GST', GST_SEQUENCE),
                          ('Twin-Strep', 'WSHPQFEKGGGSGGGSGGSAWSHPQFEK'),
                          ('AviTag', 'GLNDIFEAQKIEWHE')]:
            for count in [len(ref) // 20, len(ref) // 20 + 1]:
                mutated = list(ref)
                for i in range(count):
                    pos = i * len(ref) // max(count, 1)
                    mutated[pos] = 'A' if mutated[pos] != 'A' else 'G'
                mutated = ''.join(mutated)
                hits = [h for h in detect_features('AAA' + mutated + 'AAA') if h.name == name]
                if count <= len(ref) // 20:
                    self.assertEqual(len(hits), 1)
                    self.assertEqual((hits[0].start, hits[0].end), (4, 3 + len(ref)))
                    self.assertEqual(hits[0].substitutions, count)
                    self.assertGreaterEqual(hits[0].identity, 95)
                else:
                    self.assertEqual(hits, [])

    def test_fuzzy_search_matches_brute_force(self):
        import random
        from sequence_features import similar_tag_matches
        rng = random.Random(7)
        for length in (20, 28, 40):
            ref = ''.join(rng.choice('ACDE') for _ in range(length))
            variant = list(ref)
            variant[-1] = 'G'
            sequence = 'AAAA' + ''.join(variant) + ref + 'CCCC'
            expected = [(i, sum(a != b for a, b in zip(sequence[i:i+length], ref)))
                        for i in range(len(sequence)-length+1)]
            expected = [(i, n) for i, n in expected if n <= length // 20]
            self.assertEqual(list(similar_tag_matches(sequence, ref)), expected)
