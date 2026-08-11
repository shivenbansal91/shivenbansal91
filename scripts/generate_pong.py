#!/usr/bin/env python3
"""
Self-playing Pong bot for a GitHub profile README.

Every time this runs (via GitHub Actions, on a schedule), it:
  1. Loads the ongoing match state (ball position/velocity, paddle
     positions, score) from scripts/pong_state.json.
  2. Simulates the next chunk of the match, frame by frame.
  3. Writes those frames into assets/pong.svg as an SMIL animation,
     so the SVG itself "plays" the last few seconds of the match
     when someone views the README on GitHub.
  4. Saves the new state so next run picks up right where this one
     left off -- the match never resets, it just keeps going forever.

No external dependencies -- stdlib only, so it's cheap to run in CI.
"""

import json
import os
import random

STATE_PATH = os.path.join(os.path.dirname(__file__), "pong_state.json")
SVG_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "pong.svg")

# --- board geometry ---
W, H = 600, 300
PADDLE_W, PADDLE_H = 10, 60
PADDLE_MARGIN = 20
BALL_R = 7
FRAME_COUNT = 260         # frames rendered into this run's animation
DUR_SECONDS = 20          # how long the loop takes to play in the browser


def default_state():
    return {
        "ball_x": W / 2,
        "ball_y": H / 2,
        "ball_vx": 4.2,
        "ball_vy": 2.6,
        "left_y": H / 2,
        "right_y": H / 2,
        "left_score": 0,
        "right_score": 0,
    }


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return default_state()


def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def step(state):
    """Advance the simulation by one frame, in place."""
    state["ball_x"] += state["ball_vx"]
    state["ball_y"] += state["ball_vy"]

    # bounce off top/bottom walls
    if state["ball_y"] <= BALL_R or state["ball_y"] >= H - BALL_R:
        state["ball_vy"] *= -1
        state["ball_y"] = clamp(state["ball_y"], BALL_R, H - BALL_R)

    left_x = PADDLE_MARGIN
    right_x = W - PADDLE_MARGIN

    # paddle AI: track the ball with a max speed + a bit of imperfection
    # so the score actually moves over time instead of a perfect draw forever
    for side, x in (("left", left_x), ("right", right_x)):
        target = state["ball_y"] + random.uniform(-18, 18)
        cur = state[f"{side}_y"]
        max_speed = 3.4
        if abs(target - cur) < max_speed:
            cur = target
        else:
            cur += max_speed if target > cur else -max_speed
        state[f"{side}_y"] = clamp(cur, PADDLE_H / 2, H - PADDLE_H / 2)

    # paddle collisions
    if state["ball_vx"] < 0 and state["ball_x"] - BALL_R <= left_x + PADDLE_W / 2:
        if abs(state["ball_y"] - state["left_y"]) <= PADDLE_H / 2 + BALL_R:
            state["ball_vx"] *= -1.03
            state["ball_x"] = left_x + PADDLE_W / 2 + BALL_R
    if state["ball_vx"] > 0 and state["ball_x"] + BALL_R >= right_x - PADDLE_W / 2:
        if abs(state["ball_y"] - state["right_y"]) <= PADDLE_H / 2 + BALL_R:
            state["ball_vx"] *= -1.03
            state["ball_x"] = right_x - PADDLE_W / 2 - BALL_R

    # scoring -- ball passed a paddle
    if state["ball_x"] < 0:
        state["right_score"] += 1
        reset_ball(state, direction=1)
    elif state["ball_x"] > W:
        state["left_score"] += 1
        reset_ball(state, direction=-1)

    # keep speed sane
    state["ball_vx"] = clamp(state["ball_vx"], -7, 7)
    state["ball_vy"] = clamp(state["ball_vy"], -6, 6)


def reset_ball(state, direction):
    state["ball_x"] = W / 2
    state["ball_y"] = H / 2
    state["ball_vx"] = 4.0 * direction
    state["ball_vy"] = random.choice([-1, 1]) * random.uniform(2.0, 3.4)


def render_svg(frames, state):
    """frames: list of dicts with ball_x, ball_y, left_y, right_y per frame."""
    key_times = " ; ".join(f"{i / (len(frames) - 1):.4f}" for i in range(len(frames)))

    ball_xs = ";".join(f"{f['ball_x']:.1f}" for f in frames)
    ball_ys = ";".join(f"{f['ball_y']:.1f}" for f in frames)
    left_ys = ";".join(f"{f['left_y'] - PADDLE_H / 2:.1f}" for f in frames)
    right_ys = ";".join(f"{f['right_y'] - PADDLE_H / 2:.1f}" for f in frames)

    svg = f"""<svg width="{W}" height="{H + 40}" viewBox="0 0 {W} {H + 40}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H + 40}" fill="#0d1117"/>
  <text x="{W/2}" y="26" fill="#39ff14" font-family="Courier New, monospace" font-size="18"
        text-anchor="middle">{state['left_score']}  :  {state['right_score']}</text>
  <line x1="{W/2}" y1="40" x2="{W/2}" y2="{H+40}" stroke="#238636" stroke-width="2" stroke-dasharray="6,10"/>
  <rect x="{PADDLE_MARGIN - PADDLE_W/2}" y="{frames[0]['left_y'] - PADDLE_H/2}" width="{PADDLE_W}" height="{PADDLE_H}"
        rx="3" fill="#39ff14" transform="translate(0,40)">
    <animate attributeName="y" values="{left_ys}" keyTimes="{key_times}" dur="{DUR_SECONDS}s" repeatCount="indefinite"/>
  </rect>
  <rect x="{W - PADDLE_MARGIN - PADDLE_W/2}" y="{frames[0]['right_y'] - PADDLE_H/2}" width="{PADDLE_W}" height="{PADDLE_H}"
        rx="3" fill="#39ff14" transform="translate(0,40)">
    <animate attributeName="y" values="{right_ys}" keyTimes="{key_times}" dur="{DUR_SECONDS}s" repeatCount="indefinite"/>
  </rect>
  <circle cx="{frames[0]['ball_x']}" cy="{frames[0]['ball_y']}" r="{BALL_R}" fill="#e6edf3" transform="translate(0,40)">
    <animate attributeName="cx" values="{ball_xs}" keyTimes="{key_times}" dur="{DUR_SECONDS}s" repeatCount="indefinite"/>
    <animate attributeName="cy" values="{ball_ys}" keyTimes="{key_times}" dur="{DUR_SECONDS}s" repeatCount="indefinite"/>
  </circle>
  <text x="{W/2}" y="{H + 34}" fill="#6e7681" font-family="Courier New, monospace" font-size="11"
        text-anchor="middle">self-playing 24/7 · updates on a schedule via GitHub Actions</text>
</svg>
"""
    with open(SVG_PATH, "w") as f:
        f.write(svg)


def main():
    state = load_state()
    frames = []
    for _ in range(FRAME_COUNT):
        step(state)
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
    print(f"Score now {state['left_score']} : {state['right_score']}")


if __name__ == "__main__":
    main()
