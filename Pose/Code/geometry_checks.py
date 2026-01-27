import numpy as np

class GeometryChecks:
    @staticmethod
    def calculate_distance(p1, p2):
        return np.linalg.norm(np.array(p1) - np.array(p2))

    @staticmethod
    def calculate_horizontal_distance(p1, p2):
        return abs(p1[0] - p2[0])

    @staticmethod
    def calculate_vertical_distance(p1, p2):
        """Calculates signed vertical distance (p1_y - p2_y).
        In image coordinates (Y down):
        - Positive: p1 is below p2
        - Negative: p1 is above p2
        """
        return p1[1] - p2[1]

    @staticmethod
    def calculate_angle(a, b, c):
        """Calculates angle ABC (at point B) in degrees."""
        a = np.array(a)
        b = np.array(b)
        c = np.array(c)
        ba = a - b
        bc = c - b
        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
        angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
        return np.degrees(angle)

    @staticmethod
    def distance_from_line(p0, p1, p2):
        """Calculates perpendicular distance of point p0 from line p1-p2."""
        p0 = np.array(p0)
        p1 = np.array(p1)
        p2 = np.array(p2)
        return np.abs(np.cross(p2 - p1, p1 - p0)) / (np.linalg.norm(p2 - p1) + 1e-6)
