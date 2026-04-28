import os

import imageio
import imageio.v3 as imageio3
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.offsetbox import OffsetImage, AnnotationBbox


def braking_distance(v_kmh, m, brake_force=5000):
    # base formula: v**2/(2*a)
    # "a" differs for different cars because we assume a constant brake force
    # velocity (v) from km/h in m/s
    v = v_kmh / 3.6
    # compute brake-acceleration
    a = brake_force / m
    # compute the distance
    s = v ** 2 / (2 * a)
    return s


if __name__ == '__main__':
    # Verzeichnis für Frames und gifs
    os.makedirs("frames", exist_ok=True)
    os.makedirs("gifs", exist_ok=True)

    # define start velocities
    s_vs = [
        [20, 50, 60, 100],
        [30, 60, 70, 100],
        [10, 30, 50, 100],
        [30, 40, 70, 90],
        [20, 30, 60, 100],
    ]

    # Parameter
    for idx, (c, weight) in enumerate(
            [("auto", 1000), ("sportwagen", 1500), ("pickup", 2000), ("kleinbus", 2300), ("lastwagen", 3000)]):
        # Auto-Icon laden
        car_img = mpimg.imread(f"icons/{c}.png")
        for start_velocity in s_vs[idx]:
            n_frames = 30
            point_of_stop = start_velocity // 5
            x_positions = np.linspace(0, 10, n_frames)
            x_positions[point_of_stop:] = x_positions[point_of_stop]

            frames = []

            for i, x in enumerate(x_positions):
                fig, ax = plt.subplots(figsize=(6, 2))
                ax.set_xlim(-1, 12)
                ax.set_ylim(-0.6, 2)
                ax.axis("off")

                # Straße
                ax.plot([-1, 12], [1, 1], color="black", linewidth=3)
                ax.plot([-1, 12], [-0.5, -0.5], color="black", linewidth=3)

                # Auto einfügen
                imagebox = OffsetImage(car_img, zoom=0.15)  # zoom für Größe
                if c == "auto":
                    x_positions = x_positions * 1.0
                elif c == "sportwagen":
                    x_positions = x_positions * 1.1
                elif c == "pickup":
                    x_positions = x_positions * 1.2
                elif c == "kleinbus":
                    x_positions = x_positions * 1.3
                elif c == "lastwagen":
                    x_positions = x_positions * 1.5
                ab = AnnotationBbox(imagebox, (x, 0.5), frameon=False)
                ax.add_artist(ab)

                # Text: Geschwindigkeit nimmt linear ab
                if i >= point_of_stop:
                    ax.text(6, 1.5, f"Gemessener Bremsweg: {braking_distance(start_velocity, weight):.0f} m",
                            ha="center",
                            fontsize=12)
                # speed = max(0, start_velocity - i * 5)  # km/h
                # ax.text(6, 1.5, f"Geschwindigkeit: {speed:.0f} km/h", ha="center", fontsize=12)

                # Frame speichern
                filename = f"frames/frame_{i:03d}.png"
                plt.savefig(filename)
                plt.close(fig)

                frames.append(imageio3.imread(filename))

            # GIF speichern
            imageio.mimsave(f"gifs/{c}_{start_velocity}.gif", frames, duration=0.3)
            print(f"GIF erstellt: {c}_{start_velocity}.gif")
