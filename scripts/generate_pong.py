#!/usr/bin/env python3
"""
Seamless self-playing Pong animation for a GitHub profile README.

This generator:
  1. Loads the persistent match state from scripts/pong_state.json.
  2. Simulates a long Pong segment with smooth paddle AI.
  3. Writes the segment to assets/pong.svg as an SMIL animation.
  4. Saves the updated state so future GitHub Actions runs continue the match.

The SVG animation is designed to look continuous rather than like a tiny
recording that immediately jumps back to the start.
"""

import json
import math
import os
import random

STATE_PATH = os.path.join(os.path.dirname(__file__), "pong_state.json")
SVG_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "pong.svg")

# --- board geometry ---
W, H = 600, 300
PADDLE_W, PADDLE_H = 10, 60
PADDLE_MARGIN = 20
BALL_R = 7

# Long visual segment. The browser loops this segment.
FRAME_COUNT = 720
DUR_SECONDS = 45

# Simulation speed.
BALL_SPEED_X = 4.2
PADDLE_SPEED = 3.2


def default_state():
    return {
        "ball_x": W / 2,
        "ball_y": H / 2,
        "ball_vx": BALL_SPEED_X,
        "ball_vy": 2.6,
        "left_y": H / 2,
        "right_y": H / 2,
        "left_score": 0,
        "right_score": 0,
    }


def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return default_state()


def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def move_paddle(current, target, max_speed):
    """Smoothly move a paddle toward a target."""
    delta = target - current
    if abs(delta) <= max_speed:
        return target
    return current + max_speed if delta > 0 else current - max_speed


def step(state, rng):
    """Advance the simulation by one frame."""
    state["ball_x"] += state["ball_vx"]
    state["ball_y"] += state["ball_vy"]

    # Top/bottom wall collisions.
    if state["ball_y"] <= BALL_R:
        state["ball_y"] = BALL_R
        state["ball_vy"] = abs(state["ball_vy"])
    elif state["ball_y"] >= H - BALL_R:
        state["ball_y"] = H - BALL_R
        state["ball_vy"] = -abs(state["ball_vy"])

    left_x = PADDLE_MARGIN
    right_x = W - PADDLE_MARGIN

    # Predictive-ish paddle targets with only a small amount of imperfection.
    # This creates long rallies while still allowing an occasional score.
    left_target = state["ball_y"]
    right_target = state["ball_y"]

    # Slight personality difference between the paddles.
    if state["ball_vx"] < 0:
        left_target += rng.uniform(-5, 5)
        right_target += rng.uniform(-12, 12)
    else:
        left_target += rng.uniform(-12, 12)
        right_target += rng.uniform(-5, 5)

    state["left_y"] = clamp(
        move_paddle(state["left_y"], left_target, PADDLE_SPEED),
        PADDLE_H / 2,
        H - PADDLE_H / 2,
    )
    state["right_y"] = clamp(
        move_paddle(state["right_y"], right_target, PADDLE_SPEED),
        PADDLE_H / 2,
        H - PADDLE_H / 2,
    )

    # Paddle collisions.
    if (
        state["ball_vx"] < 0
        and state["ball_x"] - BALL_R <= left_x + PADDLE_W / 2
        and abs(state["ball_y"] - state["left_y"]) <= PADDLE_H / 2 + BALL_R
    ):
        state["ball_x"] = left_x + PADDLE_W / 2 + BALL_R
        state["ball_vx"] = min(abs(state["ball_vx"]) * 1.015, 6.5)

        # Small angle change based on where the ball hits the paddle.
        offset = (state["ball_y"] - state["left_y"]) / (PADDLE_H / 2)
        state["ball_vy"] += offset * 0.35

    if (
        state["ball_vx"] > 0
        and state["ball_x"] + BALL_R >= right_x - PADDLE_W / 2
        and abs(state["ball_y"] - state["right_y"]) <= PADDLE_H / 2 + BALL_R
    ):
        state["ball_x"] = right_x - PADDLE_W / 2 - BALL_R
        state["ball_vx"] = -min(abs(state["ball_vx"]) * 1.015, 6.5)

        offset = (state["ball_y"] - state["right_y"]) / (PADDLE_H / 2)
        state["ball_vy"] += offset * 0.35

    state["ball_vy"] = clamp(state["ball_vy"], -5.5, 5.5)

    # Score.
    if state["ball_x"] < -BALL_R:
        state["right_score"] += 1
        reset_ball(state, direction=1, rng=rng)

    elif state["ball_x"] > W + BALL_R:
        state["left_score"] += 1
        reset_ball(state, direction=-1, rng=rng)


def reset_ball(state, direction, rng):
    state["ball_x"] = W / 2
    state["ball_y"] = H / 2
    state["ball_vx"] = 4.0 * direction
    state["ball_vy"] = rng.choice([-1, 1]) * rng.uniform(1.8, 3.0)


def render_svg(frames, state):
    """Write a long SMIL animation segment."""
    key_times = ";".join(
        f"{i / (len(frames) - 1):.5f}" for i in range(len(frames))
    )

    ball_xs = ";".join(f"{f['ball_x']:.1f}" for f in frames)
    ball_ys = ";".join(f"{f['ball_y']:.1f}" for f in frames)
    left_ys = ";".join(
        f"{f['left_y'] - PADDLE_H / 2:.1f}" for f in frames
    )
    right_ys = ";".join(
        f"{f['right_y'] - PADDLE_H / 2:.1f}" for f in frames
    )

    # The first and last displayed positions are held by the animation.
    # A long segment plus smooth motion makes the loop much less conspicuous.
    svg = f"""<svg width="{W}" height="{H + 40}" viewBox="0 0 {W} {H + 40}"
xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H + 40}" fill="#0d1117"/>

  <text x="{W/2}" y="26" fill="#39ff14"
        font-family="Courier New, monospace" font-size="18"
        text-anchor="middle">{state["left_score"]}  :  {state["right_score"]}</text>

  <line x1="{W/2}" y1="40" x2="{W/2}" y2="{H+40}"
        stroke="#238636" stroke-width="2" stroke-dasharray="6,10"/>

  <rect x="{PADDLE_MARGIN - PADDLE_W/2}"
        y="{frames[0]['left_y'] - PADDLE_H/2}"
        width="{PADDLE_W}" height="{PADDLE_H}"
        rx="3" fill="#39ff14" transform="translate(0,40)">
    <animate attributeName="y"
             values="{left_ys}"
             keyTimes="{key_times}"
             dur="{DUR_SECONDS}s"
             calcMode="linear"
             repeatCount="indefinite"/>
  </rect>

  <rect x="{W - PADDLE_MARGIN - PADDLE_W/2}"
        y="{frames[0]['right_y'] - PADDLE_H/2}"
        width="{PADDLE_W}" height="{PADDLE_H}"
        rx="3" fill="#39ff14" transform="translate(0,40)">
    <animate attributeName="y"
             values="{right_ys}"
             keyTimes="{key_times}"
             dur="{DUR_SECONDS}s"
             calcMode="linear"
             repeatCount="indefinite"/>
  </rect>

  <circle cx="{frames[0]['ball_x']}"
          cy="{frames[0]['ball_y']}"
          r="{BALL_R}" fill="#e6edf3" transform="translate(0,40)">
    <animate attributeName="cx"
             values="{ball_xs}"
             keyTimes="{key_times}"
             dur="{DUR_SECONDS}s"
             calcMode="linear"
             repeatCount="indefinite"/>
    <animate attributeName="cy"
             values="{ball_ys}"
             keyTimes="{key_times}"
             dur="{DUR_SECONDS}s"
             calcMode="linear"
             repeatCount="indefinite"/>
  </circle>

  <text x="{W/2}" y="{H + 34}" fill="#6e7681"
        font-family="Courier New, monospace" font-size="11"
        text-anchor="middle">
    self-playing Pong · persistent game state · GitHub Actions
  </text>
</svg>
"""

    with open(SVG_PATH, "w", encoding="utf-8") as f:
        f.write(svg)


def main():
    # Fixed seed per run makes the generated animation stable/reproducible,
    # while the persistent state itself continues across GitHub Actions runs.
    rng = random.Random()

    state = load_state()
    frames = []

    for _ in range(FRAME_COUNT):
        step(state, rng)
        frames.append(
            {
                "ball_x": state["ball_x"],
                "ball_y": state["ball_y"],
                "left_y": state["left_y"],
                "right_y": state["right_y"],
            }
        )

    render_svg(frames, state)
    save_state(state)

    print(
        f"Score now {state['left_score']} : "
        f"{state['right_score']}"
    )


if __name__ == "__main__":
    main()
