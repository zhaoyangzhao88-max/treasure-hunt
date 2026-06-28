# 第 4 课：工具道具使用逻辑与背包/经济系统规范设计

> 本文档定义 Microsoft Treasure Hunt 复刻项目中所有工具道具的主动使用逻辑、背包容量体系、经济系统（金币/宝石）以及全局数据流。本文档与 `03_interactive_elements.md`（元素分类）配合，将元素定义升级为完整的可交互系统。所有后续课程应严格遵循本文档所定义的契约。

---

## 目录

1. [背包系统与扩容规则 (Inventory & Capacity Progression)](#1-背包系统与扩容规则-inventory--capacity-progression)
2. [工具核心主动交互逻辑 (Active Tool Mechanics)](#2-工具核心主动交互逻辑-active-tool-mechanics)
3. [经济系统设计 (Economy & Gold Logic)](#3-经济系统设计-economy--gold-logic)
4. [系统代码接口与数据流伪代码 (API & Logic Pseudo-code)](#4-系统代码接口与数据流伪-code-api--logic-pseudo-code)

---

## 1. 背包系统与扩容规则 (Inventory & Capacity Progression)

### 1.1 共享容量阶梯

三种工具（铁锹 Pickaxe、炸药 Dynamite、地图 TreasureMap）共享同一套独立的容量升级阶梯。

```
容量阶梯: 2 → 4 → 6 → 8 → 10 → 15 → 20 → 25 → 30
```

| 等级 | 最大容量 | 说明 |
|------|----------|------|
| Lv 0 (初始) | 2 | 游戏初始容量 |
| Lv 1 | 4 | 商店升级 |
| Lv 2 | 6 | 商店升级 |
| Lv 3 | 8 | 商店升级 |
| Lv 4 | 10 | 商店升级 |
| Lv 5 | 15 | 商店升级 |
| Lv 6 | 20 | 商店升级 |
| Lv 7 | 25 | 商店升级 |
| Lv 8 (满级) | 30 | 绝对上限 |

### 1.2 容量规则

| 规则 | 定义 |
|------|------|
| 共享上限 | 三种工具共用同一个 `maxCapacity` 数值 |
| 独立计数 | 每种工具有独立的 `currentCount`，各自不超过 `maxCapacity` |
| 总量约束 | `pickaxeCount + dynamiteCount + mapCount ≤ maxCapacity` |
| 溢出拒绝 | 当总量已达上限时，拾取新工具被拒绝（不销毁实体，保留在地图上） |
| 升级即扩容 | 购买扩容升级时，`maxCapacity` 提升至下一阶梯；当前数量不变 |

### 1.3 扩容升级价格参考

| 升级 | 新容量 | 价格 (金币) |
|------|--------|-------------|
| Lv 0 → Lv 1 | 4 | 200 |
| Lv 1 → Lv 2 | 6 | 400 |
| Lv 2 → Lv 3 | 8 | 600 |
| Lv 3 → Lv 4 | 10 | 1000 |
| Lv 4 → Lv 5 | 15 | 1500 |
| Lv 5 → Lv 6 | 20 | 2500 |
| Lv 6 → Lv 7 | 25 | 4000 |
| Lv 7 → Lv 8 | 30 | 6000 |

> 具体数值由经济系统课程最终确定，此处仅为参考框架。

### 1.4 数据结构

```typescript
interface ToolInventory {
  pickaxeCount: number;   // 铁锹当前数量
  dynamiteCount: number;  // 炸药当前数量
  mapCount: number;       // 地图当前数量
  maxCapacity: number;    // 当前共享容量上限
  capacityLevel: number;  // 当前容量等级 (0-8)
}

const DEFAULT_TOOL_INVENTORY: ToolInventory = {
  pickaxeCount: 1,   // 初始赠送 1 把铁锹
  dynamiteCount: 0,
  mapCount: 0,
  maxCapacity: 2,
  capacityLevel: 0,
};

const CAPACITY_LADDER: number[] = [2, 4, 6, 8, 10, 15, 20, 25, 30];
```

---

## 2. 工具核心主动交互逻辑 (Active Tool Mechanics)

### 2.1 工具选择与使用流程

```
玩家操作流程:
  1. 在 UI 工具栏中选择要使用的工具 (Pickaxe / Dynamite / Map)
  2. 高亮显示可交互的目标格子
  3. 点击目标格子 → 调用 useTool(toolType, targetPos)
  4. 系统判定合法性 → 执行效果 → 更新状态
```

### 2.2 铁锹 (Pickaxe)

#### 使用条件

| 条件 | 要求 |
|------|------|
| 背包中有铁锹 | `pickaxeCount > 0` |
| 目标格为泥墙 | `targetTile.obstacle.type === ENTITY_WALL_DIRT` |
| 目标格与角色相邻 | `isAdjacent(hero.position, targetPos)` |

#### 使用效果

```
FUNCTION usePickaxe(targetPos: TilePosition, hero: Hero):
    IF hero.toolInventory.pickaxeCount <= 0 THEN
        RETURN { success: false, reason: "NO_PICKAXE" }
    END IF
    
    targetTile = grid.getTile(targetPos)
    IF targetTile.obstacle?.type !== ENTITY_WALL_DIRT THEN
        RETURN { success: false, reason: "TARGET_NOT_DIRT_WALL" }
    END IF
    
    IF NOT isAdjacent(hero.position, targetPos) THEN
        RETURN { success: false, reason: "TARGET_NOT_ADJACENT" }
    END IF
    
    // 消耗铁锹
    hero.toolInventory.pickaxeCount -= 1
    
    // 泥墙转为已揭开
    targetTile.obstacle = null
    targetTile.background = TileState.UNCOVERED
    
    // 检查下方是否有隐藏实体
    hiddenEntity = targetTile.hiddenEntity
    IF hiddenEntity !== null THEN
        resolveHiddenEntity(hiddenEntity, hero)
    END IF
    
    triggerDirtWallBreakFX(targetPos)
    RETURN { success: true, consumed: 1, remaining: hero.toolInventory.pickaxeCount }
END FUNCTION
```

#### 下方实体显露规则

| 下方实体类型 | 效果 |
|-------------|------|
| 无实体 | 仅变为空地 |
| 金币 (Coin) | 自动收集 |
| 钥匙 (Key) | 自动收集 |
| 红心/护盾 (Heart/Shield) | 自动收集 |
| 工具 (Tool) | 自动收集 |
| 陷阱 (Trap) | **触发陷阱伤害**（按 `02_hearts_and_shields.md` 流程执行） |

### 2.3 炸药 (Dynamite)

#### 使用条件

| 条件 | 要求 |
|------|------|
| 背包中有炸药 | `dynamiteCount > 0` |
| 目标格在范围内 | 相邻 1 格 或 角色视界内可达 |
| 目标格非不可破坏墙 | `targetTile.obstacle.type !== ENTITY_WALL_INDESTRUCTIBLE` |

#### 使用效果

```
FUNCTION useDynamite(targetPos: TilePosition, hero: Hero):
    IF hero.toolInventory.dynamiteCount <= 0 THEN
        RETURN { success: false, reason: "NO_DYNAMITE" }
    END IF
    
    IF NOT isWithinBlastRange(hero.position, targetPos) THEN
        RETURN { success: false, reason: "TARGET_OUT_OF_RANGE" }
    END IF
    
    // 消耗炸药
    hero.toolInventory.dynamiteCount -= 1
    
    // 计算 3x3 爆破区域
    blastZone = getBlastZone(targetPos, radius=1)  // 3x3
    
    FOR EACH tile IN blastZone:
        // 不可破坏墙阻挡爆破
        IF tile.obstacle?.type === ENTITY_WALL_INDESTRUCTIBLE THEN
            CONTINUE  // 跳过，不被破坏
        END IF
        
        // 安全销毁陷阱（玩家不受伤）
        IF tile.background === TileState.TRAP THEN
            tile.background = TileState.UNCOVERED
            tile.hasTrap = false
            triggerSafeTrapDestroyFX(tile.position)
            CONTINUE
        END IF
        
        // 移除泥墙
        IF tile.obstacle?.type === ENTITY_WALL_DIRT THEN
            tile.obstacle = null
            tile.background = TileState.UNCOVERED
            CONTINUE
        END IF
        
        // 强制揭开泥土
        IF tile.background === TileState.DIRT THEN
            tile.background = TileState.UNCOVERED
            // 检查并显露下方实体
            IF tile.hiddenEntity !== null THEN
                resolveHiddenEntity(tile.hiddenEntity, hero)
            END IF
            CONTINUE
        END IF
        
        // 移除锁门（如果存在对应钥匙逻辑则另议，炸药可强行破开）
        IF tile.obstacle?.type === ENTITY_GATE_RED OR
           tile.obstacle?.type === ENTITY_GATE_GREEN OR
           tile.obstacle?.type === ENTITY_GATE_BLUE THEN
            tile.obstacle = null
            tile.background = TileState.UNCOVERED
            triggerGateDestroyFX(tile.position)
            CONTINUE
        END IF
    END FOR
    
    triggerExplosionFX(targetPos)
    RETURN { success: true, consumed: 1, remaining: hero.toolInventory.dynamiteCount }
END FUNCTION
```

#### 爆破安全规则

| 规则 | 说明 |
|------|------|
| 陷阱安全销毁 | 3×3 区域内的隐藏陷阱被直接销毁，**不触发任何伤害判定** |
| 不可破坏墙阻挡 | 不可破坏墙本身不被破坏，且阻挡爆破传播（该格保持原状） |
| 锁门可被炸开 | 锁门被炸药强行破坏，不消耗钥匙 |
| 出口门不可炸 | 出口门 (ExitGate) 免疫炸药，必须使用钥匙开启 |
| 友方伤害无 | 爆破不会对角色自身造成伤害 |

### 2.4 地图 (Treasure Map)

#### 使用条件

| 条件 | 要求 |
|------|------|
 背包中有地图 | `mapCount > 0` |
| 无需指定目标 | 以角色当前位置为中心 |

#### 使用效果

```
FUNCTION useTreasureMap(hero: Hero):
    IF hero.toolInventory.mapCount <= 0 THEN
        RETURN { success: false, reason: "NO_MAP" }
    END IF
    
    // 消耗地图
    hero.toolInventory.mapCount -= 1
    
    // 计算 5x5 扫描区域
    scanZone = getScanZone(hero.position, radius=2)  // 5x5
    
    flaggedCount = 0
    FOR EACH tile IN scanZone:
        // 仅扫描未揭开的泥土/陷阱
        IF tile.background === TileState.DIRT OR tile.background === TileState.TRAP THEN
            IF tile.hasTrap AND NOT tile.isFlagged THEN
                tile.isFlagged = true  // 自动标记
                flaggedCount += 1
                triggerAutoFlagFX(tile.position)
            END IF
        END IF
    END FOR
    
    triggerMapScanFX(hero.position)
    RETURN { success: true, consumed: 1, flaggedCount: flaggedCount, remaining: hero.toolInventory.mapCount }
END FUNCTION
```

#### 地图扫描规则

| 规则 | 说明 |
|------|------|
| 扫描范围 | 以角色为中心的 5×5 区域（radius=2） |
| 仅标记陷阱 | 只对含有隐藏陷阱的未揭开格子自动打旗 |
| 不揭开泥土 | 地图仅提供信息，不执行任何挖掘/揭开操作 |
| 已标记不重复 | 已标记的格子不会被重复标记 |
| 安全保证 | 玩家通过地图标记的陷阱位置100%准确 |

---

## 3. 经济系统设计 (Economy & Gold Logic)

### 3.1 货币类型

| 货币类型 | 标识 | 价值 | 视觉标识 |
|----------|------|------|----------|
| 金币-小 | `COIN_SMALL` | 10 | 金色小圆片 |
| 金币-大 | `COIN_LARGE` | 50 | 金色大圆片 |
| 宝石-小 | `GEM_SMALL` | 100 | 蓝色小菱形 |
| 宝石-大 | `GEM_LARGE` | 500 | 蓝色大菱形 |

### 3.2 全局经济数据

```typescript
interface EconomyData {
  gold: number;           // 全局金币总量（跨关卡继承）
  totalGoldEarned: number; // 历史总获得金币（成就/统计用）
  totalGoldSpent: number;  // 历史总花费金币
}

const DEFAULT_ECONOMY: EconomyData = {
  gold: 0,
  totalGoldEarned: 0,
  totalGoldSpent: 0,
};
```

### 3.3 金币获取途径

| 来源 | 价值 | 触发条件 |
|------|------|----------|
| 拾取金币-小 | +10 | 角色坐标与金币实体重合 |
| 拾取金币-大 | +50 | 角色坐标与金币实体重合 |
| 拾取宝石-小 | +100 | 角色坐标与宝石实体重合 |
| 拾取宝石-大 | +500 | 角色坐标与宝石实体重合 |
| 关卡完成奖励 | 设计待定 | 通关时根据表现发放 |
| 怪物掉落 | 设计待定 | 击败怪物后掉落（后续课程） |

### 3.4 金币消费途径

| 消费项 | 价格 | 效果 |
|--------|------|------|
| 铁锹 (Pickaxe) | 50 | pickaxeCount += 1（受容量上限约束） |
| 炸药 (Dynamite) | 100 | dynamiteCount += 1（受容量上限约束） |
| 地图 (TreasureMap) | 75 | mapCount += 1（受容量上限约束） |
| 红心回复 | 150 | currentHearts += 1 |
| 护盾回复 | 200 | currentShield += 1 |
| 容量升级 | 见 §1.3 | maxCapacity 提升至下一阶梯 |
| 红心上限+1 | 见 `02_hearts_and_shields.md` | maxHearts += 1 |
| 护盾上限+1 | 见 `02_hearts_and_shields.md` | maxShield += 1 |

### 3.5 跨关卡继承规则

| 数据 | 是否继承 | 说明 |
|------|----------|------|
| 金币 (gold) | ✅ 完全继承 | 全局经济，关卡间不重置 |
| 工具数量 | ❌ 重置 | 每关初始工具按关卡配置重置 |
| 红心/护盾 | ❌ 重置 | 每关按初始值重置 |
| 钥匙 | ❌ 重置 | 每关独立 |
| 容量等级 | ✅ 永久保留 | 永久升级，跨关卡有效 |
| 红心/护盾上限 | ✅ 永久保留 | 永久升级，跨关卡有效 |

---

## 4. 系统代码接口与数据流伪代码 (API & Logic Pseudo-code)

### 4.1 核心方法：useTool

```
FUNCTION useTool(toolType: ToolType, targetPos: TilePosition, hero: Hero):
    // 前置检查
    IF NOT canUseTool(toolType, hero) THEN
        RETURN { success: false, reason: getToolError(toolType, hero) }
    END IF
    
    // 根据工具类型分发
    SWITCH toolType:
        CASE TOOL_PICKAXE:
            result = usePickaxe(targetPos, hero)
            BREAK
            
        CASE TOOL_DYNAMITE:
            result = useDynamite(targetPos, hero)
            BREAK
            
        CASE TOOL_MAP:
            result = useTreasureMap(hero)
            BREAK
            
        DEFAULT:
            RETURN { success: false, reason: "UNKNOWN_TOOL" }
    END SWITCH
    
    // 统一后处理
    IF result.success THEN
        updateUI()
        checkCapacityOverflow(hero.toolInventory)
    END IF
    
    RETURN result
END FUNCTION
```

### 4.2 容量溢出检测

```
FUNCTION checkCapacityOverflow(inventory: ToolInventory):
    total = inventory.pickaxeCount + inventory.dynamiteCount + inventory.mapCount
    
    IF total > inventory.maxCapacity THEN
        // 理论上不应发生，但作为安全保护
        excess = total - inventory.maxCapacity
        // 按比例从数量最多的工具中扣除
        WHILE excess > 0:
            maxTool = getMaxCountTool(inventory)
            inventory[maxTool] -= 1
            excess -= 1
        END WHILE
    END IF
END FUNCTION
```

### 4.3 完整数据载荷定义

```typescript
// ===== 工具类型枚举 =====
enum ToolType {
  PICKAXE = 'PICKAXE',
  DYNAMITE = 'DYNAMITE',
  TREASURE_MAP = 'TREASURE_MAP',
}

// ===== 货币类型枚举 =====
enum CurrencyType {
  COIN_SMALL = 'COIN_SMALL',   // 10
  COIN_LARGE = 'COIN_LARGE',   // 50
  GEM_SMALL = 'GEM_SMALL',     // 100
  GEM_LARGE = 'GEM_LARGE',     // 500
}

const CURRENCY_VALUES: Record<CurrencyType, number> = {
  COIN_SMALL: 10,
  COIN_LARGE: 50,
  GEM_SMALL: 100,
  GEM_LARGE: 500,
};

// ===== 背包数据 =====
interface ToolInventory {
  pickaxeCount: number;
  dynamiteCount: number;
  mapCount: number;
  maxCapacity: number;
  capacityLevel: number;
}

// ===== 经济数据 =====
interface EconomyData {
  gold: number;
  totalGoldEarned: number;
  totalGoldSpent: number;
}

// ===== 完整玩家数据载荷 =====
interface PlayerPayload {
  economy: EconomyData;
  tools: ToolInventory;
  vitalStats: VitalStats;       // 引用 02_hearts_and_shields.md
  inventory: Inventory;         // 引用 03_interactive_elements.md
  // ... 其他系统数据
}

// ===== 容量阶梯常量 =====
const CAPACITY_LADDER: readonly number[] = [2, 4, 6, 8, 10, 15, 20, 25, 30];
const MAX_CAPACITY_LEVEL = CAPACITY_LADDER.length - 1;  // 8

// ===== 商店价格常量 =====
const SHOP_PRICES = {
  pickaxe: 50,
  dynamite: 100,
  treasureMap: 75,
  heartHeal: 150,
  shieldHeal: 200,
  capacityUpgrade: [200, 400, 600, 1000, 1500, 2500, 4000, 6000],
};
```

### 4.4 数据流全景

```
[地图实体] --(角色踩踏)--> [收集判定] --(金币)--> [EconomyData.gold += value]
                                                    |
[商店界面] --(购买请求)--> [金币扣除] --(道具)--> [ToolInventory.count += 1]
                                                    |
[工具栏选择] --(使用工具)--> [useTool()] --(消耗)--> [ToolInventory.count -= 1]
                    |                            |
                    └──(效果)──> [地图更新] <──────┘
                                        |
                                        └──> [陷阱/实体显露] ──> [伤害判定/收集]
```

---

## 附录：工具效果速查表

| 工具 | 消耗 | 范围 | 效果 | 陷阱处理 |
|------|------|------|------|----------|
| 铁锹 | 1 Pickaxe | 相邻 1 格 | 破坏泥墙 → 揭开 | 触发伤害 |
| 炸药 | 1 Dynamite | 相邻/视界内 → 3×3 | 强制揭开所有可破坏物 | 安全销毁（无伤害） |
| 地图 | 1 Map | 角色中心 5×5 | 自动标记隐藏陷阱 | 仅标记，不揭开 |

---

*文档版本: v1.0 | 创建日期: 2026-06-25 | 依赖: docs/02_hearts_and_shields.md, docs/03_interactive_elements.md*
