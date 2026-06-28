# 第 6 课：程序化地图生成与可解性验证算法规范设计

> 本文档定义 Microsoft Treasure Hunt 复刻项目中的**程序化关卡地图生成系统 (Procedural Level Generator)** 与**可解性验证算法 (Solvability Verification Algorithm)**。本文档与 `01_core_gameplay.md`（瓦片系统）、`03_interactive_elements.md`（实体分类）、`04_tools_and_economy.md`（道具系统）配合使用，构成完整的关卡数据生成契约。所有后续课程应严格遵循本文档所定义的契约。

---

## 目录

1. [地图尺寸与元素配置动态缩放 (Level Parameter Scaling)](#1-地图尺寸与元素配置动态缩放-level-parameter-scaling)
2. [三阶段生成管道 (Three-Stage Generation Pipeline)](#2-三阶段生成管道-three-stage-generation-pipeline)
3. [物理与逻辑可解性验证算法 (Solvability Verification Algorithm)](#3-物理与逻辑可解性验证算法-solvability-verification-algorithm)
4. [数据结构定义与核心生成流伪代码 (Core Level Generator API)](#4-数据结构定义与核心生成流伪代码-core-level-generator-api)

---

## 1. 地图尺寸与元素配置动态缩放 (Level Parameter Scaling)

### 1.1 缩放总览

所有地图参数由**关卡编号 `levelNum`** 唯一确定，采用分段线性插值策略，确保难度曲线平滑递增。

```
Level Parameter f(levelNum) = f_min + (f_max - f_min) * clamp((levelNum - 1) / 19, 0, 1)
```

其中 `levelNum ∈ [1, +∞)`，超过 20 关时参数锁定在 Level 20 的上限值。

### 1.2 地图大小 (Grid Size)

| 参数 | Level 1 | Level 20+ | 说明 |
|------|---------|-----------|------|
| `gridWidth` | 15 | 40 | 网格宽度（列数） |
| `gridHeight` | 15 | 40 | 网格高度（行数） |

**约束**：始终为正方形网格（`gridWidth === gridHeight`），便于算法统一处理。

### 1.3 陷阱密度 (Trap Density)

| 参数 | Level 1 | Level 20+ | 说明 |
|------|---------|-----------|------|
| `trapDensity` | 10% | 22% | 陷阱占可揭露区域（泥土瓦片）的比例 |

**计算公式**：

```
trapCount = floor(uncoveredArea * trapDensity)
```

其中 `uncoveredArea = totalTiles - wallTiles - spawnSafeZoneTiles`。

### 1.4 障碍物占比 (Obstacle Ratio)

| 元素类型 | Level 1 占比 | Level 20+ 占比 | 说明 |
|----------|-------------|---------------|------|
| 不可破坏墙 (Wall) | 8% | 12% | 占总格子数比例 |
| 泥墙 (Dirt Wall) | 10% | 18% | 占总格子数比例 |

**约束**：Wall 与 Dirt Wall 的放置不得阻断地图的连通性（由阶段一保证）。

### 1.5 锁钥对数量 (Lock-Key Pairs)

| Level 范围 | 锁钥对数量 | 说明 |
|------------|-----------|------|
| 1 - 5 | 1 | 仅蓝色门 + 蓝色钥匙 |
| 6 - 10 | 2 | 蓝色门 + 绿色门，各配对应钥匙 |
| 11 - 15 | 3 | 红/绿/蓝三门 + 三把钥匙 |
| 16 - 20 | 3 + 出口钥匙 | 三门 + 出口门需特殊钥匙 |
| 20+ | 3 + 出口钥匙 + 嵌套 | 多重嵌套（如：红门后绿门后蓝钥匙） |

**嵌套规则**：高级关卡中，钥匙之间可形成依赖链（如：蓝色钥匙被绿色门保护，绿色钥匙被红色门保护），但**不允许循环依赖**（死锁检测见 §3）。

### 1.6 缩放函数伪代码

```typescript
function getLevelParams(levelNum: number): LevelParams {
  const t = Math.min(Math.max((levelNum - 1) / 19, 0), 1); // 归一化 [0, 1]

  return {
    gridSize: Math.round(15 + (40 - 15) * t),
    trapDensity: 0.10 + (0.22 - 0.10) * t,
    wallDensity: 0.08 + (0.12 - 0.08) * t,
    dirtWallDensity: 0.10 + (0.18 - 0.10) * t,
    lockKeyPairs: getLockKeyCount(levelNum),
    hasExitKey: levelNum >= 16,
  };
}

function getLockKeyCount(levelNum: number): number {
  if (levelNum <= 5) return 1;
  if (levelNum <= 10) return 2;
  return 3;
}
```

---

## 2. 三阶段生成管道 (Three-Stage Generation Pipeline)

```
┌─────────────────────────────────────────────────────────────────┐
│                    generateLevel(levelNum)                       │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  阶段一       │    │  阶段二       │    │  阶段三       │      │
│  │  物理路径生成  │───▶│  锁钥拓扑布局  │───▶│  雷区填充     │      │
│  │  (Stage 1)   │    │  (Stage 2)   │    │  (Stage 3)   │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  连通图/迷宫生成      依赖树构建 + 验证     陷阱放置 + 数字计算    │
│  + 起点/出口门        (死锁防护)           + 安全区保护          │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 阶段一：物理路径生成 (Physical Layout Generation)

#### 2.1.1 目标

生成一个**连通图结构**，确保从起点到出口门存在至少一条可通行路径（忽略陷阱，仅考虑物理障碍）。

#### 2.1.2 算法选择：Randomized Prim 算法

采用随机化 Prim 算法生成迷宫主干道，步骤如下：

1. **初始化**：在 `gridSize × gridSize` 的网格上，选择 `(1, 1)` 作为起始单元格（起点 Spawn Point）。
2. **前沿列表**：将起始单元格的所有相邻单元格（距离为 2）加入前沿列表 (Frontier List)。
3. **循环扩展**：
   - 从前沿列表中随机选取一个单元格 `F`。
   - 找到 `F` 的所有已访问邻居（距离为 2）。
   - 随机选择一个已访问邻居 `N`，打通 `N` 与 `F` 之间的墙（将中间格子设为通路）。
   - 将 `F` 标记为已访问，将 `F` 的新邻居加入前沿列表。
4. **终止**：当前沿列表为空时，迷宫生成完成。

#### 2.1.3 起点与出口门

| 元素 | 位置 | 约束 |
|------|------|------|
| 起点 (Spawn) | `(1, 1)` | 固定左上角，3×3 安全区中心 |
| 出口门 (Exit Gate) | `(gridSize-2, gridSize-2)` | 固定右下角区域 |

**连通性保证**：Prim 算法生成的迷宫天然连通，出口门一定可达。

#### 2.1.4 额外通路（环路生成）

为避免迷宫过于线性（单一通路），在生成后随机拆除部分非关键墙壁：

```
loopFactor = 0.1 + 0.05 * t  // 10% ~ 15% 的额外拆除率
```

拆除条件：拆除后不导致起点 3×3 安全区暴露于陷阱区域。

#### 2.1.5 障碍物放置

在通路确定后，于非通路区域放置：

- **不可破坏墙 (Wall)**：填充至 `wallDensity` 上限。
- **泥墙 (Dirt Wall)**：填充至 `dirtWallDensity` 上限。

**约束**：障碍物不得阻断已有通路的连通性。

#### 2.1.6 阶段一伪代码

```typescript
function stage1PhysicalLayout(params: LevelParams): PhysicalLayout {
  const { gridSize } = params;
  const grid = createGrid(gridSize, gridSize, TileState.WALL);

  // Step 1: Randomized Prim Maze Generation
  const start = { x: 1, y: 1 };
  grid[start.y][start.x] = TileState.DIRT;
  const frontier = getFrontierCells(start, grid);

  while (frontier.length > 0) {
    const idx = randomInt(0, frontier.length);
    const cell = frontier.splice(idx, 1)[0];
    const neighbors = getVisitedNeighbors(cell, grid);

    if (neighbors.length > 0) {
      const neighbor = neighbors[randomInt(0, neighbors.length)];
      // Carve passage between cell and neighbor
      const wallX = (cell.x + neighbor.x) / 2;
      const wallY = (cell.y + neighbor.y) / 2;
      grid[wallY][wallX] = TileState.DIRT;
      grid[cell.y][cell.x] = TileState.DIRT;
      frontier.push(...getFrontierCells(cell, grid));
    }
  }

  // Step 2: Spawn & Exit Gate
  const spawn = start;
  const exit = { x: gridSize - 2, y: gridSize - 2 };
  grid[spawn.y][spawn.x] = TileState.SPAWN;
  grid[exit.y][exit.x] = TileState.EXIT_GATE;

  // Step 3: Loop generation (remove some walls)
  addLoops(grid, params.loopFactor);

  // Step 4: Place obstacles in non-path areas
  placeObstacles(grid, params.wallDensity, params.dirtWallDensity);

  return { grid, spawn, exit };
}
```

---

### 2.2 阶段二：锁钥依赖拓扑布局 (Key-Lock Dependency Placement)

#### 2.2.1 目标

在已生成的物理地图上放置钥匙和对应的锁门，确保：
1. 每把钥匙都能在不穿过其对应锁门的情况下被获取（无死锁）。
2. 依赖关系形成**有向无环图 (DAG)**。

#### 2.2.2 锁钥约束树 (Dependency Tree)

```
Dependency Tree 示例 (Level 16+):

                    [Exit Key]
                        │
                    [Blue Gate]
                        │
                    [Blue Key]
                   ╱
            [Green Gate]
                 │
            [Green Key]
           ╱
     [Red Gate]
          │
     [Red Key]
         │
       [Spawn]
```

**核心约束**：若存在门 `G` 分隔区域 `A`（含起点）与区域 `B`，则 `G` 对应的钥匙 `g` 必须放置在区域 `A` 中。

#### 2.2.3 逆向生成算法 (Reverse Placement Strategy)

采用**从出口向起点逆向放置**的策略：

1. **确定路径**：从出口门向起点执行 BFS，获取主路径 `P = [exit, ..., spawn]`。
2. **选择门位置**：在路径 `P` 上均匀分布 `lockKeyPairs` 个位置放置锁门。
3. **放置钥匙**：对于每扇锁门 `G_i`（位于路径位置 `p_i`）：
   - 将地图分为 `G_i` 前段（靠近起点）和 `G_i` 后段（靠近出口）。
   - 钥匙 `k_i` 必须放置在**前段区域**的某个非路径格子上。
   - 使用 BFS 验证：从起点出发，不经过 `G_i`，可以到达 `k_i` 的位置。
4. **出口钥匙**（Level 16+）：出口门需要特殊钥匙，该钥匙放置在最后一扇锁门之前。

#### 2.2.4 死锁检测 (Deadlock Detection)

```
Deadlock Condition: 钥匙 k 被门 G 保护，且打开门 G 需要钥匙 k。

检测方法:
1. 构建依赖图：对每把钥匙 k_i，记录其被哪些门保护。
2. 执行拓扑排序：若图中存在环，则判定为死锁。
3. 若检测到死锁，重新执行阶段二的钥匙放置（Re-seed）。
```

#### 2.2.5 多重嵌套规则 (Level 20+)

当 `lockKeyPairs >= 3` 时，允许嵌套依赖：

- 钥匙 A 被门 B 保护，钥匙 B 被门 C 保护。
- 获取顺序：C → B → A（从起点侧向出口侧依次解锁）。
- **禁止**：循环嵌套（A → B → C → A）。

#### 2.2.6 阶段二伪代码

```typescript
function stage2KeyLockPlacement(
  layout: PhysicalLayout,
  params: LevelParams
): KeyLockLayout {
  const { grid, spawn, exit } = layout;
  const pairs = params.lockKeyPairs;
  const path = bfsPath(grid, spawn, exit); // 主路径

  const gates: GatePlacement[] = [];
  const keys: KeyPlacement[] = [];
  const dependencyGraph = new DAG();

  // Step 1: Distribute gates along the path
  for (let i = 0; i < pairs; i++) {
    const pathIdx = Math.floor((path.length * (i + 1)) / (pairs + 1));
    const gatePos = path[pathIdx];
    const gateType = getGateColor(i); // 0=Red, 1=Green, 2=Blue

    gates.push({ position: gatePos, color: gateType });
    grid[gatePos.y][gatePos.x] = TileState[`GATE_${gateType}`];
  }

  // Step 2: Place keys (reverse order — outermost gate first)
  for (let i = pairs - 1; i >= 0; i--) {
    const gate = gates[i];
    // Find reachable area BEFORE this gate
    const reachableArea = bfsReachable(grid, spawn, {
      blockedGate: gate.position,
    });

    // Place key in a non-path, reachable dirt tile
    const keyPos = findDirtTile(reachableArea, path);
    keys.push({ position: keyPos, color: gate.color });
    grid[keyPos.y][keyPos.x] = TileState[`KEY_${gate.color}`];

    // Register dependency
    dependencyGraph.addEdge(gate.color, `key_${gate.color}`);
  }

  // Step 3: Deadlock detection (topological sort)
  if (dependencyGraph.hasCycle()) {
    return stage2KeyLockPlacement(layout, params); // Re-seed
  }

  // Step 4: Exit key (Level 16+)
  if (params.hasExitKey) {
    const exitKeyPos = findDirtTile(
      bfsReachable(grid, spawn, { blockedGate: gates[0].position }),
      path
    );
    keys.push({ position: exitKeyPos, color: 'EXIT' });
    grid[exitKeyPos.y][exitKeyPos.x] = TileState.KEY_EXIT;
  }

  return { gates, keys, dependencyGraph };
}
```

---

### 2.3 阶段三：扫雷雷区填充与数字生成 (Minesweeper Tile Populating)

#### 2.3.1 目标

在非主干道的泥土区域放置陷阱，并为每个瓦片计算周围陷阱数量。

#### 2.3.2 起点安全区保护

```
安全区规则: 以起点 (1,1) 为中心的 3×3 区域内绝对不生成陷阱。

安全区范围: 坐标 (x, y) 满足 x ∈ [0, 2], y ∈ [0, 2]
```

#### 2.3.3 陷阱放置算法

1. **计算可放置区域**：

```
placeableTiles = allDirtTiles - spawnSafeZone(3×3) - pathTiles - gateTiles - keyTiles
```

2. **随机采样**：

```
trapCount = floor(placeableTiles.length * trapDensity)
selectedTiles = randomSample(placeableTiles, trapCount)
```

3. **写入地图**：

```
for (pos of selectedTiles) {
  grid[pos.y][pos.x] = TileState.TRAP;
}
```

#### 2.3.4 数字生成 (Adjacent Trap Count)

对每个非陷阱瓦片，计算其 8 方向邻居中的陷阱数量：

```
for each tile (x, y) in grid:
  if grid[y][x] is not TRAP and not WALL and not GATE:
    grid[y][x].adjacentTraps = countTrapsIn8Neighbors(grid, x, y)
```

**数字范围**：0 - 8（0 表示周围无陷阱，渲染时显示空白）。

#### 2.3.5 阶段三伪代码

```typescript
function stage3MinesweeperFill(
  layout: KeyLockLayout,
  params: LevelParams
): PopulatedLevel {
  const { grid, spawn } = layout;

  // Step 1: Define safe zone (3x3 around spawn)
  const safeZone = new Set<string>();
  for (let dy = -1; dy <= 1; dy++) {
    for (let dx = -1; dx <= 1; dx++) {
      safeZone.add(`${spawn.x + dx},${spawn.y + dy}`);
    }
  }

  // Step 2: Collect placeable tiles
  const placeable: Position[] = [];
  for (let y = 0; y < grid.length; y++) {
    for (let x = 0; x < grid[0].length; x++) {
      const key = `${x},${y}`;
      if (
        grid[y][x] === TileState.DIRT &&
        !safeZone.has(key) &&
        !isPathTile(x, y) &&
        !isGateTile(grid[y][x]) &&
        !isKeyTile(grid[y][x])
      ) {
        placeable.push({ x, y });
      }
    }
  }

  // Step 3: Random trap placement
  const trapCount = Math.floor(placeable.length * params.trapDensity);
  const traps = randomSample(placeable, trapCount);
  for (const pos of traps) {
    grid[pos.y][pos.x] = TileState.TRAP;
  }

  // Step 4: Compute adjacent trap counts
  for (let y = 0; y < grid.length; y++) {
    for (let x = 0; x < grid[0].length; x++) {
      if (grid[y][x] !== TileState.TRAP && grid[y][x] !== TileState.WALL) {
        grid[y][x].adjacentTraps = countAdjacentTraps(grid, x, y);
      }
    }
  }

  return { ...layout, trapPositions: traps };
}

function countAdjacentTraps(grid: Tile[][], x: number, y: number): number {
  let count = 0;
  for (let dy = -1; dy <= 1; dy++) {
    for (let dx = -1; dx <= 1; dx++) {
      if (dx === 0 && dy === 0) continue;
      const nx = x + dx, ny = y + dy;
      if (ny >= 0 && ny < grid.length && nx >= 0 && nx < grid[0].length) {
        if (grid[ny][nx] === TileState.TRAP) count++;
      }
    }
  }
  return count;
}
```

---

## 3. 物理与逻辑可解性验证算法 (Solvability Verification Algorithm)

### 3.1 验证总览

```
┌─────────────────────────────────────────────────────┐
│           verifySolvability(levelData)               │
│                                                      │
│  ┌──────────────────┐    ┌──────────────────────┐   │
│  │ 物理可达性验证     │    │ 逻辑可推导性验证        │   │
│  │ (Physical BFS)   │    │ (Solver Simulator)   │   │
│  │ [必须通过]        │    │ [推荐通过]            │   │
│  └──────────────────┘    └──────────────────────┘   │
│           │                       │                  │
│           ▼                       ▼                  │
│    起点→出口门可达?          仅靠逻辑可揭开通路?       │
│    (含钥匙收集模拟)          (无猜测、无道具)          │
│                                                      │
│  两者均通过 → ✅ 可解                                 │
│  任一失败   → ❌ 重新生成 (Re-seed)                   │
└─────────────────────────────────────────────────────┘
```

### 3.2 物理可达性验证 (Physical Reachability)

#### 3.2.1 算法：BFS with Inventory Simulation

从起点出发，模拟玩家移动和钥匙收集过程，验证是否能到达出口门。

**状态定义**：

```typescript
interface BFSState {
  position: Position;
  keys: Set<KeyColor>;   // 已收集的钥匙
  gatesPassed: Set<Position>; // 已通过的门
}
```

**转移规则**：

```
对于当前状态 S，遍历 4 方向邻居 N:
  1. N 是 WALL → 不可通行
  2. N 是 DIRT_WALL → 可通行（挖掘后变为 DIRT）
  3. N 是 GATE_{COLOR} → 仅当 S.keys 包含对应颜色时可通行
  4. N 是 KEY_{COLOR} → 可通行，将 COLOR 加入 S.keys
  5. N 是 EXIT_GATE → 若拥有出口钥匙（如需要），到达终点
  6. N 是 DIRT / UNCOVERED / SPAWN → 可通行
  7. N 是 TRAP → 可通行（物理上可通过，但会受伤）
```

#### 3.2.2 物理可达性伪代码

```typescript
function verifyPhysicalReachability(level: LevelData): boolean {
  const { grid, spawn, exit, keys, gates } = level;
  const initialState: BFSState = {
    position: spawn,
    keys: new Set(),
    gatesPassed: new Set(),
  };

  const queue: BFSState[] = [initialState];
  const visited = new Set<string>();
  visited.add(stateKey(initialState));

  while (queue.length > 0) {
    const current = queue.shift()!;

    // Check if reached exit
    if (current.position.x === exit.x && current.position.y === exit.y) {
      if (!level.requiresExitKey || current.keys.has('EXIT')) {
        return true;
      }
    }

    // Explore neighbors
    for (const dir of DIRECTIONS_4) {
      const nextPos = {
        x: current.position.x + dir.x,
        y: current.position.y + dir.y,
      };

      if (!inBounds(grid, nextPos)) continue;

      const tile = grid[nextPos.y][nextPos.x];
      const nextState = { ...current, position: nextPos };

      // Gate check
      if (isGateTile(tile)) {
        const requiredKey = getGateColor(tile);
        if (!current.keys.has(requiredKey)) continue;
        nextState.gatesPassed.add(`${nextPos.x},${nextPos.y}`);
      }

      // Key collection
      if (isKeyTile(tile)) {
        nextState.keys = new Set(nextState.keys);
        nextState.keys.add(getKeyColor(tile));
      }

      const key = stateKey(nextState);
      if (!visited.has(key)) {
        visited.add(key);
        queue.push(nextState);
      }
    }
  }

  return false; // Exit not reachable
}

function stateKey(state: BFSState): string {
  const keysStr = [...state.keys].sort().join(',');
  return `${state.position.x},${state.position.y}|${keysStr}`;
}
```

### 3.3 逻辑可推导性验证 (Solvable Solver Simulator)

#### 3.3.1 设计目标

模拟一个"完美玩家"仅凭逻辑推理（不使用道具、不猜测、不踩雷）揭开瓦片的能力，验证主干道是否可被逻辑揭开。

#### 3.3.2 求解器规则

**规则一：单格排除 (Single-Cell Elimination)**

```
若数字 N 的未揭开邻居数 == N，则所有未揭开邻居都是陷阱 → 标记为 TRAP_FLAG。
若数字 N 的已标记陷阱数 == N，则其余未揭开邻居都是安全的 → 揭开。
```

**规则二：Chording (和弦点击)**

```
若数字 N 周围的陷阱已全部标记，点击该数字可揭开所有剩余安全邻居。
```

**规则三：边界传播 (Boundary Propagation)**

```
从起点安全区开始，使用 BFS 揭开所有可通过逻辑确定的瓦片。
每次揭开新瓦片后，重新应用规则一和二，直到无法继续。
```

#### 3.3.3 求解器伪代码

```typescript
function verifyLogicalSolvability(level: LevelData): boolean {
  const { grid, spawn, exit } = level;
  const state = createSolverState(grid, spawn);

  let progress = true;
  while (progress) {
    progress = false;

    for (let y = 0; y < state.height; y++) {
      for (let x = 0; x < state.width; x++) {
        if (state.revealed[y][x] && state.adjacentTraps[y][x] > 0) {
          const neighbors = getNeighbors(x, y);
          const hidden = neighbors.filter(n => !state.revealed[n.y][n.x] && !state.flagged[n.y][n.x]);
          const flagged = neighbors.filter(n => state.flagged[n.y][n.x]);
          const trapCount = state.adjacentTraps[y][x];

          // Rule 1: All hidden are traps
          if (hidden.length === trapCount - flagged.length) {
            for (const n of hidden) {
              state.flagged[n.y][n.x] = true;
              progress = true;
            }
          }

          // Rule 1 reverse: All traps found, rest is safe
          if (flagged.length === trapCount) {
            for (const n of hidden) {
              state.revealed[n.y][n.x] = true;
              progress = true;
            }
          }
        }
      }
    }
  }

  // Check: Is the path to exit fully revealed without hitting traps?
  return isPathRevealed(state, spawn, exit);
}

function isPathRevealed(state: SolverState, spawn: Position, exit: Position): boolean {
  // BFS on revealed tiles only
  const queue = [spawn];
  const visited = new Set<string>();
  visited.add(`${spawn.x},${spawn.y}`);

  while (queue.length > 0) {
    const pos = queue.shift()!;
    if (pos.x === exit.x && pos.y === exit.y) return true;

    for (const dir of DIRECTIONS_8) {
      const next = { x: pos.x + dir.x, y: pos.y + dir.y };
      const key = `${next.x},${next.y}`;
      if (!visited.has(key) && state.revealed[next.y][next.x] && !state.flagged[next.y][next.x]) {
        visited.add(key);
        queue.push(next);
      }
    }
  }
  return false;
}
```

### 3.4 综合验证与 Re-seed 策略

```typescript
function verifySolvability(level: LevelData): SolvabilityResult {
  const physicalOk = verifyPhysicalReachability(level);
  if (!physicalOk) {
    return { solvable: false, reason: 'PHYSICAL_UNREACHABLE' };
  }

  const logicalOk = verifyLogicalSolvability(level);
  if (!logicalOk) {
    return { solvable: false, reason: 'LOGICAL_UNSOLVABLE' };
  }

  return { solvable: true, reason: null };
}

// Re-seed 策略
function generateWithVerification(levelNum: number, maxAttempts: number = 10): LevelData {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const seed = generateSeed(levelNum, attempt);
    const level = generateLevel(levelNum, seed);
    const result = verifySolvability(level);

    if (result.solvable) {
      return level;
    }
  }

  // Fallback: 降低陷阱密度后重试
  const params = getLevelParams(levelNum);
  params.trapDensity *= 0.8;
  return generateLevel(levelNum, generateSeed(levelNum, 0));
}
```

---

## 4. 数据结构定义与核心生成流伪代码 (Core Level Generator API)

### 4.1 核心数据结构

```typescript
// ===== 关卡参数 =====
interface LevelParams {
  gridSize: number;
  trapDensity: number;
  wallDensity: number;
  dirtWallDensity: number;
  lockKeyPairs: number;
  hasExitKey: boolean;
  loopFactor: number;
}

// ===== 瓦片状态枚举 =====
enum TileState {
  DIRT = 'DIRT',
  UNCOVERED = 'UNCOVERED',
  TRAP = 'TRAP',
  WALL = 'WALL',
  DIRT_WALL = 'DIRT_WALL',
  SPAWN = 'SPAWN',
  EXIT_GATE = 'EXIT_GATE',
  KEY_RED = 'KEY_RED',
  KEY_GREEN = 'KEY_GREEN',
  KEY_BLUE = 'KEY_BLUE',
  KEY_EXIT = 'KEY_EXIT',
  GATE_RED = 'GATE_RED',
  GATE_GREEN = 'GATE_GREEN',
  GATE_BLUE = 'GATE_BLUE',
}

// ===== 瓦片数据 =====
interface Tile {
  x: number;
  y: number;
  state: TileState;
  adjacentTraps: number;  // 0-8
  isRevealed: boolean;
  isFlagged: boolean;
  layer0: TileState;       // 地形层
  layer1: EntityType | null; // 障碍物层
  layer2: EntityType | null; // 收集物层
}

// ===== 关卡数据 =====
interface LevelData {
  levelNum: number;
  grid: Tile[][];
  width: number;
  height: number;
  spawn: Position;
  exit: Position;
  trapPositions: Position[];
  gates: GatePlacement[];
  keys: KeyPlacement[];
  params: LevelParams;
  requiresExitKey: boolean;
}

// ===== 位置 =====
interface Position {
  x: number;
  y: number;
}

// ===== 门布局 =====
interface GatePlacement {
  position: Position;
  color: 'RED' | 'GREEN' | 'BLUE';
}

// ===== 钥匙布局 =====
interface KeyPlacement {
  position: Position;
  color: 'RED' | 'GREEN' | 'BLUE' | 'EXIT';
}

// ===== 中间状态 =====
interface PhysicalLayout {
  grid: Tile[][];
  spawn: Position;
  exit: Position;
}

interface KeyLockLayout extends PhysicalLayout {
  gates: GatePlacement[];
  keys: KeyPlacement[];
  dependencyGraph: DAG;
}

interface PopulatedLevel extends KeyLockLayout {
  trapPositions: Position[];
}

// ===== 可解性验证结果 =====
interface SolvabilityResult {
  solvable: boolean;
  reason: 'PHYSICAL_UNREACHABLE' | 'LOGICAL_UNSOLVABLE' | null;
}
```

### 4.2 主函数：generateLevel

```typescript
function generateLevel(levelNum: number, seed?: number): LevelData {
  // Step 0: Initialize RNG with seed
  const rng = seed !== undefined ? createSeededRNG(seed) : createDefaultRNG();
  setGlobalRNG(rng);

  // Step 1: Compute level parameters
  const params = getLevelParams(levelNum);

  // Step 2: Stage 1 — Physical Layout
  const physicalLayout = stage1PhysicalLayout(params);

  // Step 3: Stage 2 — Key-Lock Dependency Placement
  const keyLockLayout = stage2KeyLockPlacement(physicalLayout, params);

  // Step 4: Stage 3 — Minesweeper Tile Populating
  const populatedLevel = stage3MinesweeperFill(keyLockLayout, params);

  // Step 5: Assemble LevelData
  const levelData: LevelData = {
    levelNum,
    grid: populatedLevel.grid,
    width: params.gridSize,
    height: params.gridSize,
    spawn: populatedLevel.spawn,
    exit: populatedLevel.exit,
    trapPositions: populatedLevel.trapPositions,
    gates: populatedLevel.gates,
    keys: populatedLevel.keys,
    params,
    requiresExitKey: params.hasExitKey,
  };

  return levelData;
}
```

### 4.3 验证函数：verifySolvability

```typescript
function verifySolvability(level: LevelData): SolvabilityResult {
  // Phase A: Physical Reachability Check
  // - BFS from spawn with inventory simulation
  // - Verify exit gate is reachable with collected keys
  const physicalOk = verifyPhysicalReachability(level);
  if (!physicalOk) {
    return { solvable: false, reason: 'PHYSICAL_UNREACHABLE' };
  }

  // Phase B: Logical Solvability Check
  // - Simulate a perfect minesweeper solver
  // - Verify main path can be revealed without guessing
  const logicalOk = verifyLogicalSolvability(level);
  if (!logicalOk) {
    return { solvable: false, reason: 'LOGICAL_UNSOLVABLE' };
  }

  return { solvable: true, reason: null };
}
```

### 4.4 完整调用流

```
generateLevel(levelNum)
  │
  ├── getLevelParams(levelNum)        → LevelParams
  │
  ├── stage1PhysicalLayout(params)    → PhysicalLayout
  │     ├── Randomized Prim Maze
  │     ├── Place Spawn & Exit Gate
  │     ├── Add Loops
  │     └── Place Obstacles (Wall, DirtWall)
  │
  ├── stage2KeyLockPlacement(layout)  → KeyLockLayout
  │     ├── BFS Path Finding
  │     ├── Distribute Gates on Path
  │     ├── Reverse Key Placement
  │     ├── Deadlock Detection (DAG)
  │     └── Exit Key (Level 16+)
  │
  ├── stage3MinesweeperFill(layout)   → PopulatedLevel
  │     ├── Safe Zone Protection (3×3)
  │     ├── Random Trap Placement
  │     └── Adjacent Trap Count Calc
  │
  └── verifySolvability(levelData)    → SolvabilityResult
        ├── Physical BFS (with keys)
        └── Logical Solver Simulation
              ├── Single-Cell Elimination
              ├── Chording
              └── Boundary Propagation
```

---

## 附录 A：常量定义

```typescript
// 方向常量
const DIRECTIONS_4: Position[] = [
  { x: 0, y: -1 }, // Up
  { x: 1, y: 0 },  // Right
  { x: 0, y: 1 },  // Down
  { x: -1, y: 0 }, // Left
];

const DIRECTIONS_8: Position[] = [
  ...DIRECTIONS_4,
  { x: 1, y: -1 },  // Up-Right
  { x: 1, y: 1 },   // Down-Right
  { x: -1, y: 1 },  // Down-Left
  { x: -1, y: -1 }, // Up-Left
];

// 安全区半径
const SAFE_ZONE_RADIUS = 1; // 3x3 区域 (中心 ±1)

// 最大重试次数
const MAX_VERIFY_ATTEMPTS = 10;

// 陷阱密度降级因子
const TRAP_DENSITY_FALLBACK_FACTOR = 0.8;
```

## 附录 B：与已有文档的引用关系

| 引用文档 | 本文档依赖的章节 |
|----------|-----------------|
| `01_core_gameplay.md` | §1.3 瓦片状态定义、§3 扫雷规则（Flood Fill、Chording） |
| `03_interactive_elements.md` | §1.1 元素分类、§4 TileLayer 三层架构 |
| `04_tools_and_economy.md` | §2 工具对地图的影响（Pickaxe/Dynamite/Map） |
| `05_mummy_shop_and_amulet.md` | §1 关卡完成触发器（`onLevelComplete`） |
