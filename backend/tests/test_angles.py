import numpy as np
import pytest
from app.biomechanics.angles import interior_angle, joint_angles

def test_known_angles_and_degenerate_points():
    assert interior_angle([1,0], np.array([0,0]), [0,1]) == pytest.approx(90)
    assert interior_angle([-1,0], np.array([0,0]), [1,0]) == pytest.approx(180)
    assert interior_angle([0,0], np.array([0,0]), [1,0]) is None

def test_pixel_aspect_ratio_and_confidence_gating():
    points = [dict(x=.5,y=.5,visibility=1,presence=1) for _ in range(33)]
    points[11].update(x=.6,y=.6)
    points[25].update(x=.6,y=.4)
    expected = interior_angle([120,60],np.array([100,50]),[120,40])
    assert joint_angles(points,200,100)['left_hip'] == pytest.approx(expected)
    assert expected != pytest.approx(90)
    points[23]['visibility'] = .2
    assert joint_angles(points,200,100)['left_hip'] is None
    points[23]['visibility'] = 1
    points[23]['presence'] = .1
    assert joint_angles(points,200,100)['left_hip'] is None
    points[23].update(presence=1,x=-.1)
    assert joint_angles(points,200,100)['left_hip'] is None
