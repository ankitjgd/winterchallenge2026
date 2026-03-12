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


def is_supported(body, grid, height, food_set):
    """
    The snake is supported if at least one body part has STATIC support below it:
      - floor (y+1 >= height), OR
      - platform (#) directly below, OR
      - a power source directly below (food acts as a platform).

    Own body parts below are NOT counted — a floating chain provides no anchor.
    """
    for (x, y) in body:
        if y + 1 >= height:
            return True
        if grid[y + 1][x] == '#':
            return True
        if (x, y + 1) in food_set:
            return True
    return False


def simulate_fall(body, grid, height, food_set):
    """
    After a move, apply gravity by repeatedly shifting the whole snake DOWN
    until it is supported or a part leaves the grid / hits a platform.

    Returns the final resting body tuple, or None if the snake dies.
    Moving into a '#' during falling = head destruction = treat as invalid.
    """
    body_list = list(body)
    for _ in range(height):
        curr = tuple(body_list)
        if is_supported(curr, grid, height, food_set):
            return curr
        next_list = []
        for (x, y) in body_list:
            ny = y + 1
            if ny >= height:
                return None
            if grid[ny][x] == '#':
                return None
            next_list.append((x, ny))
        body_list = next_list
    return None


def apply_move(curr_body, nx, ny, grid, height, food_set):
    """
    Build the body after moving the head to (nx,ny), then apply gravity.
    Returns final body or None if the move is fatal.
    """
    if (nx, ny) in food_set:
        new_body = ((nx, ny),) + curr_body        # grows: tail stays
    else:
        new_body = ((nx, ny),) + curr_body[:-1]   # moves: tail removed

    if is_supported(new_body, grid, height, food_set):
        return new_body
    return simulate_fall(new_body, grid, height, food_set)


def count_escape_moves(body_after_eating, grid, width, height, food_set):
    """
    After the snake has eaten a food, count how many valid moves it has.
    Uses the real grown body to correctly account for self-blocking.
    """
    hx, hy = body_after_eating[0]
    if len(body_after_eating) <= 2:
        own_blocked = set(body_after_eating[1:])
    else:
        own_blocked = set(body_after_eating[1:-1])

    count = 0
    for _, dx, dy in DIRS:
        nx, ny = hx + dx, hy + dy
        if is_wall(nx, ny, grid, width, height):
            continue
        if (nx, ny) in own_blocked:
            continue
        next_body = ((nx, ny),) + body_after_eating[:-1]
        if (is_supported(next_body, grid, height, food_set) or
                simulate_fall(next_body, grid, height, food_set) is not None):
            count += 1
    return count


def is_wall(nx, ny, grid, width, height):
    """A cell is a wall if it is out-of-bounds (edge) OR a platform tile '#'."""
    if nx < 0 or nx >= width or ny < 0 or ny >= height:
        return True
    return grid[ny][nx] == '#'


def open_exits(pos, grid, width, height):
    """Count neighbours of pos that are NOT walls (edges and '#' are walls)."""
    x, y = pos
    count = 0
    for _, dx, dy in DIRS:
        if not is_wall(x + dx, y + dy, grid, width, height):
            count += 1
    return count


PENALTY_TRAPPED   = 1000  # 0 escape moves after eating — truly stuck
PENALTY_TIGHT     = 10    # 1 escape move — survivable but risky


def dijkstra_all_reachable_food(body, food_set, grid, width, height, blocked):
    """
    BFS that finds ALL reachable food with gravity simulation via apply_move().
    All moves cost 1. Dead-end food gets a penalty (PENALTY_TRAPPED/TIGHT).

    Returns list of (cost, first_direction, food_pos), sorted by cost.
    """
    results = []
    start = body[0]
    counter = 0
    heap = [(0, counter, body, None)]
    best_cost = {start: 0}

    while heap:
        cost, _, curr_body, first_dir = heapq.heappop(heap)
        hx, hy = curr_body[0]

        if cost > best_cost.get((hx, hy), float('inf')):
            continue

        if len(curr_body) <= 2:
            own_blocked_move = set(curr_body[1:])
        else:
            own_blocked_move = set(curr_body[1:-1])
        own_blocked_grow = set(curr_body[1:])

        for dir_name, dx, dy in DIRS:
            nx, ny = hx + dx, hy + dy

            if is_wall(nx, ny, grid, width, height):
                continue
            if (nx, ny) in blocked:
                continue

            eating = (nx, ny) in food_set
            own_blocked = own_blocked_grow if eating else own_blocked_move
            if (nx, ny) in own_blocked:
                continue

            final_body = apply_move(curr_body, nx, ny, grid, height, food_set)
            if final_body is None:
                continue

            actual_head = final_body[0]
            new_cost = cost + 1

            if new_cost >= best_cost.get(actual_head, float('inf')):
                continue
            best_cost[actual_head] = new_cost

            fd = first_dir if first_dir else dir_name

            if actual_head in food_set:
                exits = open_exits(actual_head, grid, width, height)
                if exits <= 1:
                    penalty = PENALTY_TRAPPED
                else:
                    escapes = count_escape_moves(final_body, grid, width, height, food_set)
                    if escapes == 0:
                        penalty = PENALTY_TRAPPED
                    elif escapes == 1:
                        penalty = PENALTY_TIGHT
                    else:
                        penalty = 0
                results.append((new_cost + penalty, fd, actual_head))

            counter += 1
            heapq.heappush(heap, (new_cost, counter, final_body, fd))

    results.sort()
    return results


def safe_move(body, food_set, grid, width, height, blocked):
    """
    Fallback: find any move that keeps the snake alive after gravity simulation.
    Respects no-reverse / no-self-collision rule.
    """
    hx, hy = body[0]
    if len(body) <= 2:
        own_blocked_move = set(body[1:])
    else:
        own_blocked_move = set(body[1:-1])
    own_blocked_grow = set(body[1:])

    for check_blocked in [blocked, set()]:   # relax opponent blocking if needed
        for dir_name, dx, dy in DIRS:
            nx, ny = hx + dx, hy + dy
            if is_wall(nx, ny, grid, width, height):
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

    return None


def last_resort_move(body, grid, width, height):
    """Return ANY direction that doesn't immediately go out of bounds or into '#'."""
    hx, hy = body[0]
    for dir_name, dx, dy in DIRS:
        nx, ny = hx + dx, hy + dy
        if is_wall(nx, ny, grid, width, height):
            continue
        return dir_name
    return 'UP'


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
    snake_options = {}
    for sid, body in alive:
        other_friendly = set()
        for other_sid, other_cells in friendly_bodies.items():
            if other_sid != sid:
                other_friendly.update(other_cells)
        blocked = opp_occupied | other_friendly
        snake_options[sid] = dijkstra_all_reachable_food(
            body, food_set, grid, width, height, blocked
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
        opts = snake_options.get(sid, [])[:5]
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
            direction = safe_move(body, food_set, grid, width, height, all_blocked)

        if not direction:
            direction = last_resort_move(body, grid, width, height)

        actions.append(f"{sid} {direction}")

    print(';'.join(actions) if actions else "WAIT", flush=True)
