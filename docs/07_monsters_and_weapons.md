# 第 7 课：怪物与武器系统规范设计

> 本文档定义 Microsoft Treasure Hunt 复刻项目中的**怪物实体 (Monster Entities)**、**武器系统 (Weapon System)**、**战斗交互优先级 (Combat Interaction Priority)** 以及**跨关卡背包重置法则 (Cross-Level Inventory Purge)**。本文档与 `01_core_gameplay.md`（核心玩法）、`03_interactive_elements.md`（实体分类）、`04_tools_and_economy.md`（道具系统）、`06_map_generation.md`（地图生成）配合使用，构成完整的关卡实体交互契约。所有后续课程应严格遵循本文档所定义的契约。

---

## 目录

1. [怪物实体与行为定义 (Monster Entities & Static Behavior)](#1-怪物实体与行为定义-monster-entities--static-behavior)
2. [武器实体与获取规则 (Weapons & Pickups)](#2-武器实体与获取规则-weapons--pickups)
3. [核心战斗交互与伤害判定逻辑 (Combat & Interaction Priority)](#3-核心战斗交互与伤害判定逻辑-combat--interaction-priority)
4. [跨关卡背包重置法则 (Cross-Level Inventory Purge)](#4-跨关卡背包重置法则-cross-level-inventory-purge)
5. [逻辑伪代码与底层接口设计 (Logic & Interface)](#5-逻辑伪代码与底层接口设计-logic--interface)

---

## 1. 怪物实体与行为定义 (Monster Entities & Static Behavior)

### 1.1 怪物种类 (Monster Types)

游戏中共有三种怪物，**核心机制完全相同**（静态卡点、阻挡通行、可被武器击杀），仅在**视觉外观**上存在差异：

| 怪物 ID | 名称 | 外观描述 | 生成关卡范围 |
|---------|------|----------|-------------|
| `bat` | 蝙蝠 (Bat) | 紫色/黑色蝙蝠形态，配翅膀动画 | Level 1+ |
| `snake` | 蛇 (Snake) | 绿色蛇形，蜷曲姿态 | Level 3+ |
| `mummy` | 地下木乃伊 (Underground Mummy) | 裹布木乃伊，棕色/米色 | Level 5+ |

**设计原则**：三种怪物共享同一套 AI 逻辑与碰撞判定，外观差异仅影响美术资源，不影响数值与机制。

### 1.2 静态卡点机制 (Static Blockage)

#### 1.2.1 生成规则

- 怪物**生成于已揭开的空地 (revealed empty tile)** 上。
- 怪物**无法主动移动**，始终停留在生成格。
- 怪物生成后，该格子**立即进入阻塞状态 (blocked)**。

#### 1.2.2 阻挡行为

- 当玩家尝试走向怪物所在格子时，**移动被阻止**（玩家停留在原格）。
- 系统触发**战斗判定流程**（详见 §3）。
- 怪物**不会追逐、移动或改变位置**，直到被击杀或关卡重置。

#### 1.2.3 视觉指示

- 怪物格始终显示怪物精灵（不透明）。
- 当玩家与怪物相邻时，怪物应播放**威胁动画**（如闪烁、抖动），提示玩家即将触发战斗。

#### 1.2.4 静态卡点判定伪代码

```typescript
function isTileBlocked(tile: Tile): boolean {
  return tile.entity !== null && tile.entity.type === 'monster' && !tile.entity.isDead;
}
```

---

## 2. 武器实体与获取规则 (Weapons & Pickups)

### 2.1 弓箭 (Arrow)

#### 2.1.1 获取方式

- 当玩家使用铁锹挖掘 **泥土 (Dirt) 瓦片** 时，系统根据概率表判定是否掘出弓箭。
- 掘出概率由关卡参数控制（默认约 5%–10%，随关卡递增）。
- 每次掘出固定获得 **1 支弓箭**。

#### 2.1.2 使用限制

| 属性 | 值 | 说明 |
|------|-----|------|
| 类型 | 消耗性 (Consumable) | 单次击杀消耗 1 支 |
| 携带上限 | 9 | 达到上限后无法再获取 |
| 获取条件 | 挖掘 Dirt 瓦片 | 非商店购买 |
| 跨关保留 | ❌ 不保留 | 进入下一关时清空为 0 |

#### 2.1.3 使用场景

- 玩家点击**相邻或可见**的怪物格子时，自动消耗 1 支弓箭击杀怪物。
- 玩家**无需走上怪物格**，保持安全距离。

### 2.2 柴刀 (Machete)

#### 2.2.1 获取方式

- 当玩家挖掘 **泥土 (Dirt) 瓦片** 时，**稀有概率**掘出柴刀（默认约 1%–2%）。
- 每个关卡**至多生成 1 把柴刀**（地图生成阶段决定）。

#### 2.2.2 使用限制

| 属性 | 值 | 说明 |
|------|-----|------|
| 类型 | 非消耗性 (Reusable) | 关卡内无限次使用 |
| 携带上限 | 1 | 布尔值 `HasMachete` |
| 获取条件 | 挖掘 Dirt 瓦片（稀有） | 非商店购买 |
| 跨关保留 | ❌ 不保留 | 进入下一关时 `HasMachete = false` |
| 击杀消耗 | 0 | 不消耗柴刀本身 |

#### 2.2.3 使用场景

- 玩家**持有柴刀**时，点击**相邻**怪物格子，无伤击杀。
- 柴刀仅在**当前关卡有效**，通关后自动移除。

---

## 3. 核心战斗交互与伤害判定逻辑 (Combat & Interaction Priority)

### 3.1 交互优先级总览

当玩家点击或尝试走向怪物所在格子时，系统按以下**优先级顺序**判定战斗结果：

```
炸药 (Dynamite) > 柴刀 (Machete) > 弓箭 (Arrow) > 肉身强推 (Unarmed)
```

**说明**：
- 炸药判定优先于一切其他武器（因为炸药影响 3×3 范围，包含怪物格）。
- 柴刀优先于弓箭（因为柴刀不消耗，鼓励玩家使用）。
- 弓箭优先于肉身（因为弓箭无伤，肉身会扣血）。
- 肉身强推是最后兜底，当玩家**没有任何武器**时触发。

### 3.2 无武器强推（肉身承受）

#### 3.2.1 触发条件

- 玩家**没有弓箭**（`Arrows === 0`）**且没有柴刀**（`HasMachete === false`）。
- 玩家点击或尝试走向怪物所在格子。

#### 3.2.2 判定结果

1. **移动被阻止**：玩家停留在原格，不移动到怪物格。
2. **伤害判定**（按顺序）：
   - 若 `CurrentShields > 0`：扣除 1 个护盾（`CurrentShields -= 1`）。
   - 否则若 `CurrentHP > 0`：扣除 1 颗红心（`CurrentHP -= 1`）。
   - 否则：触发死亡判定（参见 `01_core_gameplay.md`）。
3. **怪物不消失**：怪物仍然停留在原格，继续阻塞通行。
4. **视觉反馈**：播放受击动画与扣血特效。

#### 3.2.3 伪代码

```typescript
function handleUnarmedCollision(player: Player, monster: MonsterEntity): void {
  // 阻止移动
  player.cancelMove();

  // 优先扣护盾
  if (player.currentShields > 0) {
    player.currentShields -= 1;
  } else if (player.currentHP > 0) {
    player.currentHP -= 1;
  } else {
    triggerGameOver(player);
    return;
  }

  // 怪物存活
  monster.isDead = false;
  playDamageAnimation(player);
}
```

### 3.3 使用柴刀击杀

#### 3.3.1 触发条件

- 玩家**持有柴刀**（`HasMachete === true`）。
- 玩家点击**相邻**怪物格子。

#### 3.3.2 判定结果

1. **无伤击杀**：玩家不扣血、不扣护盾。
2. **怪物销毁**：从地图实体列表中移除，格子变为空地。
3. **柴刀不消耗**：`HasMachete` 保持 `true`。
4. **玩家不移动**：停留在原格（击杀后该格变为空地，玩家可后续走入）。

#### 3.3.3 伪代码

```typescript
function handleMacheteKill(player: Player, monster: MonsterEntity): void {
  if (!player.hasMachete) return;

  // 无伤击杀
  monster.isDead = true;
  removeMonsterFromMap(monster);
  playKillAnimation(monster);

  // 玩家不移动，但目标格已解锁
  unlockTile(monster.tile);
}
```

### 3.4 使用弓箭击杀

#### 3.4.1 触发条件

- 玩家**无柴刀**（`HasMachete === false`）**但持有至少 1 支弓箭**（`Arrows >= 1`）。
- 玩家点击**相邻或可见**的怪物格子。

#### 3.4.2 判定结果

1. **消耗 1 支弓箭**：`Arrows -= 1`。
2. **无伤击杀**：玩家不扣血、不扣护盾。
3. **怪物销毁**：从地图实体列表中移除，格子变为空地。
4. **玩家不移动**：停留在原格。

#### 3.4.3 伪代码

```typescript
function handleArrowKill(player: Player, monster: MonsterEntity): void {
  if (player.arrows < 1) return;

  // 消耗弓箭
  player.arrows -= 1;

  // 无伤击杀
  monster.isDead = true;
  removeMonsterFromMap(monster);
  playKillAnimation(monster);

  unlockTile(monster.tile);
}
```

### 3.5 使用炸药强轰

#### 3.5.1 触发条件

- 玩家**引爆炸药**（在任意格释放）。
- 爆炸影响的 **3×3 范围**内包含怪物格。

#### 3.5.2 判定结果

1. **安全气化销毁**：怪物立即被移除，**不触发任何伤害判定**。
2. **不消耗弓箭 / 柴刀**：武器数量不变。
3. **不扣除角色血量**：玩家完全无伤。
4. **视觉反馈**：播放爆炸特效 + 怪物消散动画。

#### 3.5.3 设计意图

- 炸药是**最安全的怪物清除手段**，但炸药本身数量有限（参见 `04_tools_and_economy.md`）。
- 鼓励玩家合理使用炸药处理**密集怪物群**或**危险位置怪物**。

#### 3.5.4 伪代码

```typescript
function handleDynamiteExplosion(centerTile: Tile, map: Tile[][]): void {
  const affectedTiles = get3x3Tiles(centerTile, map);

  for (const tile of affectedTiles) {
    if (tile.entity?.type === 'monster') {
      const monster = tile.entity as MonsterEntity;
      monster.isDead = true;
      removeMonsterFromMap(monster);
      unlockTile(tile);
    }
  }

  playExplosionAnimation(affectedTiles);
}
```

---

## 4. 跨关卡背包重置法则 (Cross-Level Inventory Purge)

### 4.1 触发时机

当以下事件发生时，系统**必须**执行 `purgeTemporaryInventory()`：

- 玩家**进入下一关**（关卡过渡动画开始时）。
- 玩家**进入商店界面**（商店打开前）。
- 玩家**重新开始游戏**（新游戏初始化时）。

### 4.2 清空列表 (Purged Items)

以下道具在跨关时**强制归零**：

| 道具 | 重置后值 | 说明 |
|------|---------|------|
| `Arrows` | `0` | 弓箭全部清空 |
| `HasMachete` | `false` | 柴刀移除 |
| `Keys` | `0` | 所有钥匙清空（蓝/绿/红） |

### 4.3 保留列表 (Persisted Items)

以下道具在跨关时**保持不变**：

| 道具 | 说明 |
|------|------|
| `Gold` | 金币累计值 |
| `Shovels` | 铁锹数量 |
| `Dynamite` | 炸药数量 |
| `Maps` | 地图数量 |
| `CurrentHP` | 当前生命值 |
| `MaxHP` | 最大生命值上限 |
| `CurrentShields` | 当前护盾数 |
| `MaxShields` | 最大护盾上限 |
| `HasAmulet` | 复活护身符持有状态 |

### 4.4 重置函数伪代码

```typescript
function purgeTemporaryInventory(player: Player): void {
  // 清空列表
  player.arrows = 0;
  player.hasMachete = false;
  player.keys = 0;

  // 保留列表（不做任何操作）
  // gold, shovels, dynamite, maps, currentHP, maxHP, currentShields, maxShields, hasAmulet
}
```

---

## 5. 逻辑伪代码与底层接口设计 (Logic & Interface)

### 5.1 怪物交互主入口函数

```typescript
function interactWithMonster(player: Player, monster: MonsterEntity): CombatResult {
  // 优先级 1：检查 3×3 范围内是否有炸药爆炸（由炸药系统提前处理）
  if (isMonsterInExplosionRange(monster)) {
    return { outcome: 'SAFE_KILL', damageDealt: 0, weaponUsed: 'dynamite' };
  }

  // 优先级 2：柴刀
  if (player.hasMachete && isAdjacent(player.tile, monster.tile)) {
    handleMacheteKill(player, monster);
    return { outcome: 'SAFE_KILL', damageDealt: 0, weaponUsed: 'machete' };
  }

  // 优先级 3：弓箭
  if (player.arrows >= 1 && isVisible(player.tile, monster.tile)) {
    handleArrowKill(player, monster);
    return { outcome: 'SAFE_KILL', damageDealt: 0, weaponUsed: 'arrow', arrowsConsumed: 1 };
  }

  // 优先级 4：肉身强推（兜底）
  handleUnarmedCollision(player, monster);
  return {
    outcome: 'TAKE_DAMAGE',
    damageDealt: 1,
    weaponUsed: 'unarmed',
    shieldLost: player.currentShields > 0 ? 1 : 0,
    hpLost: player.currentShields === 0 ? 1 : 0,
  };
}
```

### 5.2 TypeScript 接口定义

```typescript
// 怪物实体接口
interface MonsterEntity {
  id: string;
  type: 'bat' | 'snake' | 'mummy';
  tile: Tile;
  isDead: boolean;
  spawnLevel: number;
}

// 武器库存接口
interface WeaponInventory {
  arrows: number;       // 当前弓箭数量 [0, 9]
  hasMachete: boolean;  // 是否持有柴刀
  maxArrows: number;    // 携带上限（固定 9）
}

// 战斗载荷接口（用于前端展示 / 日志记录）
interface CombatResult {
  outcome: 'SAFE_KILL' | 'TAKE_DAMAGE';
  damageDealt: number;
  weaponUsed: 'dynamite' | 'machete' | 'arrow' | 'unarmed';
  arrowsConsumed?: number;
  shieldLost?: number;
  hpLost?: number;
  monsterType?: MonsterEntity['type'];
  monsterId?: string;
}

// 玩家完整状态接口（与武器库存配合）
interface PlayerState {
  // 武器系统
  weaponInventory: WeaponInventory;

  // 生命系统（参见 02_hearts_and_shields.md）
  currentHP: number;
  maxHP: number;
  currentShields: number;
  maxShields: number;

  // 经济系统（参见 04_tools_and_economy.md）
  gold: number;
  shovels: number;
  dynamite: number;
  maps: number;
  keys: number;

  // 特殊道具（参见 05_mummy_shop_and_amulet.md）
  hasAmulet: boolean;

  // 位置
  tile: Tile;
}
```

### 5.3 战斗判定流程图

```
玩家点击怪物格 / 尝试走向怪物格
              │
              ▼
    ┌─────────────────────┐
    │ 怪物是否在炸药 3×3  │
    │ 爆炸范围内？         │
    └─────────┬───────────┘
         是   │   否
    ┌─────────┘   │
    ▼             │
  安全气化销毁     │
  (无伤/不耗武器)  │
                  ▼
    ┌─────────────────────┐
    │ 玩家是否持有柴刀？   │
    │ 且怪物相邻？         │
    └─────────┬───────────┘
         是   │   否
    ┌─────────┘   │
    ▼             │
  柴刀无伤击杀     │
  (不消耗柴刀)     │
                  ▼
    ┌─────────────────────┐
    │ 玩家是否持有 ≥1 弓箭？│
    │ 且怪物可见？         │
    └─────────┬───────────┘
         是   │   否
    ┌─────────┘   │
    ▼             │
  弓箭无伤击杀     │
  (消耗 1 支)      │
                  ▼
    ┌─────────────────────┐
    │ 肉身强推（兜底）     │
    │ 扣 1 护盾 或 1 红心  │
    │ 怪物不消失           │
    └─────────────────────┘
```

---

## 附录 A：与其他文档的契约关系

| 关联文档 | 关联点 |
|---------|--------|
| `01_core_gameplay.md` | 死亡判定、移动系统、瓦片状态 |
| `02_hearts_and_shields.md` | 红心与护盾扣除规则 |
| `03_interactive_elements.md` | 实体分类、瓦片交互优先级 |
| `04_tools_and_economy.md` | 铁锹挖掘概率、炸药使用规则 |
| `05_mummy_shop_and_amulet.md` | 复活护身符跨关保留 |
| `06_map_generation.md` | 怪物生成位置、泥土瓦片分布 |

## 附录 B：关键常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `MAX_ARROWS` | 9 | 弓箭携带上限 |
| `ARROW_DROP_RATE` | 0.05–0.10 | 掘出弓箭概率（随关卡递增） |
| `MACHETE_DROP_RATE` | 0.01–0.02 | 掘出柴刀概率（稀有） |
| `MACHETE_MAX_PER_LEVEL` | 1 | 每关最多 1 把柴刀 |
| `MONSTER_DAMAGE` | 1 | 肉身强推时扣除的伤害值 |
