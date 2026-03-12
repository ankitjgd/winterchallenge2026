# Winter Challenge 2026 — Snakebot

## Goal
Control your snakebots to collect **power sources** and grow.
**Win condition:** have more total body parts across all your snakebots than the opponent at game end.

---

## Game Mechanics

### Grid
- Size: 15–45 wide × 10–30 tall
- `#` = platform (solid, impassable)
- `.` = free cell

### Snakebots
- Each player controls 1–8 snakebots simultaneously.
- Each snakebot is a chain of body parts; the **first coordinate is the head**.
- Body string format: `"x,y:x,y:x,y"` — e.g. `"0,1:1,1:2,1"` means head at (0,1) with two more parts to the right.

### Gravity
- **At least one body part must be supported** at all times, or the snakebot falls/is removed.
- A body part is supported if:
  - It is at the bottom row of the grid, OR
  - There is a `#` platform directly below it, OR
  - Another body part is directly below it.
- This means a **short snake may not be able to reach elevated platforms** — it needs enough body length to stay anchored while the head climbs.

### Movement
- Each turn you set a direction for each snakebot: `UP / DOWN / LEFT / RIGHT`.
- The head moves one cell in that direction; the body follows (tail removed).
- If the head moves onto a **power source**, the snake eats it and **grows by 1**.
- If the head moves into a platform or out of bounds, the snakebot is destroyed.

### Collisions
- Moving into an opponent body destroys your snakebot's head (next body part becomes the new head).

---

## Game End Conditions
The game ends when **any** of these is true:
1. All of a player's snakebots have been removed.
2. There are no more power sources left.
3. 200 turns have passed.

---

## Actions (Output Format)
Each turn output **one line** with actions separated by `;`.

| Command | Effect |
|---------|--------|
| `id UP` | Move snakebot `id` up (y−1) |
| `id DOWN` | Move snakebot `id` down (y+1) |
| `id LEFT` | Move snakebot `id` left (x−1) |
| `id RIGHT` | Move snakebot `id` right (x+1) |
| `MARK x y` | Debug marker (up to 4 per turn) |
| `WAIT` | Do nothing |

Example: `1 LEFT;2 RIGHT;MARK 12 2`

### Constraints
- Response time per turn: **≤ 50 ms**
- Response time for first turn: **≤ 1000 ms**
- 15 ≤ width ≤ 45
- 10 ≤ height ≤ 30
- 1 ≤ snakebotCount ≤ 8

---

## Input Format (per turn)

```
powerSourceCount
x y       ← repeated powerSourceCount times
snakebotCount
snakebotId body   ← repeated snakebotCount times (all snakes, both players)
```

---

## Strategy

### 1. Greedy Nearest Food (gravity-aware BFS)
Each snakebot runs a BFS toward the nearest reachable power source.
BFS carries the full body tuple so gravity can be checked correctly at every step.
A move is only valid if the resulting body configuration has at least one supported part.

### 2. Divide the Map
Sort snakes longest-first and assign food greedily (no two snakes chase the same target).
Longer snakes get first pick because they can reach more platforms.

### 3. Grow First, Then Climb
If a power source is unreachable (snake too short to bridge a gap), skip it and eat
reachable food first. Re-check deferred sources each turn as the snake grows.

### 4. Endgame Denial
When few power sources remain, route your nearest snake to intercept sources before
the opponent reaches them.

---

## Files
- `solution.py` — main bot
