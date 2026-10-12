"""Run in openmontage-maths-manim; verifies geometry, not rendered quality."""
import unittest
import numpy as np
from manim import PI
from precision_earth_v5 import globe, NORTH, TILT, Base

class PrecisionGeometryTests(unittest.TestCase):
    def test_axis_tilt(self):
        self.assertAlmostEqual(np.linalg.norm(NORTH),1.)
        self.assertAlmostEqual(np.arccos(NORTH[2]),TILT)

    def test_surface_spin_does_not_precess_axis(self):
        center=np.array([-2.1,0.,0.])
        earth,grid,axis=globe(1.85,center)
        start,end=axis.get_start().copy(),axis.get_end().copy()
        marker=grid[-1].get_center().copy()
        # Invoke the actual production updater, not a separate test rotation.
        Base.spin(None,grid,center,period=24)
        grid.update(6.)
        np.testing.assert_allclose(axis.get_start(),start,atol=1e-8)
        np.testing.assert_allclose(axis.get_end(),end,atol=1e-8)
        after=grid[-1].get_center()
        self.assertGreater(np.linalg.norm(after-marker),1.)
        self.assertAlmostEqual(np.dot(marker-center,NORTH),np.dot(after-center,NORTH),places=6)

    def test_orbit_translation_keeps_axis_direction(self):
        earth,_,axis=globe(.62,np.array([2.,0.,0.]))
        before=axis.get_end()-axis.get_start()
        for a in np.linspace(0,2*PI,12):
            earth.move_to([-1.5+3.5*np.cos(a),3.5*np.sqrt(1-.0167**2)*np.sin(a),0])
            np.testing.assert_allclose(axis.get_end()-axis.get_start(),before,atol=1e-8)

if __name__=='__main__': unittest.main()
