import unittest
from types import SimpleNamespace

from app.ui.dj_set_panel import DJSetPanel
from qt_test_helpers import ensure_qapplication


class DJSetPanelUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ensure_qapplication()

    def _result(self):
        sequence = tuple(SimpleNamespace(position=index, track_id=index) for index in range(1, 5))
        phases = tuple(SimpleNamespace(name=name, start_position=index, end_position=index) for index, name in enumerate(("warm-up", "build", "peak", "cooldown"), 1))
        journey = SimpleNamespace(set_plan=SimpleNamespace(is_partial=False), target_energy_by_position=(35, 60, 90, 50), phases=phases, deviations=())
        return SimpleNamespace(journey=journey, sequence=sequence)

    def test_empty_state_does_not_invoke_a_service(self):
        panel = DJSetPanel()
        try:
            self.assertIn("Todavía", panel.track_list.item(0).text())
            self.assertTrue(panel.journey_section.isHidden())
            self.assertFalse(panel.generate_button.isEnabled())
        finally:
            panel.close()

    def test_reference_selection_enables_an_explicit_generation_request(self):
        panel = DJSetPanel()
        requested = []
        try:
            panel.generate_requested.connect(requested.append)
            track = SimpleNamespace(id=9, artist="Artist", title="Reference")
            panel.set_reference_track(track)
            self.assertTrue(panel.generate_button.isEnabled())
            self.assertIn("Reference", panel.reference_label.text())
            panel.generate_button.click()
            self.assertEqual(requested, [track])
        finally:
            panel.close()

    def test_result_renders_sequence_phases_and_target_toggle_without_writes(self):
        tracks = tuple(SimpleNamespace(id=index, artist=chr(64 + index), title=("Warm", "Build", "Peak", "Close")[index - 1], bpm=116 + index * 4, key=f"{7 + index}A", energy=(30, 60, 90, 48)[index - 1], duration=(240, 300, 360, 250)[index - 1]) for index in range(1, 5))
        panel = DJSetPanel()
        try:
            panel.set_result(self._result(), tracks)
            self.assertEqual(panel.energy_segments.count(), 4)
            self.assertEqual(panel.phase_labels.count(), 4)
            self.assertEqual(panel.track_list.count(), 4)
            first = panel.energy_segments.itemAt(0).widget()
            self.assertIn("objetivo 35", first.accessibleName())
            self.assertEqual(first.property("energyBand"), "low")
            panel.target_toggle.setChecked(False)
            self.assertNotIn("objetivo", panel.energy_segments.itemAt(0).widget().accessibleName())
        finally:
            panel.close()
