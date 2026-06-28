# 第 5 课：贪婪木乃伊商店与复活护身符机制规范设计

> 本文档定义 Microsoft Treasure Hunt 复刻项目中的元进度系统：贪婪木乃伊商店（Greedy Mummy Shop）的触发条件、商品体系、定价模型，以及复活护身符（Amulet of Rebirth）的 Roguelite 死亡数据流。本文档与 `04_tools_and_economy.md`（经济系统）配合，构成完整的跨关卡持久化框架。所有后续课程应严格遵循本文档所定义的契约。

---

## 目录

1. [商店关卡触发与环境规范 (Shop Stage Trigger & Map Environment)](#1-商店关卡触发与环境规范-shop-stage-trigger--map-environment)
2. [商品目录与定价模型 (Shop Inventory & Price Scaling)](#2-商品目录与定价模型-shop-inventory--price-scaling)
3. [复活与 Roguelite 死亡数据流 (Resurrection & Death Progression Flow)](#3-复活与-roguelite-死亡数据流-resurrection--death-progression-flow)
4. [核心逻辑伪代码与系统接口 (Logic & Interface Definition)](#4-核心逻辑伪代码与系统接口-logic--interface-definition)

---

## 1. 商店关卡触发与环境规范 (Shop Stage Trigger & Map Environment)

### 1.1 触发时机

贪婪木乃伊商店是一个**关卡间枢纽（Hub Stage）**，在玩家通过特定关卡后自动进入。

**触发规则**：

| 触发事件 | 进入商店 | 说明 |
|----------|----------|------|
| 完成第 1 关 | ✅ 进入商店（第 1 关后） | 首次进入 |
| 完成第 5 关 | ✅ 进入商店（第 5 关后） | 5 关周期 |
| 完成第 10 关 | ✅ 进入商店（第 10 关后） | 5 关周期 |
| 完成第 15 关 | ✅ 进入商店（第 15 关后） | 5 关周期 |
| 完成第 20 关 | ✅ 进入商店（第 20 关后） | 5 关周期 |
| ... | ... | 依此类推 |

**通用公式**：

```
触发商店的关卡 = {1} ∪ {n | n > 1 且 n mod 5 == 0}
```

即：第 1 关后必触发，此后每通过 5 个关卡触发一次。

### 1.2 地图特性

商店关卡是一个**绝对安全的微型专属地图**，具有以下特性：

| 属性 | 值 | 说明 |
|------|-----|------|
| 尺寸 | 7×7（可配置） | 微型地图 |
| 陷阱 | 无 | 绝对安全 |
| 怪物 | 无 | 绝对安全 |
| 泥土/泥墙 | 无 | 全部为已揭开平地 |
| 不可破坏墙 | 外围边界 | 仅用于地图边界 |

### 1.3 地图元素

```
┌─────────────────────────┐
│  ░░░░░░░░░░░░░░░░░░░░  │  ░ = 不可破坏墙（边界）
│  ░                   ░  │
│  ░   ┌───────────┐   ░  │  P = 传送门（通往下一关）
│  ░   │           │   ░  │  M = 贪婪木乃伊 NPC
│  ░   │     M     │   ░  │  . = 已揭开平地
│  ░   │           │   ░  │
│  ░   └───────────┘   ░  │
│  ░         P         ░  │
│  ░                   ░  │
│  ░░░░░░░░░░░░░░░░░░░░  │
└─────────────────────────┘
```

| 元素 | 标识 | 位置 | 交互 |
|------|------|------|------|
| 贪婪木乃伊 | `NPC_MUMMY` | 地图中心 | 打开商店界面 |
| 传送门 | `PORTAL_NEXT` | 地图南侧中央 | 点击进入下一关 |
| 不可破坏墙 | `WALL_BOUNDARY` | 地图四周边界 | 阻挡移动 |

### 1.4 进入与退出流程

```
[关卡完成] → [加载商店关卡] → [玩家出现在传送门旁]
                                        │
                                        ├──(与木乃伊交互)──> [打开商店界面]
                                        │
                                        └──(走向传送门)──> [加载下一关]
```

**退出条件**：
- 玩家走向传送门 → 加载下一关卡
- 玩家可随时与木乃伊交互购买，无时间限制
- 商店关卡内无失败条件

---

## 2. 商品目录与定价模型 (Shop Inventory & Price Scaling)

### 2.1 商品总览

| 商品 | 类型 | 价格 | 效果 | 约束 |
|------|------|------|------|------|
| 铁锹 (Pickaxe) | 消耗品 | 50 金币 | pickaxeCount += 1 | 受容量上限约束 |
| 炸药 (Dynamite) | 消耗品 | 100 金币 | dynamiteCount += 1 | 受容量上限约束 |
| 地图 (Treasure Map) | 消耗品 | 75 金币 | mapCount += 1 | 受容量上限约束 |
| 护盾充能 (Shield Refill) | 服务 | 见 §2.2 | currentShield = maxShield | — |
| 生命上限+1 (Max Hearts) | 永久升级 | 见 §2.3 | maxHearts += 1 | 上限 8 |
| 容量升级 (Capacity) | 永久升级 | 见 §2.3 | maxCapacity 升一级 | 上限 30 |
| 重生护身符 (Amulet) | 特殊 | 见 §2.4 | amuletCount += 1 | 上限 1 |

### 2.2 护盾充能 (Shield Refill)

补满当前所有护盾（`currentShield = maxShield`）。

| 参数 | 值 |
|------|-----|
| 价格公式 | `price = maxShield × 75` |
| 示例 | maxShield=1 → 75 金币；maxShield=2 → 150 金币；maxShield=3 → 225 金币 |

### 2.3 永久升级定价

#### 生命上限 +1

| 当前 maxHearts | 价格 (金币) |
|---------------|-------------|
| 3 → 4 | 300 |
| 4 → 5 | 500 |
| 5 → 6 | 800 |
| 6 → 7 | 1200 |
| 7 → 8 | 2000 |
| 已达 8 | 不可购买 | |

#### 容量等级升级

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
| 已达 Lv 8 | 30 | 不可购买 |

### 2.4 重生护身符 (Amulet of Rebirth)

#### 基本属性

| 属性 | 值 | 说明 |
|------|-----|------|
| 携带上限 | 1 | 最多同时持有 1 个 |
| 初始价格 | 100 金币 | 首次购买价格 |
| 价格增长 | 翻倍 | 每次复活后再次购买价格翻倍 |

#### 动态加价模型

```
护身符价格 = BASE_AMULET_PRICE × 2^(purchaseCount)

其中:
  BASE_AMULET_PRICE = 100
  purchaseCount = 本次购买前已购买过的次数
```

| 购买次数 | 价格 (金币) |
|----------|-------------|
| 第 1 次 | 100 |
| 第 2 次 | 200 |
| 第 3 次 | 400 |
| 第 4 次 | 800 |
| 第 5 次 | 1600 |
| 第 6 次 | 3200 |
| 第 7 次 | 6400 |
| ... | ... |

#### 购买约束

```
FUNCTION canBuyAmulet(economy: EconomyData, amuletState: AmuletState):
    IF amuletState.amuletCount >= 1 THEN
        RETURN { eligible: false, reason: "ALREADY_CARRYING" }
    END IF
    
    price = calculateAmuletPrice(amuletState)
    IF economy.gold < price THEN
        RETURN { eligible: false, reason: "INSUFFICIENT_GOLD" }
    END IF
    
    RETURN { eligible: true, price: price }
END FUNCTION
```

---

## 3. 复活与 Roguelite 死亡数据流 (Resurrection & Death Progression Flow)

### 3.1 死亡判定入口

当角色生命值（Hearts）归零时，系统进入死亡判定流程：

```
[Hearts 归零] → handlePlayerDeath() → 分支判定
```

### 3.2 有护身符复活流程 (With Amulet)

**触发条件**：`currentHearts <= 0` 且 `amuletState.amuletCount >= 1`

**复活效果**：

| 数据 | 处理 | 说明 |
|------|------|------|
| 重生护身符 | 消耗 1 个 | `amuletCount -= 1` |
| 生命值 | 恢复至满 | `currentHearts = maxHearts` |
| 护盾 | 清空 | `currentShield = 0` |
| 金币 | ✅ 保留 | 全局金币不丢失 |
| 永久升级 | ✅ 保留 | maxHearts、maxCapacity 等全部保留 |
| 当前关卡工具 | ❌ 清空 | 铁锹、炸药、地图全部重置 |
| 当前关卡钥匙 | ❌ 清空 | 所有钥匙丢失 |
| 当前位置 | 传送至商店 | 进入最近一次访问的商店关卡 |
| 关卡进度 | 退回上一关 | 需重新通过上一关才能进入当前关 |

```
FUNCTION resurrectPlayer(hero: Hero, runState: RunState):
    // 消耗护身符
    runState.amuletCount -= 1
    
    // 恢复生命
    hero.vitalStats.currentHearts = hero.vitalStats.maxHearts
    hero.vitalStats.currentShield = 0
    
    // 清空当前关卡工具
    hero.toolInventory.pickaxeCount = 0
    hero.toolInventory.dynamiteCount = 0
    hero.toolInventory.mapCount = 0
    
    // 清空钥匙
    hero.inventory.keys = { red: 0, green: 0, blue: 0, exit: 0 }
    
    // 退回上一关
    runState.currentLevel = runState.lastShopLevel - 1
    
    // 传送至商店
    runState.phase = RunPhase.SHOP
    loadShopLevel(runState.lastShopLevel)
    
    // 增加复活计数
    runState.totalResurrections += 1
    
    // 增加护身符价格
    runState.amuletPurchaseCount += 1
    
    triggerResurrectionFX()
END FUNCTION
```

### 3.3 无护身符死亡流程 (Without Amulet — Game Over)

**触发条件**：`currentHearts <= 0` 且 `amuletState.amuletCount == 0`

**死亡效果**：

| 数据 | 处理 | 说明 |
|------|------|------|
| 金币 | ❌ 清空 | 当前携带金币全部丢失 |
| 工具 | ❌ 清空 | 铁锹、炸药、地图全部丢失 |
| 钥匙 | ❌ 清空 | 所有钥匙丢失 |
| 红心上限 | ✅ 保留 | 永久升级保留 |
| 护盾上限 | ✅ 保留 | 永久升级保留 |
| 容量等级 | ✅ 保留 | 永久升级保留 |
| 关卡进度 | ❌ 重置 | 必须从第 1 关重新开始 |
| 护身符价格 | ❌ 重置 | 恢复至初始 100 金币 |

```
FUNCTION gameOver(hero: Hero, runState: RunState, persistentData: PersistentData):
    // 清空当前运行数据
    runState = createNewRun()
    
    // 保留永久升级
    persistentData.maxHearts = hero.vitalStats.maxHearts
    persistentData.maxShield = hero.vitalStats.maxShield
    persistentData.capacityLevel = hero.toolInventory.capacityLevel
    
    // 清空临时数据
    hero.toolInventory = createDefaultToolInventory()
    hero.inventory = createDefaultInventory()
    hero.vitalStats.currentHearts = hero.vitalStats.maxHearts
    hero.vitalStats.currentShield = 0
    
    // 重置护身符价格
    persistentData.amuletPurchaseCount = 0
    
    // 显示 Game Over 界面
    showGameOverScreen({
        levelReached: runState.currentLevel,
        goldLost: runState.goldThisRun,
        stepsTaken: runState.stepsThisRun,
        cause: hero.lastDamageSource
    })
    
    // 返回主菜单
    transitionToMainMenu()
END FUNCTION
```

### 3.4 数据保留总结

| 数据类型 | 有护身符复活 | 无护身符死亡 |
|----------|-------------|-------------|
| 全局金币 | ✅ 保留 | ❌ 清空 |
| 红心上限 | ✅ 保留 | ✅ 保留 |
| 护盾上限 | ✅ 保留 | ✅ 保留 |
| 容量等级 | ✅ 保留 | ✅ 保留 |
| 当前工具 | ❌ 清空 | ❌ 清空 |
| 当前钥匙 | ❌ 清空 | ❌ 清空 |
| 关卡进度 | 退回上一关 | 重置至第 1 关 |
| 护身符价格 | 翻倍上涨 | 重置为 100 |
| 复活计数 | +1 | 不变 |

---

## 4. 核心逻辑伪代码与系统接口 (Logic & Interface Definition)

### 4.1 死亡判定核心逻辑

```
FUNCTION handlePlayerDeath(hero: Hero, runState: RunState, persistentData: PersistentData):
    // 播放死亡动画
    playDeathAnimation(hero)
    
    // 等待动画结束
    await animationComplete(DEATH_ANIMATION_DURATION)
    
    // 分支判定
    IF runState.amuletCount >= 1 THEN
        // 有护身符 → 复活
        showResurrectionDialog({
            amuletCount: runState.amuletCount,
            nextLevel: runState.lastShopLevel - 1
        })
        
        IF playerConfirmsResurrection() THEN
            resurrectPlayer(hero, runState)
        ELSE
            // 玩家拒绝复活 → 等同 Game Over
            gameOver(hero, runState, persistentData)
        END IF
    ELSE
        // 无护身符 → Game Over
        gameOver(hero, runState, persistentData)
    END IF
END FUNCTION
```

### 4.2 护身符价格计算

```
FUNCTION calculateAmuletPrice(amuletState: AmuletState):
    BASE_PRICE = 100
    multiplier = pow(2, amuletState.purchaseCount)
    RETURN BASE_PRICE * multiplier
END FUNCTION
```

### 4.3 商店购买逻辑

```
FUNCTION purchaseShopItem(item: ShopItem, hero: Hero, runState: RunState, persistentData: PersistentData):
    SWITCH item.type:
        CASE ITEM_PICKAXE:
            IF NOT hasCapacityFor(hero.toolInventory, 1) THEN
                RETURN { success: false, reason: "CAPACITY_FULL" }
            END IF
            IF persistentData.economy.gold < item.price THEN
                RETURN { success: false, reason: "INSUFFICIENT_GOLD" }
            END IF
            persistentData.economy.gold -= item.price
            hero.toolInventory.pickaxeCount += 1
            RETURN { success: true }
            
        CASE ITEM_DYNAMITE:
            IF NOT hasCapacityFor(hero.toolInventory, 1) THEN
                RETURN { success: false, reason: "CAPACITY_FULL" }
            END IF
            IF persistentData.economy.gold < item.price THEN
                RETURN { success: false, reason: "INSUFFICIENT_GOLD" }
            END IF
            persistentData.economy.gold -= item.price
            hero.toolInventory.dynamiteCount += 1
            RETURN { success: true }
            
        CASE ITEM_MAP:
            IF NOT hasCapacityFor(hero.toolInventory, 1) THEN
                RETURN { success: false, reason: "CAPACITY_FULL" }
            END IF
            IF persistentData.economy.gold < item.price THEN
                RETURN { success: false, reason: "INSUFFICIENT_GOLD" }
            END IF
            persistentData.economy.gold -= item.price
            hero.toolInventory.mapCount += 1
            RETURN { success: true }
            
        CASE ITEM_SHIELD_REFILL:
            IF persistentData.economy.gold < item.price THEN
                RETURN { success: false, reason: "INSUFFICIENT_GOLD" }
            END IF
            persistentData.economy.gold -= item.price
            hero.vitalStats.currentShield = hero.vitalStats.maxShield
            RETURN { success: true }
            
        CASE ITEM_MAX_HEARTS_UP:
            IF hero.vitalStats.maxHearts >= hero.vitalStats.hardCapHearts THEN
                RETURN { success: false, reason: "MAX_REACHED" }
            END IF
            IF persistentData.economy.gold < item.price THEN
                RETURN { success: false, reason: "INSUFFICIENT_GOLD" }
            END IF
            persistentData.economy.gold -= item.price
            hero.vitalStats.maxHearts += 1
            hero.vitalStats.currentHearts += 1
            RETURN { success: true }
            
        CASE ITEM_CAPACITY_UP:
            IF hero.toolInventory.capacityLevel >= MAX_CAPACITY_LEVEL THEN
                RETURN { success: false, reason: "MAX_REACHED" }
            END IF
            IF persistentData.economy.gold < item.price THEN
                RETURN { success: false, reason: "INSUFFICIENT_GOLD" }
            END IF
            persistentData.economy.gold -= item.price
            hero.toolInventory.capacityLevel += 1
            hero.toolInventory.maxCapacity = CAPACITY_LADDER[hero.toolInventory.capacityLevel]
            RETURN { success: true }
            
        CASE ITEM_AMULET:
            result = canBuyAmulet(persistentData.economy, runState)
            IF NOT result.eligible THEN
                RETURN { success: false, reason: result.reason }
            END IF
            persistentData.economy.gold -= result.price
            runState.amuletCount += 1
            runState.amuletPurchaseCount += 1
            RETURN { success: true, newPrice: calculateAmuletPrice(runState) }
            
        DEFAULT:
            RETURN { success: false, reason: "UNKNOWN_ITEM" }
    END SWITCH
END FUNCTION
```

### 4.4 数据结构定义

```typescript
// ===== 商店商品类型 =====
enum ShopItemType {
  PICKAXE = 'PICKAXE',
  DYNAMITE = 'DYNAMITE',
  TREASURE_MAP = 'TREASURE_MAP',
  SHIELD_REFILL = 'SHIELD_REFILL',
  MAX_HEARTS_UP = 'MAX_HEARTS_UP',
  CAPACITY_UP = 'CAPACITY_UP',
  AMULET = 'AMULET',
}

// ===== 商店商品 =====
interface ShopItem {
  type: ShopItemType;
  name: string;
  description: string;
  price: number;                    // 固定价格（动态商品计算时忽略）
  isDynamicPrice: boolean;          // 是否为动态价格
  isPermanent: boolean;             // 是否为永久升级
  canPurchase: (state: GameState) => boolean;  // 购买条件检查
  onPurchase: (state: GameState) => void;      // 购买效果
}

// ===== 护身符状态 =====
interface AmuletState {
  amuletCount: number;       // 当前携带数量 (0 或 1)
  purchaseCount: number;     // 历史购买次数（用于计算价格）
}

const DEFAULT_AMULET_STATE: AmuletState = {
  amuletCount: 0,
  purchaseCount: 0,
};

// ===== 运行状态（单次探险） =====
interface RunState {
  currentLevel: number;      // 当前关卡
  lastShopLevel: number;     // 最近一次商店所在关卡
  amuletCount: number;       // 当前携带护身符数量
  amuletPurchaseCount: number; // 本次运行购买护身符次数
  totalResurrections: number; // 本次运行复活次数
  goldThisRun: number;       // 本次运行获得的金币
  stepsThisRun: number;      // 本次运行步数
  phase: RunPhase;           // 当前阶段
}

enum RunPhase {
  LEVEL = 'LEVEL',
  SHOP = 'SHOP',
  DEATH_ANIMATION = 'DEATH_ANIMATION',
  GAME_OVER = 'GAME_OVER',
}

// ===== 永久数据（跨运行保留） =====
interface PersistentData {
  economy: EconomyData;      // 引用 04_tools_and_economy.md
  maxHearts: number;
  maxShield: number;
  capacityLevel: number;
  amuletPurchaseCount: number;  // 跨运行累计（用于护身符价格）
  bestLevelReached: number;     // 历史最佳关卡
  totalRuns: number;            // 总探险次数
}

// ===== 商店状态 =====
interface ShopState {
  isVisible: boolean;         // 商店界面是否打开
  availableItems: ShopItem[]; // 当前可购买商品列表
  amuletPrice: number;        // 当前护身符价格（动态计算）
}

// ===== 商店商品列表生成 =====
FUNCTION generateShopItems(hero: Hero, runState: RunState): ShopItem[] {
  items = []
  
  // 消耗品（始终显示）
  items.push({ type: PICKAXE, price: 50, ... })
  items.push({ type: DYNAMITE, price: 100, ... })
  items.push({ type: TREASURE_MAP, price: 75, ... })
  
  // 护盾充能
  items.push({ type: SHIELD_REFILL, price: hero.vitalStats.maxShield * 75, ... })
  
  // 永久升级（条件显示）
  IF hero.vitalStats.maxHearts < 8 THEN
    items.push({ type: MAX_HEARTS_UP, price: getHeartUpgradePrice(hero.vitalStats.maxHearts), ... })
  END IF
  
  IF hero.toolInventory.capacityLevel < MAX_CAPACITY_LEVEL THEN
    items.push({ type: CAPACITY_UP, price: getCapacityUpgradePrice(hero.toolInventory.capacityLevel), ... })
  END IF
  
  // 护身符（条件显示）
  IF runState.amuletCount < 1 THEN
    items.push({ type: AMULET, price: calculateAmuletPrice(runState), ... })
  END IF
  
  RETURN items
}
```

### 4.5 商店触发判定

```
FUNCTION shouldTriggerShop(completedLevel: number):
    IF completedLevel == 1 THEN
        RETURN true
    END IF
    IF completedLevel > 1 AND completedLevel % 5 == 0 THEN
        RETURN true
    END IF
    RETURN false
END FUNCTION

// 关卡完成时调用
FUNCTION onLevelComplete(levelId: number, runState: RunState, persistentData: PersistentData):
    IF shouldTriggerShop(levelId) THEN
        runState.lastShopLevel = levelId
        runState.phase = RunPhase.SHOP
        loadShopLevel()
    ELSE
        runState.phase = RunPhase.LEVEL
        loadNextLevel(levelId + 1)
    END IF
END FUNCTION
```

---

## 附录：数据保留速查表

| 数据 | 有护身符复活 | 无护身符死亡 (Game Over) |
|------|-------------|-------------------------|
| 全局金币 | ✅ 保留 | ❌ 清空 |
| 红心/护盾上限 | ✅ 保留 | ✅ 保留 |
| 容量等级 | ✅ 保留 | ✅ 保留 |
| 工具 (铁锹/炸药/地图) | ❌ 清空 | ❌ 清空 |
| 钥匙 | ❌ 清空 | ❌ 清空 |
| 关卡进度 | 退回上一关 | 重置至第 1 关 |
| 护身符价格 | 翻倍 | 重置为 100 |
| 历史最佳关卡 | ✅ 保留 | ✅ 保留 |

---

*文档版本: v1.0 | 创建日期: 2026-06-25 | 依赖: docs/04_tools_and_economy.md*
