import sys
import heapq
from collections import deque


def debug(*args):
    print(*args, file=sys.stderr, flush=True)


def parse_body(body_str):
    """Parse '0,1:1,1:2,1' into tuple of (x,y) tuples. First = head."""
    parts = []
    for coord in body_str.split(':'):
        x, y = map(int, coord.split(','))
        parts.append((x, y))
    return tuple(parts)


DIRS = [('UP', 0, -1), ('DOWN', 0, 1), ('LEFT', -1, 0), ('RIGHT', 1, 0)]


def is_supported(body, grid, height, food_set, friendly_cells=None):
    """
    The snake is supported if at least one body part has STATIC support below it:
      - floor (y+1 >= height), OR
      - platform (#) directly below, OR
      - a power source directly below (food acts as a platform), OR
      - a friendly (allied) snake's body part directly below.

    Own body parts below are NOT counted — a floating chain provides no anchor.
    But a friendly snake is independently grounded, so it acts as a real platform.
    """
    for (x, y) in body:
        if y + 1 >= height:
            return True
        if grid[y + 1][x] == '#':
            return True
        if (x, y + 1) in food_set:
            return True
        if friendly_cells and (x, y + 1) in friendly_cells:
            return True
    return False


def simulate_fall(body, grid, height, food_set, friendly_cells=None):
    """
    After a move, apply gravity by repeatedly shifting the whole snake DOWN
    until it is supported or a part leaves the grid / hits a platform.

    Returns the final resting body tuple, or None if the snake dies.
    Moving into a '#' during falling = head destruction = treat as invalid.
    """
    body_list = list(body)
    for _ in range(height):
        curr = tuple(body_list)
        if is_supported(curr, grid, height, food_set, friendly_cells):
            return curr
        # Shift every part down by 1
        next_list = []
        for (x, y) in body_list:
            ny = y + 1
            if ny >= height:
                return None          # falls off the grid
            if grid[ny][x] == '#':
                return None          # hits a platform — fatal
            next_list.append((x, ny))
        body_list = next_list
    return None  # never settled — treat as invalid


def apply_move(curr_body, nx, ny, grid, height, food_set, friendly_cells=None):
    """
    Build the body after moving the head to (nx,ny), then apply gravity.

    When the head lands on food the snake GROWS (tail stays), so the search
    correctly models the extra body length that becomes available for support —
    e.g. eating a source at (0,9) grows the snake and lets the body reach all
    the way to the floor, enabling the head to climb to (0,5) while still
    being supported.

    Returns final body or None if the move is fatal.
    """
    if (nx, ny) in food_set:
        new_body = ((nx, ny),) + curr_body        # grows: tail stays
    else:
        new_body = ((nx, ny),) + curr_body[:-1]   # moves: tail removed

    if is_supported(new_body, grid, height, food_set, friendly_cells):
        return new_body
    return simulate_fall(new_body, grid, height, food_set, friendly_cells)


def count_escape_moves(body_after_eating, grid, width, height, food_set, friendly_cells=None):
    """
    After the snake has eaten a food (body_after_eating = grown body), count
    how many valid moves it has from its new head position.

    Uses the real post-eat body to correctly account for self-blocking —
    open_exits() would miss cases where the snake's own tail seals the corner.

    When growing (just ate), the next move is NOT eating, so:
      - tail will shift away (is free) UNLESS snake is length 2 (tail = reverse).
    """
    hx, hy = body_after_eating[0]
    # Same own_blocked rule as in the Dijkstra for non-eating moves
    if len(body_after_eating) <= 2:
        own_blocked = set(body_after_eating[1:])
    else:
        own_blocked = set(body_after_eating[1:-1])

    count = 0
    for _, dx, dy in DIRS:
        nx, ny = hx + dx, hy + dy
        if is_wall(nx, ny, grid, width, height):   # edge and '#' both blocked
            continue
        if (nx, ny) in own_blocked:
            continue
        next_body = ((nx, ny),) + body_after_eating[:-1]
        if (is_supported(next_body, grid, height, food_set, friendly_cells) or
                simulate_fall(next_body, grid, height, food_set, friendly_cells) is not None):
            count += 1
    return count


def is_wall(nx, ny, grid, width, height):
    """A cell is a wall if it is out-of-bounds (edge) OR a platform tile '#'."""
    if nx < 0 or nx >= width or ny < 0 or ny >= height:
        return True          # grid edge counts as wall
    return grid[ny][nx] == '#'


def open_exits(pos, grid, width, height):
    """
    Count neighbours of pos that are NOT walls.
    Both '#' tiles and grid edges are treated as walls, so a cell at the
    border of the grid counts the edge directions as blocked.
    """
    x, y = pos
    count = 0
    for _, dx, dy in DIRS:
        if not is_wall(x + dx, y + dy, grid, width, height):
            count += 1
    return count


PENALTY_TRAPPED   = 1000  # 0 escape moves after eating — truly stuck, last resort only
PENALTY_TIGHT     = 10    # 1 escape move — survivable but slightly risky, small tiebreaker


def move_cost(dir_name, final_head_y, height):
    """All moves cost 1. Penalty only applied to dead-end food, not floor proximity."""
    return 1


def dijkstra_all_reachable_food(body, food_set, grid, width, height, blocked, friendly_cells=None):
    """
    BFS that finds ALL reachable food with gravity simulation via apply_move().
    All moves cost 1. Dead-end food gets a penalty (PENALTY_TRAPPED/TIGHT).

    friendly_cells: body cells of other allied snakes — treated as support
    platforms in gravity simulation (snake can rest on top of allies).

    Returns list of (cost, first_direction, food_pos), sorted by cost.
    """
    results = []
    start = body[0]
    # heap: (cost, counter, body_tuple, first_dir)
    # counter breaks ties without comparing body tuples
    counter = 0
    heap = [(0, counter, body, None)]
    best_cost = {start: 0}

    while heap:
        cost, _, curr_body, first_dir = heapq.heappop(heap)
        hx, hy = curr_body[0]

        if cost > best_cost.get((hx, hy), float('inf')):
            continue

        # Precompute both blocked sets.
        # KEY RULE: body[1] (cell directly behind the head) is ALWAYS blocked —
        # it is the reverse direction and the game rejects backwards moves.
        # For length-2 snakes body[1:-1] is empty, so we must add body[1]
        # explicitly (it is the tail but also the only reverse direction).
        # Tail (body[-1]) is free when NOT eating because it shifts away,
        # UNLESS the snake has length 2 (tail == body[1] == reverse).
        if len(curr_body) <= 2:
            own_blocked_move = set(curr_body[1:])   # block body[1] (= tail = reverse)
        else:
            own_blocked_move = set(curr_body[1:-1]) # block middle; tail is free
        own_blocked_grow = set(curr_body[1:])       # when growing, tail stays: block all

        for dir_name, dx, dy in DIRS:
            nx, ny = hx + dx, hy + dy

            if is_wall(nx, ny, grid, width, height):   # edge and '#' both blocked
                continue
            if (nx, ny) in blocked:
                continue

            eating = (nx, ny) in food_set
            own_blocked = own_blocked_grow if eating else own_blocked_move
            if (nx, ny) in own_blocked:
                continue

            final_body = apply_move(curr_body, nx, ny, grid, height, food_set, friendly_cells)
            if final_body is None:
                continue

            actual_head = final_body[0]
            new_cost = cost + 1   # all moves cost 1

            if new_cost >= best_cost.get(actual_head, float('inf')):
                continue
            best_cost[actual_head] = new_cost

            fd = first_dir if first_dir else dir_name

            if actual_head in food_set:
                # Two-stage dead-end check:
                # Stage 1 (fast): if the food cell has only 1 physical exit,
                #   entering = only way out is backwards = illegal = guaranteed trap.
                #   No need to simulate the body.
                exits = open_exits(actual_head, grid, width, height)
                if exits <= 1:
                    # Physical dead end: only 1 non-wall neighbour → entering
                    # makes the only exit body[1] (backwards) → illegal.
                    penalty = PENALTY_TRAPPED
                else:
                    # Stage 2 (accurate): use the real grown body so self-
                    # blocking is accounted for correctly.
                    escapes = count_escape_moves(final_body, grid, width, height, food_set, friendly_cells)
                    if escapes == 0:
                        penalty = PENALTY_TRAPPED   # body seals all exits
                    elif escapes == 1:
                        penalty = PENALTY_TIGHT     # one-way street, survivable
                    else:
                        penalty = 0                 # safe, no penalty
                results.append((new_cost + penalty, fd, actual_head))

            counter += 1
            heapq.heappush(heap, (new_cost, counter, final_body, fd))

    results.sort()
    return results


def hold_position(body, food_set, grid, width, height, blocked, friendly_cells=None):
    """
    For a stuck snake (no food assigned): try to stay near current position so
    it acts as a stable platform for allied snakes to climb on.

    Picks the move whose final position (after gravity) is closest to the
    current head — preferring zero displacement (gravity returns us home).
    Falls back to safe_move order if all moves displace equally.
    """
    hx, hy = body[0]
    if len(body) <= 2:
        own_blocked = set(body[1:])
    else:
        own_blocked = set(body[1:-1])
    own_blocked_grow = set(body[1:])

    best_dir = None
    best_dist = float('inf')

    for dir_name, dx, dy in DIRS:
        nx, ny = hx + dx, hy + dy
        if is_wall(nx, ny, grid, width, height):
            continue
        eating = (nx, ny) in food_set
        own_bl = own_blocked_grow if eating else own_blocked
        if (nx, ny) in own_bl:
            continue
        if (nx, ny) in blocked:
            continue
        final_body = apply_move(body, nx, ny, grid, height, food_set, friendly_cells)
        if final_body is None:
            continue
        fhx, fhy = final_body[0]
        dist = abs(fhx - hx) + abs(fhy - hy)
        if dist < best_dist:
            best_dist = dist
            best_dir = dir_name

    return best_dir


def safe_move(body, food_set, grid, width, height, blocked):
    """
    Fallback: find any move that keeps the snake alive after gravity simulation.
    Respects no-reverse / no-self-collision rule.
    Ignores opponent blocking (better to bump opponent than fall into spikes).
    """
    hx, hy = body[0]
    if len(body) <= 2:
        own_blocked_move = set(body[1:])    # length-2: tail = reverse, always block
    else:
        own_blocked_move = set(body[1:-1])  # length 3+: tail is free
    own_blocked_grow = set(body[1:])

    # Prefer moves that don't require falling (already supported)
    for check_blocked in [blocked, set()]:   # relax opponent blocking if needed
        for dir_name, dx, dy in DIRS:
            nx, ny = hx + dx, hy + dy
            if is_wall(nx, ny, grid, width, height):   # edge and '#' both blocked
                continue
            eating = (nx, ny) in food_set
            own_blocked = own_blocked_grow if eating else own_blocked_move
            if (nx, ny) in own_blocked:
                continue
            if (nx, ny) in check_blocked:
                continue
            final_body = apply_move(body, nx, ny, grid, height, food_set)
            if final_body is not None:
                return dir_name

    return None  # truly trapped — caller must still output something


def last_resort_move(body, grid, width, height):
    """
    Absolute last resort: return ANY direction that doesn't immediately go
    out of bounds or into a '#'. Used to always have something to output.
    """
    hx, hy = body[0]
    for dir_name, dx, dy in DIRS:
        nx, ny = hx + dx, hy + dy
        if is_wall(nx, ny, grid, width, height):
            continue
        return dir_name
    return 'UP'  # can't do better — output something to avoid default direction


# ── Initialisation ─────────────────────────────────────────────────────────────

my_id = int(input())
width = int(input())
height = int(input())
grid = []
for _ in range(height):
    grid.append(input())

snakebots_per_player = int(input())
my_ids = [int(input()) for _ in range(snakebots_per_player)]
opp_ids = [int(input()) for _ in range(snakebots_per_player)]

# ── Game loop ──────────────────────────────────────────────────────────────────

while True:
    power_source_count = int(input())
    power_sources = []
    for _ in range(power_source_count):
        x, y = map(int, input().split())
        power_sources.append((x, y))
    food_set = set(power_sources)

    snakebots = {}
    snakebot_count = int(input())
    for _ in range(snakebot_count):
        parts = input().split()
        sid = int(parts[0])
        body = parse_body(parts[1])
        snakebots[sid] = body

    # Cells occupied by opponent snakebots (impassable)
    opp_occupied = set()
    for oid in opp_ids:
        if oid in snakebots:
            opp_occupied.update(snakebots[oid])

    alive = [(sid, snakebots[sid]) for sid in my_ids if sid in snakebots]

    # All friendly snake bodies (used to block paths of other friendly snakes)
    friendly_bodies = {}
    for sid, body in alive:
        friendly_bodies[sid] = set(body)

    # ── Proximity-based food assignment ────────────────────────────────────────
    # One BFS per snake finds all reachable food (with gravity sim).
    # Greedily assign: globally closest (snake, food) pair wins first pick.

    snake_options = {}
    for sid, body in alive:
        # Block: enemy bodies + all OTHER friendly snakes' bodies (can't enter)
        # friendly_cells: other friendly bodies as support platforms (can stand on top)
        other_friendly = set()
        for other_sid, other_cells in friendly_bodies.items():
            if other_sid != sid:
                other_friendly.update(other_cells)
        blocked = opp_occupied | other_friendly
        snake_options[sid] = dijkstra_all_reachable_food(
            body, food_set, grid, width, height, blocked,
            friendly_cells=other_friendly
        )

    all_pairs = []
    for sid, options in snake_options.items():
        for dist, direction, food in options:
            all_pairs.append((dist, sid, direction, food))
    all_pairs.sort()

    assignments = {}
    assignment_food = {}
    food_taken = set()
    snakes_assigned = set()

    for dist, sid, direction, food in all_pairs:
        if sid in snakes_assigned:
            continue
        if food in food_taken:
            continue
        assignments[sid] = direction
        assignment_food[sid] = (food, dist)
        food_taken.add(food)
        snakes_assigned.add(sid)

    # ── Debug: print each snake's top options and assignment ───────────────────
    for sid, body in alive:
        hx, hy = body[0]
        opts = snake_options.get(sid, [])[:5]  # top 5 options
        debug(f"Snake {sid} head=({hx},{hy}) len={len(body)}")
        for cost, direction, food in opts:
            debug(f"  option: food={food} cost={cost} dir={direction}")
        if sid in assignment_food:
            f, d = assignment_food[sid]
            debug(f"  => assigned food={f} cost={d} dir={assignments[sid]}")
        else:
            debug(f"  => NO food assigned")

    # ── Build output — EVERY alive snake must get a direction ──────────────────
    actions = []
    for sid, body in alive:
        other_friendly = set()
        for other_sid, other_cells in friendly_bodies.items():
            if other_sid != sid:
                other_friendly.update(other_cells)
        all_blocked = opp_occupied | other_friendly

        direction = assignments.get(sid)

        if not direction:
            # No food: hold position so this snake acts as a stable platform for allies
            direction = hold_position(body, food_set, grid, width, height,
                                      all_blocked, friendly_cells=other_friendly)

        if not direction:
            direction = safe_move(body, food_set, grid, width, height, all_blocked)

        if not direction:
            direction = last_resort_move(body, grid, width, height)

        actions.append(f"{sid} {direction}")

    print(';'.join(actions) if actions else "WAIT", flush=True)
