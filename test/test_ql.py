import unittest

import simplecadapi as scad
from simplecadapi import ql as Q


class TestQLTagPredicates(unittest.TestCase):
    def test_tag_exact_and_wildcard(self):
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        box.apply_tag("role.mounting_surface")

        self.assertTrue(Q.tag("role.mounting_surface")(box))
        self.assertTrue(Q.tag("role.*")(box))
        self.assertFalse(Q.tag("role.other")(box))

    def test_tag_face_prefix(self):
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        box.auto_tag_faces("box")
        top_faces = [face for face in box.get_faces() if face.has_tag("face.top")]
        self.assertTrue(top_faces)

        top_face = top_faces[0]
        self.assertTrue(Q.tag("face.top")(top_face))
        self.assertTrue(Q.tag("face.*")(top_face))


class TestQLMetadataPredicates(unittest.TestCase):
    def test_meta_eq_and_compare(self):
        box = scad.make_box_rsolid(2.0, 3.0, 4.0)

        self.assertTrue(Q.meta("geo.type", "==", "box")(box))
        self.assertTrue(Q.meta("geo.size.x", ">", 1.0)(box))

    def test_select_where_order_first(self):
        c1 = scad.make_cylinder_rsolid(1.0, 1.0)
        c2 = scad.make_cylinder_rsolid(1.0, 3.0)
        c3 = scad.make_cylinder_rsolid(1.0, 2.0)

        result = (
            Q.select([c1, c2, c3]).order_by(Q.value("geo.height"), desc=True).first()
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.get_metadata("geo")["height"], 3.0)

    def test_where_and_not(self):
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        cyl = scad.make_cylinder_rsolid(1.0, 1.0)
        box.apply_tag("role.mounting_surface")
        box.apply_tag("state.debug", propagate=False)

        predicate = Q.and_(
            Q.meta("geo.type", "==", "box"),
            Q.tag("role.mounting_surface"),
            Q.not_(Q.tag("state.*")),
        )

        result = Q.select([box, cyl]).where(predicate).all()
        self.assertEqual(result, [])

        predicate = Q.and_(
            Q.meta("geo.type", "==", "box"),
            Q.tag("role.mounting_surface"),
        )

        result = Q.select([box, cyl]).where(predicate).all()
        self.assertEqual(result, [box])

    def test_first_empty(self):
        self.assertIsNone(Q.select([]).first())


class TestQLExportSelection(unittest.TestCase):
    def test_ql_select_records_exportable_face(self):
        scad.create_new_history("ql_select_export")
        profile = scad.make_circle_rface((0.0, 0.0, 0.0), 5.0)
        cylinder = scad.extrude_rsolid(profile, (0.0, 0.0, 1.0), 10.0)

        top_face = scad.ql_select_one(
            cylinder,
            "faces",
            Q.query().where(Q.tag("extrusion end face")).take(1).exactly(1),
            name="Selected_Extrusion_Top_Face",
        )
        path = scad.make_helix_rwire(2.0, 18.0, 7.0, center=(0.0, 0.0, 10.0))
        scad.sweep_rsolid(top_face, path, is_frenet=True)

        script = scad.FeatureExporter(scad.get_global_history())._generate_freecad_script()
        self.assertIn("# QL Select: Selected_Extrusion_Top_Face", script)
        self.assertIn("_scad_match_topology_by_signature", script)
        self.assertIn(".Sections = [Feature_002_Selected_Extrusion_Top_Face_Result]", script)
        self.assertNotIn("# Warning: Sweep profile/path not found", script)

    def test_ql_select_from_feature_outputs_exports(self):
        scad.create_new_history("ql_select_from_export")
        small = scad.make_box_rsolid(1.0, 1.0, 1.0)
        large = scad.make_box_rsolid(2.0, 2.0, 2.0)

        selected = scad.ql_select_one_from(
            [small, large],
            Q.query().order_by(Q.geo("volume"), desc=True).take(1).exactly(1),
            name="Largest_Box",
        )

        self.assertIs(selected, large)
        script = scad.FeatureExporter(scad.get_global_history())._generate_freecad_script()
        self.assertIn("# QL Select From List: Largest_Box", script)
        self.assertIn("Part.Compound([item.Shape", script)

    def test_ql_select_from_topology_exports(self):
        scad.create_new_history("ql_select_multi_topology_export")
        a = scad.make_box_rsolid(1.0, 1.0, 1.0)
        b = scad.make_box_rsolid(2.0, 2.0, 2.0)

        selected = scad.ql_select_one_from_topology(
            [(a, "faces"), (b, "faces")],
            Q.query().order_by(Q.geo("area"), desc=True).take(1).exactly(1),
            name="Largest_Face",
        )

        self.assertAlmostEqual(selected.get_area(), 4.0)
        script = scad.FeatureExporter(scad.get_global_history())._generate_freecad_script()
        self.assertIn("# QL Select From Topology: Largest_Face", script)
        self.assertIn("_scad_match_topology_by_signature", script)


if __name__ == "__main__":
    unittest.main()
