import heapq

def astar(grid, start, goal, threshold=1):
    """
    grid : 2D np.ndarray, obstacles > 1
    start : (i,j)
    goal  : (i,j)
    """
    start = tuple(start)
    goal  = tuple(goal)

    print(start, goal)

    rows, cols = grid.shape
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}

    def heuristic(a, b):
        # Manhattan distance
        return abs(a[0]-b[0]) + abs(a[1]-b[1])

    while open_set:
        _, current = heapq.heappop(open_set)
        #print(current)

        if current == goal:
            # reconstruct path
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path

        i, j = current
        for di, dj in [(0,1),(1,0),(0,-1),(-1,0)]:
            ni, nj = i+di, j+dj
            neighbor = (ni, nj)

            if 0 <= ni < rows and 0 <= nj < cols:
                if grid[ni, nj] <= threshold:  # obstacle
                    continue

                tentative_g = g_score[current] + 1
                if tentative_g < g_score.get(neighbor, float('inf')):
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score, neighbor))
                    came_from[neighbor] = current

    return None  # no path found
