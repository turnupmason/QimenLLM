"""Regression against the supplied immutable business chapter, no invented facts."""
import hashlib
import unittest
from pathlib import Path
from scripts.import_shenqi_business import SOURCE_FILE, SOURCE_SHA, build_artifacts, source_lines


class BusinessSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = SOURCE_FILE.read_bytes()
        cls.curated, cls.cases, cls.candidates, cls.counts = build_artifacts(cls.raw)

    def test_exact_source_bytes(self):
        self.assertEqual(len(self.raw), 56047)
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), SOURCE_SHA)
        self.assertEqual(len(source_lines(self.raw)), 1366)

    def test_intact_case_families_and_event_counts(self):
        self.assertEqual(self.counts["cases"], 14)
        self.assertEqual(self.counts["events"], 19)
        self.assertEqual(self.counts["charts"], 16)
        self.assertEqual(len(self.cases["cases"]), 14)
        self.assertEqual(len({c["family"]["family_key"] for c in self.cases["cases"]}), 14)
        self.assertEqual([len(c["events"]) for c in self.cases["cases"]][-3:], [6,1,1])

    def test_multi_day_draw_is_not_16_invented_events(self):
        draw = self.cases["cases"][11]
        self.assertEqual([len(e["charts"]) for e in draw["events"]],[0,1,1,1,0,0])
        self.assertTrue(all(e["chronology_status"] == "unknown" for e in draw["events"]))
        self.assertEqual(sum(len(e["charts"]) for e in draw["events"]),3)
        self.assertTrue(all(r["knowledge_phase"] != "pre_prediction"
            for e in draw["events"] for r in e["records"]))

    def test_original_palace_grid_and_no_golden_claim(self):
        source=source_lines(self.raw)
        for case in self.cases["cases"]:
            for event in case["events"]:
                for chart in event["charts"]:
                    rows=chart["payload"]["row_cells_as_written"]
                    self.assertEqual(len(rows),9)
                    self.assertTrue(all(len(r)==4 for r in rows))
                    self.assertFalse(chart["payload"]["engine_verified"])
                    self.assertFalse(chart["payload"]["independent_gold_checked"])
                    self.assertEqual(chart["validation_status"],"original_unparsed")
                    left,right=chart["source_lines"]
                    self.assertIn("九宫盘面：", "".join(source[left-1:right]))

    def test_section_coverage_and_candidate_scoping(self):
        n=len(source_lines(self.raw))
        covered=set()
        for group in self.curated["groups"]:
            covered.update(range(group["line_start"],group["line_end"]+1))
        self.assertEqual(covered,set(range(1,n+1)))
        self.assertEqual(len(self.candidates["candidates"]),14)
        for c in self.candidates["candidates"]:
            self.assertTrue(c["reference_only"])
            self.assertFalse(c["formal_role_activation_allowed"])
            self.assertFalse(c["professional_prediction_completed"])
            self.assertEqual(c["source_quote"],source_lines(self.raw)[c["source_lines"][0]-1].rstrip("\r\n"))

    def test_source_stage_model_not_success_prediction(self):
        self.assertEqual(self.cases["temporal_payload_contract"],"source-stage-v1")
        for case in self.cases["cases"]:
            self.assertEqual(case["completeness"],"confirmed_complete")
            for event in case["events"]:
                keys=[r["record_key"] for r in event["records"]]
                self.assertEqual(len(keys),len(set(keys)))
                for r in event["records"]:
                    if r["kind"] in ("feedback","outcome","continuation"):
                        self.assertNotEqual(r["knowledge_phase"],"pre_prediction")
                    if r["knowledge_phase"]=="pre_prediction":
                        self.assertTrue(r["payload"]["pre_prediction_release_allowed"])


if __name__=="__main__":
    unittest.main()
