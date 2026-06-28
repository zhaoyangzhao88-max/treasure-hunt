# 第 3 课：地图交互元素、障碍物与钥匙/门机制规范设计

> 本文档定义 Microsoft Treasure Hunt 复刻项目中所有地图交互元素的分类、属性、碰撞交互逻辑、钥匙与门色彩匹配机制，以及底层实体数据结构。本文档与 `01_core_gameplay.md`（瓦片系统）和 `02_hearts_and_shields.md`（生命系统）配合使用，构成完整的地图交互规范。所有后续课程应严格遵循本文档所定义的契约。

---

## 目录

1. [地图元素分类与属性 (Map Elements Classification)](#1-地图元素分类与属性-map-elements-classification)
2. [触发与碰撞交互逻辑 (Interaction & Collision Logic)](#2-触发与碰撞交互逻辑-interaction--collision-logic)
3. [钥匙与门色彩匹配机制 (Key-Gate Color Matching)](#3-钥匙与门色彩匹配机制-key-gate-color-matching)
4. [底层实体数据结构定义 (Data Structure & Type Definitions)](#4-底层实体数据结构定义-data-structure--type-definitions)

---

## 1. 地图元素分类与属性 (Map Elements Classification)

### 1.1 元素分类总览

地图元素分为两大类：**可收集实体 (Collectibles)** 和 **阻挡障碍物 (Obstacles)**。

```
地图元素 (MapEntity)
├── 可收集实体 (Collectible)
│   ├── 金币 (Coin)
│   ├── 钥匙 (Key)
│   ├── 红心 (Heart)
│   ├── 护盾 (Shield)
│   └── 工具 (Tool)
│       ├── 铁锹 (Shovel)
│       ├── 地图 (Map)
│       └── 炸药 (Dynamite)
│
└── 阻挡障碍物 (Obstacle)
    ├── 不可破坏墙 (IndestructibleWall)
    ├── 泥墙 / 可破坏墙 (DirtWall)
    └── 锁门 (LockedGate)
        ├── 红色锁门 (RedGate)
        ├── 绿色锁门 (GreenGate)
        ├── 蓝色锁门 (BlueGate)
        └── 出口门 (ExitGate)
```

### 1.2 可收集实体详细属性

#### 1.2.1 金币 (Coin)

| 属性 | 值 | 说明 |
|------|-----|------|
| 标识 | `ENTITY_COIN` | 实体类型标识 |
| 价值 | `1` | 单个金币价值 |
| 视觉 | 金色圆形图标 | 旋转动画（可选） |
| 收集条件 | 角色坐标重合 | 自动收集 |
| 收集效果 | `inventory.coins += 1` | 增加金币计数 |

#### 1.2.2 钥匙 (Key)

| 属性 | 值 | 说明 |
|------|-----|------|
| 标识 | `ENTITY_KEY_{COLOR}` | 颜色标识（KEY_RED, KEY_GREEN, KEY_BLUE, KEY_EXIT） |
| 价值 | — | 功能性道具，无货币价值 |
| 视觉 | 对应颜色的钥匙图标 | 红/绿/蓝/金 |
| 收集条件 | 角色坐标重合 | 自动收集 |
| 收集效果 | `inventory.keys.{color} += 1` | 增加对应颜色钥匙 |

#### 1.2.3 红心 (Heart Pickup)

| 属性 | 值 | 说明 |
|------|-----|------|
| 标识 | `ENTITY_HEART` | 实体类型标识 |
| 视觉 | 红色心形图标 | 弹跳动画（可选） |
| 收集条件 | 角色坐标重合 | 自动收集 |
| 收集效果 | 遵循 `02_hearts_and_shields.md` §3.1.1 | +1 红心，不超过 maxHearts |

#### 1.2.4 护盾 (Shield Pickup)

| 属性 | 值 | 说明 |
|------|-----|------|
| 标识 | `ENTITY_SHIELD` | 实体类型标识 |
| 视觉 | 蓝色盾牌图标 | — |
| 收集条件 | 角色坐标重合 | 自动收集 |
| 收集效果 | 遵循 `02_hearts_and_shields.md` §3.1.2 | +1 护盾，不超过 maxShield |

#### 1.2.5 工具类 (Tools)

##### 铁锹 (Shovel)

| 属性 | 值 | 说明 |
|------|-----|------|
| 标识 | `ENTITY_SHOVEL` | 实体类型标识 |
| 视觉 | 铲子/镐子图标 | — |
| 收集条件 | 角色坐标重合 | 自动收集 |
| 收集效果 | `inventory.shovels += 1` | 用于破坏泥墙 |
| 消耗规则 | 破除 1 个泥墙消耗 1 个铁锹 | — |

##### 地图 (Map Fragment)

| 属性 | 值 | 说明 |
|------|-----|------|
| 标识 | `ENTITY_MAP` | 实体类型标识 |
| 视觉 | 羊皮纸/地图碎片图标 | — |
| 收集条件 | 角色坐标重合 | 自动收集 |
| 收集效果 | 揭示部分迷雾区域（关卡设计决定范围） | 可选功能 |

##### 炸药 (Dynamite)

| 属性 | 值 | 说明 |
|------|-----|------|
| 标识 | `ENTITY_DYNAMITE` | 实体类型标识 |
| 视觉 | 炸药桶/ TNT 图标 | — |
| 收集条件 | 角色坐标重合 | 自动收集 |
| 收集效果 | `inventory.dynamite += 1` | 可炸毁 3×3 区域内的所有可破坏物 |

### 1.3 阻挡障碍物详细属性

#### 1.3.1 不可破坏墙 (Indestructible Wall)

| 属性 | 值 | 说明 |
|------|-----|------|
| 标识 | `ENTITY_WALL_INDESTRUCTIBLE` | 实体类型标识 |
| 视觉 | 实心砖墙/石块纹理 | — |
| 阻挡类型 | 完全阻挡 | 不可通过，不可破坏 |
| 可被破坏？ | ❌ 否 | 任何道具/操作均无效 |

#### 1.3.2 泥墙 / 可破坏墙 (Dirt Wall)

| 属性 | 值 | 说明 |
|------|-----|------|
| 标识 | `ENTITY_WALL_DIRT` | 实体类型标识 |
| 视觉 | 泥土/泥砖纹理 | 与 DIRT 瓦片区分 |
| 阻挡类型 | 完全阻挡 | 不可通过，但可被破坏 |
| 破坏条件 | 持有铁锹 (Shovel) | 消耗 1 个铁锹 |
| 破坏后状态 | 变为 `UNCOVERED`（空地） | — |

#### 1.3.3 锁门 (Locked Gate)

| 属性 | 值 | 说明 |
|------|-----|------|
| 标识 | `ENTITY_GATE_{COLOR}` | 颜色标识（GATE_RED, GATE_GREEN, GATE_BLUE） |
| 视觉 | 对应颜色的门框 + 锁图标 | — |
| 阻挡类型 | 完全阻挡 | 不可通过，但可被对应钥匙解锁 |
| 解锁条件 | 持有对应颜色钥匙 | 消耗 1 把对应钥匙 |
| 解锁后状态 | 变为 `UNCOVERED`（空地） | — |

#### 1.3.4 出口门 (Exit Gate)

| 属性 | 值 | 说明 |
|------|-----|------|
| 标识 | `ENTITY_GATE_EXIT` | 实体类型标识 |
| 视觉 | 金色大门 + 钥匙孔 | 初始锁定，得钥匙后发光 |
| 阻挡类型 | 完全阻挡 | 需专用钥匙解锁 |
| 解锁条件 | 持有出口钥匙 (Exit Key) | 消耗 1 把出口钥匙 |
| 解锁后状态 | 激活状态 | 角色进入触发通关 |

---

## 2. 触发与碰撞交互逻辑 (Interaction & Collision Logic)

### 2.1 交互类型总览

| 交互类型 | 触发条件 | 适用元素 |
|----------|----------|----------|
| 步入式触发 (Step-on) | 角色坐标 == 实体坐标 | 所有可收集实体 |
| 相邻交互 (Adjacent) | 角色尝试移动/点击到相邻格 | 泥墙、锁门 |

### 2.2 步入式触发 (Step-on Activation)

当角色移动到一个包含可收集实体的格子时，自动触发收集：

```
FUNCTION onStepOnto(tile: Tile, hero: Hero):
    entity = tile.getEntity()
    
    IF entity IS Collectible THEN
        collectResult = collectEntity(entity, hero)
        IF collectResult.success THEN
            tile.removeEntity()     // 从地图移除
            triggerCollectFX(entity) // 播放收集特效
            updateUI()               // 更新 UI 显示
        END IF
    END IF
END FUNCTION
```

**收集逻辑**：

```
FUNCTION collectEntity(entity: Collectible, hero: Hero):
    SWITCH entity.type:
        CASE ENTITY_COIN:
            hero.inventory.coins += 1
            RETURN { success: true }
            
        CASE ENTITY_KEY_RED:
            hero.inventory.keys.red += 1
            RETURN { success: true }
            
        CASE ENTITY_KEY_GREEN:
            hero.inventory.keys.green += 1
            RETURN { success: true }
            
        CASE ENTITY_KEY_BLUE:
            hero.inventory.keys.blue += 1
            RETURN { success: true }
            
        CASE ENTITY_KEY_EXIT:
            hero.inventory.keys.exit += 1
            RETURN { success: true }
            
        CASE ENTITY_HEART:
            IF hero.vitalStats.currentHearts < hero.vitalStats.maxHearts THEN
                hero.vitalStats.currentHearts += 1
                RETURN { success: true }
            ELSE
                RETURN { success: false, reason: "HEARTS_FULL" }
            END IF
            
        CASE ENTITY_SHIELD:
            IF hero.vitalStats.currentShield < hero.vitalStats.maxShield THEN
                hero.vitalStats.currentShield += 1
                RETURN { success: true }
            ELSE
                RETURN { success: false, reason: "SHIELDS_FULL" }
            END IF
            
        CASE ENTITY_SHOVEL:
            hero.inventory.shovels += 1
            RETURN { success: true }
            
        CASE ENTITY_MAP:
            revealMapArea(entity.mapArea)
            RETURN { success: true }
            
        CASE ENTITY_DYNAMITE:
            hero.inventory.dynamite += 1
            RETURN { success: true }
            
        DEFAULT:
            RETURN { success: false, reason: "UNKNOWN_ENTITY" }
    END SWITCH
END FUNCTION
```

### 2.3 相邻交互 (Adjacent Interaction)

当角色尝试向一个包含障碍物的格子移动时，触发相邻交互判定：

```
FUNCTION tryMoveTo(targetPos: TilePosition, hero: Hero):
    targetTile = grid.getTile(targetPos)
    entity = targetTile.getEntity()
    
    IF entity IS Obstacle THEN
        SWITCH entity.type:
            CASE ENTITY_WALL_INDESTRUCTIBLE:
                RETURN { success: false, reason: "BLOCKED_INDESTRUCTIBLE" }
                
            CASE ENTITY_WALL_DIRT:
                IF hero.inventory.shovels > 0 THEN
                    hero.inventory.shovels -= 1
                    targetTile.setEntity(null)
                    targetTile.setState(UNCOVERED)
                    triggerDirtWallBreakFX(targetPos)
                    RETURN { success: true, consumed: "SHOVEL" }
                ELSE
                    RETURN { success: false, reason: "NO_SHOVEL" }
                END IF
                
            CASE ENTITY_GATE_RED:
                IF hero.inventory.keys.red > 0 THEN
                    hero.inventory.keys.red -= 1
                    targetTile.setEntity(null)
                    targetTile.setState(UNCOVERED)
                    triggerGateUnlockFX(targetPos, RED)
                    RETURN { success: true, consumed: "KEY_RED" }
                ELSE
                    RETURN { success: false, reason: "NO_KEY_RED" }
                END IF
                
            CASE ENTITY_GATE_GREEN:
                IF hero.inventory.keys.green > 0 THEN
                    hero.inventory.keys.green -= 1
                    targetTile.setEntity(null)
                    targetTile.setState(UNCOVERED)
                    triggerGateUnlockFX(targetPos, GREEN)
                    RETURN { success: true, consumed: "KEY_GREEN" }
                ELSE
                    RETURN { success: false, reason: "NO_KEY_GREEN" }
                END IF
                
            CASE ENTITY_GATE_BLUE:
                IF hero.inventory.keys.blue > 0 THEN
                    hero.inventory.keys.blue -= 1
                    targetTile.setEntity(null)
                    targetTile.setState(UNCOVERED)
                    triggerGateUnlockFX(targetPos, BLUE)
                    RETURN { success: true, consumed: "KEY_BLUE" }
                ELSE
                    RETURN { success: false, reason: "NO_KEY_BLUE" }
                END IF
                
            CASE ENTITY_GATE_EXIT:
                IF hero.inventory.keys.exit > 0 THEN
                    hero.inventory.keys.exit -= 1
                    targetTile.setEntity(null)
                    targetTile.setState(UNCOVERED)
                    triggerExitGateOpenFX(targetPos)
                    RETURN { success: true, consumed: "KEY_EXIT" }
                ELSE
                    RETURN { success: false, reason: "NO_KEY_EXIT" }
                END IF
                
            DEFAULT:
                RETURN { success: false, reason: "UNKNOWN_OBSTACLE" }
        END SWITCH
    END IF
    
    // 无障碍，正常移动
    hero.position = targetPos
    onStepOnto(targetTile, hero)
    RETURN { success: true }
END FUNCTION
```

### 2.4 交互优先级总结

```
玩家点击/移动:
  ├─ 目标格为 UNCOVERED → 移动角色
  ├─ 目标格含 Collectible → 移动 + 收集
  ├─ 目标格含 DirtWall + 有 Shovel → 消耗 Shovel → 揭开 → 移动
  ├─ 目标格含 LockedGate + 有 Key → 消耗 Key → 揭开 → 移动
  ├─ 目标格含 Obstacle + 无工具 → 拒绝移动，显示提示
  └─ 目标格含 IndestructibleWall → 拒绝移动
```

---

## 3. 钥匙与门色彩匹配机制 (Key-Gate Color Matching)

### 3.1 颜色枚举

```typescript
enum KeyColor {
  RED = 'RED',
  GREEN = 'GREEN',
  BLUE = 'BLUE',
  EXIT = 'EXIT'  // 金色/特殊
}

enum GateColor {
  RED = 'RED',
  GREEN = 'GREEN',
  BLUE = 'BLUE',
  EXIT = 'EXIT'  // 出口门
}
```

### 3.2 匹配规则

| 钥匙 | 可解锁的门 | 说明 |
|------|-----------|------|
| 红色钥匙 (Key Red) | 红色锁门 (Gate Red) | 一对一匹配 |
| 绿色钥匙 (Key Green) | 绿色锁门 (Gate Green) | 一对一匹配 |
| 蓝色钥匙 (Key Blue) | 蓝色锁门 (Gate Blue) | 一对一匹配 |
| 出口钥匙 (Key Exit) | 出口门 (Gate Exit) | 专用钥匙 |

**匹配逻辑**：

```
FUNCTION canUnlock(gateColor: GateColor, keyColor: KeyColor):
    RETURN gateColor === keyColor
END FUNCTION
```

> **设计原则**：颜色严格匹配，不可跨色使用。出口钥匙独立于三色钥匙体系。

### 3.3 出口门特殊规则

出口门除了需要专用出口钥匙外，还关联通关判定：

```
FUNCTION onExitGateOpened(gatePos: TilePosition, hero: Hero):
    // 出口门解锁后，角色进入即通关
    IF hero.position == gatePos THEN
        triggerLevelComplete()
    END IF
END FUNCTION
```

### 3.4 钥匙数量约束

| 约束 | 规则 |
|------|------|
| 单种颜色钥匙上限 | `9`（设计约束，避免溢出） |
| 钥匙总数上限 | `27`（9×3 色 + 出口钥匙单独计算） |
| 出口钥匙上限 | `1`（每关仅 1 把） |
| 钥匙不可再生 | 关卡内钥匙数量固定，消耗后不补充 |

---

## 4. 底层实体数据结构定义 (Data Structure & Type Definitions)

### 4.1 瓦片层级深度 (Tile Layer Depth)

地图采用分层渲染与逻辑处理：

```
Layer 2 (顶层)  ─ 可收集实体层 (Collectible Entities)
                  渲染优先级：最高
                  逻辑：碰撞检测、收集判定
                  
Layer 1 (中间层) ─ 静态阻挡层 (Static Obstacles)
                  渲染优先级：中
                  逻辑：移动阻挡、破坏判定
                  
Layer 0 (底层)  ─ 背景/地形层 (Background / Terrain)
                  渲染优先级：最低
                  逻辑：瓦片状态（DIRT/UNCOVERED/TRAP）
```

```typescript
interface TileLayer {
  background: TileState;       // Layer 0: DIRT | UNCOVERED | TRAP
  obstacle: ObstacleEntity;     // Layer 1: Wall | DirtWall | LockedGate | null
  collectible: CollectibleEntity; // Layer 2: Coin | Key | Heart | Shield | Tool | null
}
```

### 4.2 实体类型定义

```typescript
// ===== 基础实体 =====
interface MapEntity {
  id: string;
  type: EntityType;
  position: TilePosition;
  isCollected: boolean;
}

// ===== 可收集实体 =====
interface CollectibleEntity extends MapEntity {
  type: EntityType.COIN
        | EntityType_KEY_RED | EntityType_KEY_GREEN
        | EntityType_KEY_BLUE | EntityType_KEY_EXIT
        | EntityType_HEART | EntityType_SHIELD
        | EntityType_SHOVEL | EntityType_MAP | EntityType_DYNAMITE;
  value: number;  // 金币价值，其他为 0
}

// ===== 障碍物实体 =====
interface ObstacleEntity extends MapEntity {
  type: EntityType_WALL_INDESTRUCTIBLE
        | EntityType_WALL_DIRT
        | EntityType_GATE_RED | EntityType_GATE_GREEN
        | EntityType_GATE_BLUE | EntityType_GATE_EXIT;
  destructible: boolean;
  requiredItem: EntityType | null;  // 破坏所需道具
}
```

### 4.3 背包/库存定义

```typescript
interface Inventory {
  coins: number;
  keys: {
    red: number;
    green: number;
    blue: number;
    exit: number;
  };
  shovels: number;
  dynamite: number;
  mapFragments: number;
}

const DEFAULT_INVENTORY: Inventory = {
  coins: 0,
  keys: { red: 0, green: 0, blue: 0, exit: 0 },
  shovels: 0,
  dynamite: 0,
  mapFragments: 0,
};
```

### 4.4 完整枚举定义

```typescript
enum EntityType {
  // 可收集
  COIN = 'COIN',
  KEY_RED = 'KEY_RED',
  KEY_GREEN = 'KEY_GREEN',
  KEY_BLUE = 'KEY_BLUE',
  KEY_EXIT = 'KEY_EXIT',
  HEART = 'HEART',
  SHIELD = 'SHIELD',
  SHOVEL = 'SHOVEL',
  MAP = 'MAP',
  DYNAMITE = 'DYNAMITE',

  // 障碍物
  WALL_INDESTRUCTIBLE = 'WALL_INDESTRUCTIBLE',
  WALL_DIRT = 'WALL_DIRT',
  GATE_RED = 'GATE_RED',
  GATE_GREEN = 'GATE_GREEN',
  GATE_BLUE = 'GATE_BLUE',
  GATE_EXIT = 'GATE_EXIT',
}
```

### 4.5 碰撞检测基础逻辑（伪代码）

```
// 基于网格坐标的碰撞检测（无需 AABB）
FUNCTION checkCollision(heroPos: TilePosition, entityPos: TilePosition):
    RETURN heroPos.x === entityPos.x AND heroPos.y === entityPos.y
END FUNCTION

// 每帧/每步移动检测
FUNCTION processMovement(targetPos: TilePosition, hero: Hero):
    targetTile = grid.getTile(targetPos)
    
    // Layer 1: 障碍物检测
    IF targetTile.obstacle !== null THEN
        result = tryInteractWithObstacle(targetTile.obstacle, hero)
        IF NOT result.success THEN
            showFeedback(result.reason)  // 显示"需要铁锹"等提示
            RETURN false
        END IF
        // 障碍物已破坏，继续移动
    END IF
    
    // 执行移动
    hero.position = targetPos
    
    // Layer 2: 可收集实体检测
    IF targetTile.collectible !== null THEN
        collectEntity(targetTile.collectible, hero)
        targetTile.collectible = null
    END IF
    
    RETURN true
END FUNCTION
```

### 4.6 Pygame 坐标参考

```python
# Pygame 中的基础坐标与碰撞（参考实现）
class Entity:
    def __init__(self, x: int, y: int, entity_type: str):
        self.grid_x = x        # 网格列坐标
        self.grid_y = y        # 网格行坐标
        self.pixel_x = x * TILE_SIZE  # 像素坐标
        self.pixel_y = y * TILE_SIZE
        self.type = entity_type
        self.alive = True

    def get_rect(self) -> pygame.Rect:
        """获取 Pygame 矩形区域（用于渲染和碰撞）"""
        return pygame.Rect(self.pixel_x, self.pixel_y, TILE_SIZE, TILE_SIZE)

    def check_collision(self, other: 'Entity') -> bool:
        """基于网格坐标的快速碰撞检测"""
        return self.grid_x == other.grid_x and self.grid_y == other.grid_y
```

---

## 附录：元素速查表

| 元素 | 标识 | 交互类型 | 效果 |
|------|------|----------|------|
| 金币 | `COIN` | Step-on | coins += 1 |
| 红/绿/蓝钥匙 | `KEY_COLOR` | Step-on | keys.{color} += 1 |
| 出口钥匙 | `KEY_EXIT` | Step-on | keys.exit += 1 |
| 红心 | `HEART` | Step-on | currentHearts += 1 (max) |
| 护盾 | `SHIELD` | Step-on | currentShield += 1 (max) |
| 铁锹 | `SHOVEL` | Step-on | shovels += 1 |
| 地图碎片 | `MAP` | Step-on | 揭示区域 |
| 炸药 | `DYNAMITE` | Step-on | dynamite += 1 |
| 不可破坏墙 | `WALL_INDESTRUCTIBLE` | 阻挡 | 无法通过 |
| 泥墙 | `WALL_DIRT` | Adjacent | 消耗 Shovel → 揭开 |
| 红/绿/蓝锁门 | `GATE_COLOR` | Adjacent | 消耗 Key → 揭开 |
| 出口门 | `GATE_EXIT` | Adjacent | 消耗 Exit Key → 通关 |

---

*文档版本: v1.0 | 创建日期: 2026-06-25 | 依赖: docs/01_core_gameplay.md, docs/02_hearts_and_shields.md*
