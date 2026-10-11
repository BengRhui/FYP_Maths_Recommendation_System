"""
This file defines the configuration of the prerequisite graph.
"""

from collections import defaultdict

# The configurations for the graph
CARD_WIDTH = 200
CARD_HEIGHT = 100
ROW_HEIGHT = 175
CARD_GAP = 30
LANE_GAP = 28
PADDING = 26
PADDING_Y = 0
CORNER = 7
MIN_TURN = 12
GUTTER = ROW_HEIGHT - CARD_HEIGHT


# A function to build the learning path graph
def build_graph(skill_rows):

    # Extract the IDs for each skill, then create a prerequisite mapping for each of the skill
    rows_by_id = {r["skill"].id: r for r in skill_rows}
    prereqs = {
        skill_id: [p.id for p in r["skill"].prerequisites.all() if p.id in rows_by_id]
        for skill_id, r in rows_by_id.items()
    }

    # Assign the vertical row index for each skill (make sure each skill is below its prerequisites)
    row_of = _assign_rows(rows_by_id, prereqs)
    if not row_of:
        return {"nodes": [], "bands": [], "edges": [], "width": 0, "height": 0}

    # Create the prerequisite links
    links = _links(rows_by_id, prereqs, row_of)

    # Outline what items are in each row, and reserve empty slots for edges to pass through
    members, feeds = _items(links, row_of)

    # Calculate the number of rows that each edge spans
    spans = {link["key"]: link["bottom"] - link["top"] for link in links}

    # Determine the skills that are located below the current skill
    below = _reverse_feeds(feeds)

    # Determine the order of the skills arranged from left to right
    order = _order_items(members, below, rows_by_id, spans, reverse=True)

    # Convert the order into positions
    positions = _place(order, below, rows_by_id)

    # Reduce the zigzag-ness of an edge
    _straighten(links, order, positions)

    # If calculation turns out to be negative, offset everything to the right
    offset = PADDING - min(
        x - (CARD_WIDTH / 2 if item[0] == "node" else 0)
        for item, x in positions.items()
    )
    positions = {item: x + offset for item, x in positions.items()}

    # Determine the width and height of the graph
    width = round(
        max(
            x + (CARD_WIDTH / 2 if item[0] == "node" else 0)
            for item, x in positions.items()
        )
        + PADDING
    )
    height = (max(row_of.values()) + 1) * ROW_HEIGHT + 2 * PADDING_Y

    # Compile all details and pass them to the template for rendering
    return {
        "nodes": _nodes(rows_by_id, row_of, positions),
        "bands": _bands(rows_by_id, row_of, height),
        "edges": _routes(links, positions, rows_by_id),
        "width": width,
        "height": height,
    }


# A function to order skills so a skill always follows its prerequisites
def in_prerequisite_order(skill_rows):

    # Extract the skill IDs and the prerequisites
    rows_by_id = {r["skill"].id: r for r in skill_rows}
    prereqs = {
        skill_id: [p.id for p in r["skill"].prerequisites.all() if p.id in rows_by_id]
        for skill_id, r in rows_by_id.items()
    }

    # Arrange the skills in topological order
    return [rows_by_id[i] for i in _topological(list(rows_by_id), prereqs)]


# A function to assign each skill to a row index
def _assign_rows(rows_by_id, prereqs):

    # The place to store the row numbers
    row_of = {}
    offset = 0

    # Sort the skills by form level, and loop through each form
    forms = sorted({r["skill"].form_level for r in rows_by_id.values()})
    for form in forms:

        # Extract the skills in this form
        ids = [i for i, r in rows_by_id.items() if r["skill"].form_level == form]

        # Assign each skill to a row, and make sure that each skill is below its prerequisite
        highest = offset
        for skill_id in _topological(ids, prereqs):

            # Determine the row of the prerequisite skills
            parent_rows = [row_of[p] for p in prereqs[skill_id] if p in row_of]

            # Determine the row of the current skill (one row below the prerequisite skill)
            row = max([offset] + [r + 1 for r in parent_rows])
            row_of[skill_id] = row

            # Update the highest row after setting
            highest = max(highest, row)

        # The next form starts at the next row after the current form
        offset = highest + 1

    # Return the mapping of skill IDs to their rows
    return row_of


# A function to order the skills to follow prerequisites
def _topological(ids, prereqs):

    # Loop through each skill
    remaining = set(ids)
    ordered = []
    while remaining:

        # Identify the skills that do not have uncleared prerequisites
        ready = sorted(i for i in remaining if not any(p in remaining for p in prereqs[i]))

        # If there are no skills ready to be arranged, then the prerequisite is circular
        # Under this scenario, stop the arrangement and sort them alphabetically
        if not ready:
            ordered.extend(sorted(remaining))
            break

        # Add the ready skills to the order
        ordered.extend(ready)

        # Remove the arranged skills from the remaining set
        remaining -= set(ready)

    # Return the skills ordered by prerequisites
    return ordered


# A function to build the prerequisite edges
def _links(rows_by_id, prereqs, row_of):

    # Loop through each prerequisite
    links = []
    for skill_id, parents in prereqs.items():
        for parent_id in parents:

            # Add the prerequisite edges to the list of edges
            links.append(
                {
                    "key": f"{rows_by_id[parent_id]['skill'].slug}~{rows_by_id[skill_id]['skill'].slug}",
                    "source": parent_id,
                    "target": skill_id,
                    "top": row_of[parent_id],
                    "bottom": row_of[skill_id],
                }
            )

    # Return the sorted prerequisite edges
    return sorted(links, key=lambda link: (link["top"], link["bottom"], link["key"]))


# A function to build the content of each row
def _items(links, row_of):

    # Declare empty dicts to store two details:
    # Members: The items in that row
    # Feeds: The items that is above the current row and is connected
    members = defaultdict(list)
    feeds = defaultdict(list)

    # Loop through each skill and add each skill into their respective rows
    for skill_id, index in row_of.items():
        members[index].append(("node", skill_id))

    # Loop through each prerequisite link
    for link in links:

        # Begin at the source card
        previous = ("node", link["source"])

        # Walk through the rows that the link passes through, except its own starting row
        for index in range(link["top"] + 1, link["bottom"]):

            # Reserve a slot in this row to prevent other items from blocking the link
            lane = ("channel", link["key"], index)

            # The slot joins the row, and connects to the previous slot/card
            members[index].append(lane)
            feeds[lane].append(previous)

            # Move to the next slot
            previous = lane

        # The destination card connects to the last slot
        feeds[("node", link["target"])].append(previous)

    # Return the row contents and upward connections
    return members, feeds


# A function to order items in each row
def _order_items(members, feeds, rows_by_id, spans=None, reverse=False):

    # Dict to store information
    spans = spans or {}
    positions = {}
    ordered = {}

    # Loop through each row
    for index in sorted(members, reverse=reverse):

        # A function to determine the position of an item
        def barycentre(item):

            # Determine the position of the items that is above the current item
            above = [positions[f] for f in feeds.get(item, []) if f in positions]

            # The average of the position (center) gives the position of the current item
            return sum(above) / len(above) if above else -1

        # Sort items based on the value of the barycentre
        items = sorted(
            members[index], key=lambda i: (barycentre(i), _tiebreak(i, rows_by_id, spans))
        )

        # Add the position of each item to the dict
        for position, item in enumerate(items):
            positions[item] = position

        # Save the configuration for the row
        ordered[index] = items

    # Once done, return the ordered items for each row
    return ordered


# A function to invert the prerequisite link mapping
def _reverse_feeds(feeds):

    # A dict to store the inverted mapping
    below = defaultdict(list)

    # Loop through each item and map the source to the item
    for item, sources in feeds.items():
        for source in sources:
            below[source].append(item)

    # Return the dict once done
    return below


# A function to determine the tiebreaker if barycenter is the same
def _tiebreak(item, rows_by_id, spans=None):

    # If the current item is a card
    if item[0] == "node":

        # Retrieve the skill information
        skill = rows_by_id[item[1]]["skill"]

        # Return the order and title (rank based on order, then alphabetically as fallback)
        return (skill.order, skill.title)

    # If the current item is a slot, then sort based on the number of rows it spans
    span = (spans or {}).get(item[1], 0)
    return (10_000 + span, item[1])


# A function to calculate the distance between cards / slots
def _separation(left, right):

    # Calculate the width of the card / slot
    half = (CARD_WIDTH / 2 if left[0] == "node" else 0) + (
        CARD_WIDTH / 2 if right[0] == "node" else 0
    )

    # Calculate the gap between the left and right items
    gap = CARD_GAP if left[0] == "node" and right[0] == "node" else LANE_GAP

    # Return the separation distance
    return half + gap


# A function to convert the position of each item into the x-coordinate
def _place(ordered, feeds, rows_by_id):

    # Loop through the rows
    positions = {}
    for index in sorted(ordered):
        items = ordered[index]
        wishes = []

        # Loop though each item in the row
        for item in items:

            # Retrieve the positions of the items above the current item
            above = [positions[f] for f in feeds.get(item, []) if f in positions]

            # Calculate the average position
            wishes.append(sum(above) / len(above) if above else None)

        # Fill in the values for rows without known positions
        known = [w for w in wishes if w is not None]
        fallback = sum(known) / len(known) if known else 0
        wishes = [fallback if w is None else w for w in wishes]

        # Assign the x coordinate for each item
        for item, x in zip(items, _compact(items, wishes)):
            positions[item] = x

    # Return the position of each item
    return positions


# A function to make sure that long arrows are as straight as possible
def _straighten(links, ordered, positions):

    # Loop from the longest edge to the shortest edge
    for link in sorted(links, key=lambda l: l["bottom"] - l["top"], reverse=True):

        # Retrieve the slot for the edge in each row
        lanes = [("channel", link["key"], r) for r in range(link["top"] + 1, link["bottom"])]
        if not lanes:
            continue

        # Calculate the allowable reposition for the edge
        low, high = float("-inf"), float("inf")
        for lane in lanes:
            lane_low, lane_high = _window(lane, ordered, positions)
            low, high = max(low, lane_low), min(high, lane_high)

        # If reposition is impossible, just leave the edge as it is
        if low > high:
            continue

        # Reposition the edge
        source = positions[("node", link["source"])]
        target = positions[("node", link["target"])]
        if low <= source <= high:
            x = source
        elif low <= target <= high:
            x = target
        else:
            x = min(max(source, low), high)

        # Once determining the x-coordinate, write to all slots of the edge
        for lane in lanes:
            positions[lane] = x


# A function to compute how far a lane can move left and right without crowding its neighbors
def _window(lane, ordered, positions):

    # Retrieve the row index
    row = ordered[lane[2]]

    # Find the position of the slot within the row
    index = row.index(lane)

    # Begin from the leftmost ad rightmost positions
    item = lane
    low = float("-inf")
    high = float("inf")

    # Calculate the minimum separation from the left neighbor
    if index:
        low = positions[row[index - 1]] + _separation(row[index - 1], item)

    # Calculate the minimum separation from the right neighbor
    if index < len(row) - 1:
        high = positions[row[index + 1]] - _separation(item, row[index + 1])

    # Return the leftmost and rightmost positions
    return low, high


# A function to make sure that each item is as close to its desired position without overlapping
def _compact(items, wishes):

    # Calculate the position if items are pushed to right
    forward = list(wishes)
    for k in range(1, len(items)):
        forward[k] = max(forward[k], forward[k - 1] + _separation(items[k - 1], items[k]))

    # Calculate the position if items are pushed to left
    backward = list(wishes)
    for k in range(len(items) - 2, -1, -1):
        backward[k] = min(backward[k], backward[k + 1] - _separation(items[k], items[k + 1]))

    # Average the two directions to get a balanced position
    merged = [(f + b) / 2 for f, b in zip(forward, backward)]

    # Position the items based on the average to make sure they follow the minimum gap
    for k in range(1, len(items)):
        merged[k] = max(merged[k], merged[k - 1] + _separation(items[k - 1], items[k]))
    return merged


# A function to compute the y-coordinate of a card in a given row
def _card_top(index):
    return PADDING_Y + index * ROW_HEIGHT + (ROW_HEIGHT - CARD_HEIGHT) / 2


# A function to compile the coordinates for the HTML template
def _nodes(rows_by_id, row_of, positions):

    # Loop through each row and skill
    nodes = []
    for skill_id, index in sorted(row_of.items(), key=lambda kv: (kv[1], kv[0])):

        # Extract the information of the skill
        node = dict(rows_by_id[skill_id])

        # Calculate the x and y coordinates of the skill card
        node["left"] = round(positions[("node", skill_id)] - CARD_WIDTH / 2)
        node["top"] = round(_card_top(index))

        # Add the skill card to the list of nodes
        nodes.append(node)

    # Once done, return the list of nodes
    return nodes


# A function to build the macro domains (forms 1 to 3) at the left of the graph
def _bands(rows_by_id, row_of, height):

    # Loop through each skill
    first = {}
    for skill_id, index in row_of.items():

        # Find the first row of each skill
        skill = rows_by_id[skill_id]["skill"]
        if skill.form_level not in first or index < first[skill.form_level][0]:
            first[skill.form_level] = (index, skill.get_form_level_display())

    # Sort the forms and calculate their y-coordinates
    ordered = [first[form] for form in sorted(first)]
    starts = [0] + [PADDING_Y + index * ROW_HEIGHT for index, _label in ordered[1:]]

    # Calculate and return the height and offset of each form band
    return [
        {
            "label": label,
            "height": round(end - start),
            "offset": round(_card_top(index) - start),
        }
        for (index, label), start, end in zip(ordered, starts, starts[1:] + [height])
    ]


# A function to convert each prerequisite link into SVG lines
def _routes(links, positions, rows_by_id):

    # Loop through each link
    plans = []
    per_gutter = defaultdict(list)
    for link in links:

        # Extract the x-coordinate of the source card
        columns = [positions[("node", link["source"])]]

        # Loop through each row and extract the x-coordinates of each slot
        for index in range(link["top"] + 1, link["bottom"]):
            columns.append(positions[("channel", link["key"], index)])

        # Extract the x-coordinate of the target card
        columns.append(positions[("node", link["target"])])

        # Reduce the zigzag-ness of the edge
        columns = _absorb_kinks(columns)

        # Loop through each pair of card/slot
        turns = []
        for step in range(1, len(columns)):

            # If the x-coordinate changes too much
            if abs(columns[step] - columns[step - 1]) > 0.5:

                # It is considered a turn, so record the distance it moves
                gutter = link["top"] + step - 1
                per_gutter[gutter].append(
                    {
                        "left": min(columns[step - 1], columns[step]),
                        "right": max(columns[step - 1], columns[step]),
                        "id": (link["key"], len(turns)),
                    }
                )
                turns.append(step)

        # Save the details for the edge
        plans.append({"link": link, "columns": columns, "turns": turns})

    # Assign a y-coordinate to each gutter
    heights = {}
    for gutter, runs in per_gutter.items():
        heights.update(_gutter_heights(gutter, runs))

    # Loop through each plan
    edges = []
    for plan in plans:

        # Calculate the starting point of the edge
        link = plan["link"]
        points = [(plan["columns"][0], _card_top(link["top"]) + CARD_HEIGHT)]

        # Loop through each turn and calculate the coordinates for each gutter
        for index, step in enumerate(plan["turns"]):
            y = heights[(link["key"], index)]
            points.append((plan["columns"][step - 1], y))
            points.append((plan["columns"][step], y))

        # Calculate the ending point of the edge
        points.append((plan["columns"][-1], _card_top(link["bottom"])))

        # Compile the information and add to the list of edges
        edges.append(
            {
                "key": link["key"],
                "d": _rounded(points),
                "source": rows_by_id[link["source"]]["skill"].slug,
                "target": rows_by_id[link["target"]]["skill"].slug,
                "label": (
                    f"{rows_by_id[link['source']]['skill'].title}"
                    f" unlocks {rows_by_id[link['target']]['skill'].title}"
                ),
            }
        )

    # Return the edges
    return edges


# A function to reduce the zigzag-ness of an edge by removing unnecessary turns
def _absorb_kinks(columns):

    # Retrieve the x-coordinates of the edges
    snapped = list(columns)

    # Loop through each x-coordinate
    for index in range(1, len(snapped)):

        # If the turn is too small, then remove it
        if abs(snapped[index] - snapped[index - 1]) < MIN_TURN:
            snapped[index] = snapped[index - 1]

    # If the accumulative adjustment is too large, make a one last turn to the destination card
    if abs(snapped[-1] - columns[-1]) > MIN_TURN:
        snapped[-1] = columns[-1]

    # Return the x-coordinates of the edge after removing the small turns
    return snapped


# A function to adjust the y-coordinate of gutters
def _gutter_heights(gutter, runs):

    # Each run starts itself (will be assigned parent later)
    parent = list(range(len(runs)))

    # A function to find the root of the grouped edges
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    # Loop through each pair of edges
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):

            # If the edges are close to each other, group them together
            if (
                abs(runs[i]["left"] - runs[j]["left"]) < 0.5
                or abs(runs[i]["right"] - runs[j]["right"]) < 0.5
            ):
                parent[find(i)] = find(j)

    # Group the edges into clusters
    clusters = defaultdict(list)
    for i in range(len(runs)):
        clusters[find(i)].append(runs[i])

    # Merge the edges in each cluster into a single edge
    merged = [
        {
            "left": min(r["left"] for r in members),
            "right": max(r["right"] for r in members),
            "members": members,
        }
        for members in clusters.values()
    ]

    # Loop through the edges from left to right
    lanes = []
    assigned = {}
    for cluster in sorted(merged, key=lambda c: (c["left"], c["right"])):
        for index, edge in enumerate(lanes):

            # In this lane, if the edge does not overlap with the previous edge, then assign it to the same lane
            if cluster["left"] >= edge - 0.5:
                lanes[index] = max(edge, cluster["right"])
                height_index = index
                break

        # The existing levels do not have room, so open a new level
        else:
            lanes.append(cluster["right"])
            height_index = len(lanes) - 1

        # Record the level index for each edge in the cluster
        for run in cluster["members"]:
            assigned[run["id"]] = height_index

    # Calculate the y-coordinate for each edge based on its level index
    top = _card_top(gutter) + CARD_HEIGHT
    return {
        key: top + GUTTER * (index + 1) / (len(lanes) + 1)
        for key, index in assigned.items()
    }


# A function to convert turns into a rounded arc
def _rounded(points):

    # Retrieve the starting point of the path
    d = f"M {points[0][0]:.1f} {points[0][1]:.1f}"

    # Loop through each corner
    for index in range(1, len(points) - 1):

        # Convert each corner into a small arc (Bézier curve)
        corner = points[index]
        start = _towards(corner, points[index - 1])
        end = _towards(corner, points[index + 1])
        d += f" L {start[0]:.1f} {start[1]:.1f}"
        d += f" Q {corner[0]:.1f} {corner[1]:.1f} {end[0]:.1f} {end[1]:.1f}"

    # Finish with a straight line to the last point
    return d + f" L {points[-1][0]:.1f} {points[-1][1]:.1f}"


# A function to calculate the coordinates of a point from the origin to draw the rounded arc
def _towards(origin, target):

    # Calculate the distance between two points
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    length = (dx * dx + dy * dy) ** 0.5

    # If the distance is zero, return the original point
    if not length:
        return origin

    # Calculate the size of the step (default is CORNER, but take length / 2 if distance is too short)
    step = min(CORNER, length / 2)

    # Return the coordinates of the calculated point
    return (origin[0] + dx / length * step, origin[1] + dy / length * step)
