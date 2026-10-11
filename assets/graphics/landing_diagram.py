"""
This file generates a 3D Möbius strip animation for the landing page.
"""

from manim import *
import numpy as np


# The class handling the Möbius strip
class MobiusAnimation(ThreeDScene):

    # The function called when rendering the strip
    def construct(self):

        # Define the view angle and the number of dots for the strip
        self.set_camera_orientation(phi=70 * DEGREES, theta=45 * DEGREES)
        num_points = 60

        # Create groups to allow dots and lines to rotate
        dots = VGroup()
        lines = VGroup()

        # Define the three colors for the dots
        color_red = ManimColor("#FF0000")
        color_orange = ManimColor("#FFA500")
        color_brown = ManimColor("#8B4513")

        # The function to define the color of each dot based on its position
        def get_transition_color(index, total):

            # Ratio = how far around the loop
            ratio = index / total

            # Transition from red to orange for first half of loop
            if ratio < 0.5:
                return interpolate_color(color_red, color_orange, ratio * 2)

            # Transition from orange to brown for the next half of loop
            else:
                return interpolate_color(color_orange, color_brown, (ratio - 0.5) * 2)

        # Generate the position of each dot
        points = []
        for i in range(num_points):

            # The dots run for two laps, so 4π
            t = i * (4 * PI / num_points)

            # The x, y, and z coordinates of each dot
            x = (3 + np.cos(t / 2)) * np.cos(t)
            y = (3 + np.cos(t / 2)) * np.sin(t)
            z = 1.5 * np.sin(t / 2)
            points.append(np.array([x, y, z]))

        # Attach colour to the dots
        for i, p in enumerate(points):
            dot_color = get_transition_color(i, num_points)
            dot = Dot3D(point=p, color=dot_color, radius=0.12)
            dots.add(dot)

        # Generate the connecting lines between opposite points
        half_points = num_points // 2
        for i in range(half_points):
            p1 = points[i]
            p2 = points[i + half_points]
            line = Line(p1, p2, color=WHITE, stroke_opacity=0.3)
            lines.add(line)

        # Group everything together
        structure = VGroup(lines, dots)
        self.add(structure)

        # Animate a smooth, continuous 3D rotation
        self.play(Rotate(structure, angle=2 * PI, axis=UP, run_time=8, rate_func=linear))
