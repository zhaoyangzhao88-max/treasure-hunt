# 第 1 课：核心玩法与胜败判定规范设计

> 本文档定义 Microsoft Treasure Hunt 复刻项目的核心游戏机制、数据结构规范以及胜负判定逻辑。所有后续课程应严格遵循本文档所定义的契约。

---

## 目录

1. [瓦片与网格系统 (Grid & Tile System)](#1-瓦片与网格系统-grid--tile-system)
2. [角色移动与交互机制 (Hero Movement & Interaction)](#2-角色移动与交互机制-hero-movement--interaction)
3. [冒险扫雷规则 (Minesweeper Mechanics in Adventure)](#3-冒险扫雷规则-minesweeper-mechanics-in-adventure)
4. [生命值与护盾判定 (Hearts & Shield)](#4-生命值与护盾判定-hearts--shield)
5. [胜负与关卡出口机制 (Win & Exit Conditions)](#5-胜负与关卡出口机制-win--exit-conditions)

---

## 1. 瓦片与网格系统 (Grid & Tile System)

### 1.1 基础网格

游戏世界采用二维矩形网格（Grid）作为基本空间单元。

| 属性 | 定义 | 说明 |
|------|------|------|
| `width` | `number` | 网格宽度（列数），取值范围 ≥ 5 |
| `height` | `number` | 网格高度（行数），取值范围 ≥ 5 |
| `tileSize` | `number` | 单个瓦片的像素尺寸（用于渲染） |

### 1.2 坐标系统

采用 2D 笛卡尔坐标系，原点 `(0, 0)` 位于网格左上角：

- **x 轴**：从左到右递增（列索引）
- **y 轴**：从上到下递增（行索引）
- 坐标表示：`TilePosition { x: number, y: number }`

### 1.3 瓦片状态定义

每个网格单元（瓦片）在任意时刻处于且仅处于以下状态之一：

| 状态标识 | 中文名 | 英文名 | 描述 |
|----------|--------|--------|------|
| `DIRT` | 泥土 | Dirt | 未揭露的泥土瓦片，玩家可挖掘 |
| `UNCOVERED` | 安全地带 | Uncovered | 已揭开的空白安全区域，显示数字或为空 |
| `TRAP` | 陷阱 | Trap | 隐藏的陷阱，挖掘后触发伤害 |
| `WALL` | 不可破坏墙 | Wall | 不可通过的实体边界或障碍物 |
| `DIRT_WALL` | 可破坏泥墙 | Dirt Wall | 可通过挖掘破坏的泥墙，破坏后变为 DIRT 或 UNCOVERED |

### 1.4 瓦片数据结构

```typescript
interface Tile {
  position: TilePosition;  // { x, y }
  state: TileState;        // DIRT | UNCOVERED | TRAP | WALL | DIRT_WALL
  adjacentTraps: number; // 周围 8 格中陷阱的数量 (0-8)
  isFlagged: boolean;      // 是否被玩家标记（插旗）
  hasKey: boolean;         // 是否包含钥匙
  hasExit: boolean;        // 是否为出口门位置
}
```

### 1.5 状态转换规则

```
挖掘(DIG)操作:
  DIRT → UNCOVERED (揭示后显示 adjacentTraps)
  DIRT → TRAP (该格实际为陷阱，触发伤害)
  DIRT_WALL → UNCOVERED (泥墙被破坏，揭示下方内容)

标记(FLAG)操作:
  DIRT ↔ DIRT+isFlagged (切换标记状态)

移动(MOVE)操作:
  UNCOVERED → UNCOVERED (允许移动)
  其他状态 → 拒绝移动
```

---

## 2. 角色移动与交互机制 (Hero Movement & Interaction)

### 2.1 角色位置

角色（Hero）始终占据一个网格单元，其位置由 `TilePosition` 表示。

### 2.2 移动约束

| 条件 | 是否允许移动 |
|------|-------------|
| 目标格为 `UNCOVERED`（数字格或空白格） | ✅ 允许 |
| 目标格为 `DIRT`（未挖掘的泥土） | ❌ 不允许 |
| 目标格为 `WALL`（不可破坏墙） | ❌ 不允许 |
| 目标格为 `DIRT_WALL`（可破坏泥墙） | ❌ 不允许（需先挖掘） |
| 目标格超出网格边界 | ❌ 不允许 |
| 目标格与当前位置不相邻（非 8 方向） | ❌ 不允许 |

### 2.3 移动方向

支持 8 方向移动（上、下、左、右 + 四个对角线）：

```
(-1,-1)  (0,-1)  (+1,-1)
(-1, 0)  [HERO]  (+1, 0)
(-1,+1)  (0,+1)  (+1,+1)
```

### 2.4 挖掘操作

玩家可通过点击/选择相邻的 `DIRT` 瓦片进行挖掘：

- **前提条件**：目标 DIRT 瓦片必须与角色当前位置相邻（8 方向）
- **操作流程**：
  1. 玩家选中相邻的 DIRT 瓦片
  2. 系统执行挖掘判定
  3. 若该格为安全泥土 → 状态变为 `UNCOVERED`，显示周围陷阱数
  4. 若该格为陷阱 → 状态变为 `TRAP`，对角色造成伤害

### 2.5 交互优先级

当玩家点击一个瓦片时，交互判定优先级：

1. 若瓦片为 `UNCOVERED` 且角色相邻 → 移动角色到该格
2. 若瓦片为 `DIRT` 且角色相邻 → 执行挖掘
3. 若瓦片为 `DIRT` 且已被标记 → 取消标记
4. 其他情况 → 无操作

---

## 3. 冒险扫雷规则 (Minesweeper Mechanics in Adventure)

### 3.1 数字逻辑

当一块泥土被成功挖掘（安全）后，该格变为 `UNCOVERED` 状态，并显示一个数字：

- **数字范围**：`0` 到 `8`
- **含义**：该格子周围 **8 个相邻格子** 中隐藏陷阱（`TRAP`）的数量
- **特殊规则**：
  - 数字 `0`：周围无陷阱，自动展开（flood fill）所有相邻的 `0` 格及其边界数字格
  - 数字 `1-8`：周围有对应数量的陷阱

### 3.2 标记逻辑（Flagging）

玩家可对可疑的 `DIRT` 瓦片放置/移除红旗标记：

| 操作 | 触发条件 | 效果 |
|------|----------|------|
| 放置标记 | 点击未标记的 `DIRT` 瓦片 | `isFlagged = true`，显示红旗图标 |
| 移除标记 | 点击已标记的 `DIRT` 瓦片 | `isFlagged = false`，恢复泥土图标 |

**标记约束**：
- 只能标记 `DIRT` 状态的瓦片
- 已揭开的 `UNCOVERED` 瓦片不可标记
- 标记数量无上限（但需符合逻辑判断）
- 标记不影响实际游戏逻辑，仅作为玩家辅助工具

### 3.3 连带清除 (Chording)

Chording 是一种高级操作，允许玩家一次性揭开数字格周围所有未标记的泥土：

**触发条件**：
1. 玩家点击或双击一个 `UNCOVERED` 瓦片
2. 该瓦片的 `adjacentTraps` 数字 ≥ 1
3. 该瓦片周围 8 格中，**已被标记（Flag）的格子数** 等于该瓦片的数字

**执行逻辑**：
```
IF flaggedCount == tile.adjacentTraps THEN
    FOR each adjacent tile:
        IF tile.state == DIRT AND NOT tile.isFlagged THEN
            REVEAL(tile)  // 揭开该格
            IF tile实际为陷阱 THEN
                触发陷阱伤害
            END IF
        END IF
    END FOR
END IF
```

**安全保证**：当且仅当标记数与数字完全相等时才执行，确保不会误开陷阱（前提是玩家标记正确）。

---

## 4. 生命值与护盾判定 (Hearts & Shield)

### 4.1 生命值系统

| 属性 | 默认值 | 说明 |
|------|--------|------|
| `maxHearts` | `3` | 最大生命值上限 |
| `currentHearts` | `3` | 当前剩余生命值 |
| `maxShield` | `1` | 最大护盾数量 |
| `currentShield` | `0` | 当前护盾数量 |

### 4.2 伤害判定流程

当角色触发陷阱（踩中未标记的 `TRAP`）时，伤害按以下优先级扣除：

```
FUNCTION onTrapTriggered():
    IF currentShield > 0 THEN
        currentShield -= 1        // 优先扣除护盾
        triggerShieldBreakEffect()
    ELSE
        currentHearts -= 1        // 护盾耗尽，扣除生命值
        triggerHeartLossEffect()
    END IF

    IF currentHearts <= 0 THEN
        triggerGameOver()
    END IF
END FUNCTION
```

### 4.3 死亡判定

- **触发条件**：`currentHearts <= 0`
- **结果**：游戏结束（Game Over）
- **处理方式**：
  - 显示 Game Over 画面
  - 提供"重新开始"和"返回主菜单"选项
  - 记录本次游戏数据（步数、用时等）

### 4.4 生命恢复

- 游戏中可通过特定道具（如 Heart Pickup）恢复生命值
- 恢复上限不超过 `maxHearts`
- 护盾可通过 Shield Pickup 获得

---

## 5. 胜负与关卡出口机制 (Win & Exit Conditions)

### 5.1 通关条件

玩家必须同时满足以下 **两个条件** 才能通关：

| 条件 | 描述 |
|------|------|
| ① 获得钥匙 (Key) | 关卡中存在一把隐藏的钥匙，玩家需挖掘特定泥土格子找到它 |
| ② 到达出口门 (Exit Gate) | 获得钥匙后，玩家需移动到出口门所在位置 |

### 5.2 钥匙机制 (Key)

- 每关有且仅有 **1 把钥匙**
- 钥匙隐藏在某个 `DIRT` 瓦片下方（非 `TRAP` 格）
- 挖掘到钥匙后：
  - 玩家状态 `hasKey = true`
  - 钥匙从地图中移除
  - UI 显示钥匙图标
  - 出口门激活（视觉变化）

### 5.3 出口门机制 (Exit Gate)

- 出口门位于地图的某个固定位置（由关卡设计指定）
- **初始状态**：出口门处于锁定状态（不激活）
- **激活条件**：玩家获得钥匙（`hasKey = true`）
- **通关触发**：
  ```
  IF hero.position == exitGate.position AND player.hasKey THEN
      triggerLevelComplete()
  END IF
  ```

### 5.4 关卡完成流程

```
1. 玩家获得钥匙 → 出口门激活
2. 玩家移动至出口门位置
3. 系统检测到通关条件满足
4. 播放通关动画/特效
5. 显示关卡完成画面
6. 解锁下一关 / 返回关卡选择
```

### 5.5 游戏状态机总览

```
[INIT] → [PLAYING] → [GAME_OVER]
           ↓
       [LEVEL_COMPLETE] → [INIT] (下一关)
```

---

## 附录：核心枚举定义

```typescript
enum TileState {
  DIRT = 'DIRT',
  UNCOVERED = 'UNCOVERED',
  TRAP = 'TRAP',
  WALL = 'WALL',
  DIRT_WALL = 'DIRT_WALL'
}

enum GameState {
  INIT = 'INIT',
  PLAYING = 'PLAYING',
  LEVEL_COMPLETE = 'LEVEL_COMPLETE',
  GAME_OVER = 'GAME_OVER'
}

interface TilePosition {
  x: number;
  y: number;
}

interface HeroState {
  position: TilePosition;
  currentHearts: number;
  maxHearts: number;
  currentShield: number;
  maxShield: number;
  hasKey: boolean;
}
```

---

*文档版本: v1.0 | 创建日期: 2026-06-25 | 作者: OWL Assistant*
