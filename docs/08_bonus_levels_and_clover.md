# 第 8 课：地下秘道、隐藏奖励关与幸运四叶草双倍收益机制规范设计

> 本文档定义 Microsoft Treasure Hunt 复刻项目中的**地下秘道生成系统 (Secret Stairs Spawning System)**、**隐藏奖励关运行机制 (Bonus Level Gameplay Rules)**、**幸运四叶草双倍收益 Buff (Lucky Clover Double Benefit)** 以及**主关卡挂起/恢复场景管理器 (Level Suspension State Machine)**。本文档与 `01_core_gameplay.md`（场景切换）、`04_tools_and_economy.md`（金币/宝石/宝箱收集）、`05_mummy_shop_and_amulet.md`（商店关卡判定）、`06_map_generation.md`（泥土瓦片分布）配合使用，构成完整的奖励关卡交互契约。所有后续课程应严格遵循本文档所定义的契约。

---

## 目录

1. [地下秘道生成与进入规则 (Secret Stairs Spawning & Entrance)](#1-地下秘道生成与进入规则-secret-stairs-spawning--entrance)
2. [隐藏奖励关运行机制 (Bonus Level Gameplay Rules)](#2-隐藏奖励关运行机制-bonus-level-gameplay-rules)
3. [双重机制加成：满血治疗与幸运四叶草 (Double Benefit System)](#3-双重机制加成满血治疗与幸运四叶草-double-benefit-system)
4. [主关卡现场挂起与恢复场景管理器 (Level Suspension State Machine)](#4-主关卡现场挂起与恢复场景管理器-level-suspension-state-machine)
5. [逻辑伪代码与系统接口 (API & Logic Pseudo-code)](#5-逻辑伪代码与系统接口-api--logic-pseudo-code)

---

## 1. 地下秘道生成与进入规则 (Secret Stairs Spawning & Entrance)

### 1.1 生成概率与条件

地下秘道楼梯 (Secret Stairs) 的生成遵循以下规则：

| 属性 | 值 | 说明 |
|------|-----|------|
| 生成时机 | 地图初始化阶段 | 与地图生成同步进行 |
| 生成条件 | **非商店关卡** | 商店关卡（参见 `05_mummy_shop_and_amulet.md`）不生成秘道 |
| 生成位置 | 泥土 (Dirt) 瓦片下 | 随机选择一个 Dirt 瓦片 |
| 生成概率 | 5%–10% | 随关卡递增，Level 1 约 5%，Level 20+ 约 10% |
| 每关上限 | 1 个 | 每个非商店关卡至多生成 1 个秘道 |

### 1.2 隐蔽与显露机制

#### 1.2.1 隐蔽状态

- 秘道楼梯在地图生成时被**埋藏在 Dirt 瓦片下方**。
- 玩家无法直接看到秘道存在，与普通 Dirt 瓦片视觉一致。
- 系统内部标记该 Dirt 瓦片的 `hiddenEntity = 'secret_stairs'`。

#### 1.2.2 显露触发

- 当玩家使用铁锹**挖开该 Dirt 瓦片**时：
  1. Dirt 瓦片状态由 `covered` 变为 `revealed`。
  2. 系统检测到 `hiddenEntity === 'secret_stairs'`。
  3. 瓦片视觉切换为**显露的楼梯精灵**（向下延伸的阶梯动画）。
  4. 瓦片实体标记为 `secret_stairs_revealed`。

### 1.3 进入奖励关触发

#### 1.3.1 Step-on 触发

- 玩家**移动到已显露的楼梯格**时，系统触发进入判定。
- 触发方式：玩家主动走向楼梯格（点击或自动寻路）。

#### 1.3.2 进入确认

- **方案 A（自动进入）**：玩家踏上楼梯格后，立即自动切换场景，无需确认弹窗。
- **方案 B（弹窗确认）**：玩家踏上楼梯格后，弹出确认对话框："你发现了一条地下秘道！是否进入隐藏奖励关？" 玩家点击确认后切换。

**推荐方案**：方案 A（自动进入），减少操作摩擦，提升流畅度。

#### 1.3.3 进入流程

1. 玩家踏上楼梯格。
2. 系统调用 `enterBonusLevel()`（详见 §5.1）。
3. 主关卡状态被序列化挂起。
4. 加载奖励关独立地图。
5. 执行瞬间满血治疗（详见 §3.1）。
6. 启动 30 秒倒计时。

### 1.4 伪代码

```typescript
function onDirtRevealed(tile: Tile): void {
  if (tile.hiddenEntity === 'secret_stairs') {
    tile.entity = { type: 'secret_stairs', isRevealed: true };
    tile.visual = 'stairs_sprite';
  }
}

function onPlayerStepOnStairs(player: Player, tile: Tile): void {
  if (tile.entity?.type === 'secret_stairs' && tile.entity.isRevealed) {
    enterBonusLevel(player, tile);
  }
}
```

---

## 2. 隐藏奖励关运行机制 (Bonus Level Gameplay Rules)

### 2.1 奖励关地图结构

| 属性 | 值 | 说明 |
|------|-----|------|
| 地图尺寸 | 8×8 或 10×10 | 比主关卡小，紧凑密集 |
| 地形构成 | 100% Dirt 瓦片 | 全部为可挖掘的泥土 |
| 金币密度 | 高 | 约 60% Dirt 下藏有金币/宝石/宝箱 |
| 陷阱密度 | 低 | 约 10%–15% Dirt 下藏有陷阱 |
| 怪物 | 无 | 奖励关不生成怪物 |
| 出口 | 无 | 无法通过行走离开，仅靠倒计时或陷阱退出 |

### 2.2 时限设定 (Countdown Timer)

| 属性 | 值 | 说明 |
|------|-----|------|
| 倒计时时长 | 30 秒 | 进入奖励关即刻启动 |
| 显示方式 | 屏幕顶部大字倒计时 | 最后 5 秒变红闪烁 |
| 时间到行为 | 立即结算并退回主关卡 | 触发 `exitBonusLevel()` |

### 2.3 金币狂欢与陷阱隐患

#### 2.3.1 金币/宝石/宝箱分布

- **金币 (Gold)**：单个 Dirt 下 1–5 枚金币。
- **宝石 (Gem)**：稀有掉落，单个 Dirt 下 1 颗，价值 10 金币。
- **宝箱 (Treasure Chest)**：极稀有，单个 Dirt 下 1 个，价值 25–50 金币。

#### 2.3.2 陷阱分布

- 陷阱随机生成于部分 Dirt 瓦片下（约 10%–15%）。
- 陷阱类型与主关卡一致（参见 `03_interactive_elements.md`）。
- 陷阱在奖励关中**不造成伤害**，但会立即结束奖励关。

### 2.4 无伤强退判定

#### 2.4.1 触发条件

- 玩家在奖励关中**挖出并踩中陷阱**（Trap）。

#### 2.4.2 判定结果

| 项目 | 结果 | 说明 |
|------|------|------|
| 主关卡血量 | **不扣** | 不扣除当前红心或护盾 |
| 奖励关状态 | **立即结束** | 倒计时强制归零 |
| 已收集奖励 | **保留** | 已挖出的金币/宝石/宝箱全部计入 |
| 玩家位置 | **强制传送** | 退回主关卡楼梯位置 |
| 视觉反馈 | 屏幕震动 + "秘道坍塌！" 提示 | 提示玩家已安全返回 |

#### 2.4.3 设计意图

- 奖励关是**纯收益场景**，陷阱仅作为"强制退出"机制，不惩罚玩家。
- 鼓励玩家快速挖掘，同时增加紧张感。

### 2.5 正常结束判定

#### 2.5.1 触发条件

- 倒计时自然归零（30 秒耗尽）。

#### 2.5.2 判定结果

| 项目 | 结果 | 说明 |
|------|------|------|
| 已收集奖励 | **保留** | 全部计入 |
| 玩家位置 | **强制传送** | 退回主关卡楼梯位置 |
| 视觉反馈 | 倒计时归零动画 + "时间到！" 提示 | 提示奖励关结束 |

### 2.6 伪代码

```typescript
function onBonusLevelTick(bonusState: BonusLevelState): void {
  bonusState.remainingTime -= 1;

  if (bonusState.remainingTime <= 0) {
    exitBonusLevel('timeout');
  }
}

function onBonusTrapTriggered(player: Player, tile: Tile): void {
  // 不扣血！
  // 立即结束奖励关
  exitBonusLevel('trap_triggered');
}

function exitBonusLevel(reason: 'timeout' | 'trap_triggered'): void {
  const collectedGold = calculateCollectedGold();

  // 恢复主关卡
  resumeMainLevel();

  // 合并金币
  mainLevel.player.gold += collectedGold;

  // 设置四叶草 Buff
  mainLevel.player.luckyClover = true;

  // 放置玩家到楼梯位置
  mainLevel.player.tile = mainLevel.secretStairsTile;

  // 提示
  showMessage(reason === 'timeout' ? '时间到！' : '秘道坍塌！');
}
```

---

## 3. 双重机制加成：满血治疗与幸运四叶草 (Double Benefit System)

### 3.1 瞬间满血恢复 (Instant Full Heal)

#### 3.1.1 触发时机

- 在玩家**踏入奖励关的一瞬间**（场景切换完成后、倒计时开始前）。

#### 3.1.2 执行逻辑

```typescript
function applyInstantFullHeal(player: Player): void {
  player.currentHearts = player.maxHearts;
}
```

#### 3.1.3 设计意图

- 奖励关是"纯收益"场景，满血治疗作为额外奖励。
- 玩家在进入奖励关后**立即恢复满血**，无需消耗任何道具。
- 此治疗**不影响主关卡血量**（主关卡血量在挂起时保持不变）。

### 3.2 幸运四叶草 Buff (Lucky Clover Power-up)

#### 3.2.1 获取时机

- 当奖励关结束、玩家**回到主关卡**时，系统赋予 `luckyClover = true` 状态。

#### 3.2.2 翻倍增益规则

| 收集物 | 基础值 | 四叶草加成后 |
|--------|--------|-------------|
| 金币 (Gold) | +N 金币 | +2N 金币 |
| 宝石 (Gem) | +10 金币 | +20 金币 |
| 宝箱 (Treasure Chest) | +25~50 金币 | +50~100 金币 |

**公式**：`actualValue = baseValue * (player.luckyClover ? 2 : 1)`

#### 3.2.3 销毁时机

| 事件 | 四叶草状态 | 说明 |
|------|-----------|------|
| 回到主关卡 | `true` | 激活状态 |
| 收集金币/宝石/宝箱 | `true` | 持续生效 |
| **踏入终点传送门通关** | **`false`** | **强制移除，不跨关** |
| 进入下一关 | `false` | 已失效 |

#### 3.2.4 视觉指示

- 玩家头顶显示**四叶草图标**（绿色）。
- 金币收集时显示 **"×2"** 浮动文字。
- 四叶草 Buff 在通关后立即消失。

### 3.3 伪代码

```typescript
function applyLuckyClover(player: Player): void {
  player.luckyClover = true;
  showCloverIcon(player);
}

function collectGoldWithMultiplier(player: Player, baseValue: number): void {
  const multiplier = player.luckyClover ? 2 : 1;
  const actualValue = baseValue * multiplier;

  player.gold += actualValue;

  if (player.luckyClover) {
    showFloatingText(`×2 (+${actualValue})`);
  }
}

function onPlayerReachExitPortal(player: Player): void {
  // 通关时强制移除四叶草
  player.luckyClover = false;
  hideCloverIcon(player);

  // 进入下一关
  advanceToNextLevel(player);
}
```

---

## 4. 主关卡现场挂起与恢复场景管理器 (Level Suspension State Machine)

### 4.1 挂起逻辑 (Level Suspension)

#### 4.1.1 触发时机

- 玩家踏上已显露的楼梯格时，`enterBonusLevel()` 被调用。

#### 4.1.2 序列化内容

系统必须将主关卡的以下状态完整保存至 `SuspendedLevelState`：

| 状态项 | 说明 |
|--------|------|
| 地图瓦片状态 | 每个瓦片的 `covered/revealed`、`entity`、`hiddenEntity` |
| 怪物状态 | 每个怪物的 `isDead`、位置 |
| 玩家道具 | `arrows`、`hasMachete`、`keys`、`gold`、`shovels`、`dynamite`、`maps` |
| 玩家生命 | `currentHearts`、`maxHearts`、`currentShields`、`maxShields` |
| 已解锁门 | 哪些门已被打开 |
| 楼梯位置 | 玩家进入奖励关时的位置（用于恢复放置） |
| 关卡编号 | 当前关卡号 |

#### 4.1.3 伪代码

```typescript
function suspendMainLevel(mainLevel: Level): SuspendedLevelState {
  return {
    tileStates: mainLevel.tiles.map(row => row.map(tile => ({ ...tile }))),
    monsterStates: mainLevel.monsters.map(m => ({ ...m })),
    playerInventory: { ...mainLevel.player.inventory },
    playerHealth: { ...mainLevel.player.health },
    unlockedDoors: [...mainLevel.unlockedDoors],
    secretStairsTile: { ...mainLevel.secretStairsTile },
    levelNumber: mainLevel.levelNumber,
    timestamp: Date.now(),
  };
}
```

### 4.2 恢复逻辑 (Level Resumption)

#### 4.2.1 触发时机

- 奖励关结束（倒计时归零或陷阱触发）后，`exitBonusLevel()` 被调用。

#### 4.2.2 恢复内容

| 恢复项 | 说明 |
|--------|------|
| 地图瓦片状态 | 从 `SuspendedLevelState.tileStates` 恢复 |
| 怪物状态 | 从 `SuspendedLevelState.monsterStates` 恢复 |
| 玩家道具 | 合并：主关卡道具 + 奖励关新获得的金币 |
| 玩家生命 | 恢复主关卡血量（不保留奖励关的满血状态） |
| 已解锁门 | 从 `SuspendedLevelState.unlockedDoors` 恢复 |
| 玩家位置 | 放置到楼梯格位置 |
| 四叶草 Buff | 设置为 `true` |

#### 4.2.3 伪代码

```typescript
function resumeMainLevel(suspendedState: SuspendedLevelState, bonusGold: number): Level {
  const level = loadLevel(suspendedState.levelNumber);

  // 恢复瓦片状态
  level.tiles = suspendedState.tileStates;

  // 恢复怪物状态
  level.monsters = suspendedState.monsterStates;

  // 恢复道具（合并金币）
  level.player.inventory = suspendedState.playerInventory;
  level.player.gold += bonusGold;

  // 恢复生命
  level.player.health = suspendedState.playerHealth;

  // 恢复门状态
  level.unlockedDoors = suspendedState.unlockedDoors;

  // 放置玩家到楼梯位置
  level.player.tile = suspendedState.secretStairsTile;

  // 设置四叶草
  level.player.luckyClover = true;

  return level;
}
```

### 4.3 状态机流程图

```
主关卡运行中
     │
     ▼
玩家踏上楼梯格
     │
     ▼
┌──────────────────────┐
│  suspendMainLevel()  │
│  序列化主关卡状态     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  applyInstantFullHeal()│
│  瞬间满血治疗         │
└──────────┬───────────┘
           │
           ┌──────────────────────┐
           │   奖励关运行中        │
           │  (30秒倒计时)         │
           │  玩家挖掘金币/陷阱    │
           └──────────┬───────────┘
                  │   │
          超时   │   │  踩陷阱
        ┌──────┘   └──────┐
        ▼                 ▼
   结算金币           结算金币
        │                 │
        └────────┬────────┘
                 │
                 ▼
┌──────────────────────┐
│  exitBonusLevel()    │
│  恢复主关卡           │
│  合并金币 + 四叶草 Buff│
└──────────────────────┘
                 │
                 ▼
         主关卡继续运行
       (玩家位于楼梯格)
                 │
                 ▼
        玩家到达出口传送门
                 │
                 ▼
        四叶草 Buff 销毁
        进入下一关
```

---

## 5. 逻辑伪代码与系统接口 (API & Logic Pseudo-code)

### 5.1 场景管理器切换方法

#### 5.1.1 `enterBonusLevel()`

```typescript
function enterBonusLevel(player: Player, stairsTile: Tile): void {
  // 1. 序列化主关卡
  const suspendedState = suspendMainLevel(currentLevel);

  // 2. 切换到奖励关场景
  gameScene.transitionTo('bonus_level');

  // 3. 加载奖励关地图
  const bonusMap = generateBonusMap(8, 8); // 8x8 Dirt 地图
  bonusMap.populateGold(0.6);   // 60% 金币密度
  bonusMap.populateTraps(0.12); // 12% 陷阱密度

  // 4. 放置玩家到奖励关起点
  bonusMap.player.startTile = { x: 0, y: 0 };

  // 5. 瞬间满血治疗
  applyInstantFullHeal(player);

  // 6. 启动倒计时
  bonusMap.remainingTime = 30;
  bonusMap.timer = startCountdown(30, onBonusLevelTimeout);

  // 7. 保存挂起状态到全局
  gameSession.suspendedLevel = suspendedState;
}
```

#### 5.1.2 `exitBonusLevel()`

```typescript
function exitBonusLevel(reason: 'timeout' | 'trap_triggered'): void {
  const bonusMap = getCurrentBonusMap();
  const collectedGold = bonusMap.collectedGold;

  // 1. 停止倒计时
  stopCountdown(bonusMap.timer);

  // 2. 切换到主关卡场景
  gameScene.transitionTo('main_level');

  // 3. 恢复主关卡
  const suspendedState = gameSession.suspendedLevel;
  currentLevel = resumeMainLevel(suspendedState, collectedGold);

  // 4. 设置四叶草 Buff
  applyLuckyClover(currentLevel.player);

  // 5. 提示
  showMessage(reason === 'timeout' ? '时间到！' : '秘道坍塌，安全返回！');

  // 6. 清理挂起状态
  gameSession.suspendedLevel = null;
}
```

### 5.2 金币收集函数

```typescript
function collectGoldWithMultiplier(player: Player, baseValue: number): void {
  const multiplier = player.luckyClover ? 2 : 1;
  const actualValue = baseValue * multiplier;

  player.gold += actualValue;

  // 视觉反馈
  if (player.luckyClover) {
    showFloatingText({
      text: `×2 (+${actualValue})`,
      color: '#FFD700',
      position: player.tile,
    });
  }

  // 记录到关卡统计
  currentLevel.collectedGold += actualValue;
}
```

### 5.3 TypeScript 接口定义

```typescript
// 奖励关状态接口
interface BonusLevelState {
  id: string;
  map: Tile[][];              // 奖励关地图（8x8 Dirt）
  remainingTime: number;      // 剩余时间（秒）
  timer: Timer | null;        // 倒计时器
  collectedGold: number;      // 已收集金币总数
  collectedGems: number;      // 已收集宝石总数
  collectedChests: number;    // 已收集宝箱总数
  trapTiles: Set<string>;     // 陷阱格坐标集合
  exitReason: 'timeout' | 'trap_triggered' | null;
}

// 挂起关卡状态接口
interface SuspendedLevelState {
  tileStates: TileState[][];         // 瓦片状态快照
  monsterStates: MonsterSnapshot[];  // 怪物状态快照
  playerInventory: PlayerInventory;   // 玩家道具快照
  playerHealth: PlayerHealth;         // 玩家生命快照
  unlockedDoors: string[];            // 已解锁门的 ID 列表
  secretStairsTile: { x: number; y: number }; // 楼梯位置
  levelNumber: number;                // 关卡编号
  timestamp: number;                  // 挂起时间戳
}

// 四叶草 Buff 载荷接口
interface LuckyCloverPayload {
  isActive: boolean;          // 是否激活
  multiplier: number;         // 倍率（固定 2）
  sourceLevel: number;        // 来源关卡
  activatedAt: number;        // 激活时间戳
  expiresOnExit: boolean;     // 是否在通关时销毁（固定 true）
}

// 玩家完整状态扩展（含四叶草）
interface PlayerWithClover extends PlayerState {
  luckyClover: boolean;
}

// 场景管理器接口
interface SceneManager {
  currentScene: 'main_level' | 'bonus_level' | 'shop';
  transitionTo(scene: SceneManager['currentScene']): void;
  getCurrentScene(): SceneManager['currentScene'];
}

// 游戏会话接口
interface GameSession {
  currentLevel: Level | null;
  bonusLevel: BonusLevelState | null;
  suspendedLevel: SuspendedLevelState | null;
  sceneManager: SceneManager;
}
```

---

## 附录 A：与其他文档的契约关系

| 关联文档 | 关联点 |
|---------|--------|
| `01_core_gameplay.md` | 场景切换、终点传送门判定、移动系统 |
| `02_hearts_and_shields.md` | 满血治疗与血量恢复规则 |
| `03_interactive_elements.md` | 陷阱类型定义、Dirt 瓦片交互 |
| `04_tools_and_economy.md` | 金币/宝石/宝箱收集规则、铁锹挖掘 |
| `05_mummy_shop_and_amulet.md` | 商店关卡判定（秘道不在商店关生成） |
| `06_map_generation.md` | Dirt 瓦片分布、地图初始化阶段 |
| `07_monsters_and_weapons.md` | 怪物状态序列化（挂起时保存） |

## 附录 B：关键常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `SECRET_STAIRS_MIN_CHANCE` | 0.05 | Level 1 秘道生成概率 |
| `SECRET_STAIRS_MAX_CHANCE` | 0.10 | Level 20+ 秘道生成概率 |
| `MAX_SECRET_STAIRS_PER_LEVEL` | 1 | 每关最多秘道数 |
| `BONUS_LEVEL_WIDTH` | 8 | 奖励关地图宽度 |
| `BONUS_LEVEL_HEIGHT` | 8 | 奖励关地图高度 |
| `BONUS_LEVEL_TIMEOUT` | 30 | 奖励关倒计时（秒） |
| `BONUS_GOLD_DENSITY` | 0.60 | 金币生成密度 |
| `BONUS_TRAP_DENSITY` | 0.12 | 陷阱生成密度 |
| `LUCKY_CLOVER_MULTIPLIER` | 2 | 四叶草金币倍率 |
