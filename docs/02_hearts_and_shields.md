# 第 2 课：红心、护盾与伤害机制规范设计

> 本文档是《Microsoft Treasure Hunt》复刻项目中生命值、护盾与伤害判定系统的权威规范。它扩展了 `01_core_gameplay.md` 第 4 节中的基础描述，定义了完整的数值体系、伤害流程、回复机制、永久升级以及 Game Over 状态机。所有后续课程应严格遵循本文档所定义的契约。

---

## 目录

1. [数值定义与基础属性 (Base Attributes)](#1-数值定义与基础属性-base-attributes)
2. [伤害判定与扣减优先级 (Damage Calculation & Priority)](#2-伤害判定与扣减优先级-damage-calculation--priority)
3. [回复、获取与上限升级 (Recovery & Upgrades)](#3-回复获取与上限升级-recovery--upgrades)
4. [游戏结束触发流程 (Game Over Trigger Flow)](#4-游戏结束触发流程-game-over-trigger-flow)

---

## 1. 数值定义与基础属性 (Base Attributes)

### 1.1 红心 (Hearts)

红心代表角色的生命值，是生存的核心指标。

| 属性 | 默认值 | 类型 | 说明 |
|------|--------|------|------|
| `currentHearts` | `3` | `number` | 当前剩余红心数量 |
| `maxHearts` | `3` | `number` | 当前生命上限（可通过升级提升） |
| `hardCapHearts` | `8` | `number` | 红心绝对上限，任何情况下不可突破 |

**约束规则**：
- `0 ≤ currentHearts ≤ maxHearts ≤ hardCapHearts`
- 初始化时 `currentHearts = maxHearts`（满血起步）
- 当 `currentHearts` 降至 `0` 时，触发 Game Over 判定

### 1.2 护盾 (Shields)

护盾作为红心的缓冲层，在红心受损前优先吸收伤害。

| 属性 | 默认值 | 类型 | 说明 |
|------|--------|------|------|
| `currentShield` | `0` | `number` | 当前护盾数量 |
| `maxShield` | `1` | `number` | 当前护盾上限（可通过升级提升） |
| `hardCapShield` | `3` | `number` | 护盾绝对上限，任何情况下不可突破 |

**约束规则**：
- `0 ≤ currentShield ≤ maxShield ≤ hardCapShield`
- 初始状态无护盾，需通过道具或升级获取
- 护盾不具备累积抵消能力——每次受击最多消耗 1 点护盾

### 1.3 数据结构定义

```typescript
interface VitalStats {
  // 红心
  currentHearts: number;
  maxHearts: number;
  hardCapHearts: number;

  // 护盾
  currentShield: number;
  maxShield: number;
  hardCapShield: number;
}

// 默认初始值
const DEFAULT_VITAL_STATS: VitalStats = {
  currentHearts: 3,
  maxHearts: 3,
  hardCapHearts: 8,

  currentShield: 0,
  maxShield: 1,
  hardCapShield: 3,
};
```

---

## 2. 伤害判定与扣减优先级 (Damage Calculation & Priority)

### 2.1 伤害来源

在游戏中，角色可能受到以下来源的伤害：

| 伤害来源 | 触发条件 | 单次伤害值 |
|----------|----------|-----------|
| 陷阱 (Trap) | 挖掘到隐藏的陷阱格 | 1 |
| 怪物 (Monster) | 与怪物接触（后续课程定义） | 1 |
| 环境伤害 (Environment) | 特定关卡机制（如落石、岩浆） | 1 |

> **设计原则**：单次伤害值统一为 1 点，保持逻辑简洁。未来可通过扩展 `DamageEvent` 支持多点点数。

### 2.2 扣减优先级

当角色受到伤害时，按以下优先级扣除：

```
优先级：护盾 > 红心
```

**逻辑流程**：

```
FUNCTION applyDamage(amount: number = 1):
    IF isInvulnerable THEN
        RETURN  // 处于无敌状态，忽略伤害
    END IF

    remainingDamage = amount

    // 第一步：优先扣除护盾
    IF currentShield > 0 THEN
        shieldLoss = min(remainingDamage, currentShield)
        currentShield -= shieldLoss
        remainingDamage -= shieldLoss
        triggerShieldBreakEffect(shieldLoss)
    END IF

    // 第二步：护盾耗尽，扣除红心
    IF remainingDamage > 0 THEN
        currentHearts -= remainingDamage
        triggerHeartLossEffect(remainingDamage)
    END IF

    // 第三步：进入无敌窗口
    enterInvulnerability(INVULNERABILITY_DURATION)

    // 第四步：死亡判定
    IF currentHearts <= 0 THEN
        triggerDeath()
    END IF
END FUNCTION
```

### 2.3 无敌时间 (Invulnerability Window)

角色在受到伤害后进入短暂的无敌状态，避免在同一触发事件中重复受伤。

| 参数 | 值 | 说明 |
|------|-----|------|
| `INVULNERABILITY_DURATION` | `1500ms` | 受伤后的无敌持续时间 |
| 视觉反馈 | 角色闪烁 (Blink) | 以 100ms 间隔切换可见性 |
| 控制反馈 | 操作输入正常接收 | 玩家可正常移动/挖掘 |

**状态机**：

```
[VULNERABLE] --(受伤)--> [INVULNERABLE] --(1500ms 结束)--> [VULNERABLE]
      ↑                                                          |
      └──────────────────────────────────────────────────────────┘
```

### 2.4 受伤反馈 (Feedback Hooks)

| 事件 | 视觉反馈 | 音频反馈 |
|------|----------|----------|
| 护盾破碎 | 护盾图标碎裂动画 + 蓝色粒子 | 玻璃破碎音效 |
| 红心损失 | 红心图标闪烁消失 + 屏幕边缘红色脉冲 | 心跳/受伤音效 |
| 角色闪烁 | 受伤后 1500ms 内以 100ms 间隔闪烁 | — |

```typescript
// 反馈事件类型
interface DamageFeedback {
  type: 'SHIELD_BREAK' | 'HEART_LOSS';
  amount: number;
  remainingHearts: number;
  remainingShield: number;
}
```

---

## 3. 回复、获取与上限升级 (Recovery & Upgrades)

### 3.1 消耗性回复道具

#### 3.1.1 红心道具 (Heart Pickup)

| 属性 | 值 |
|------|-----|
| 效果 | `currentHearts += 1` |
| 约束 | 不能超过 `maxHearts` |
| 获取方式 | 地图掉落、怪物掉落、宝箱 |
| 视觉标识 | 红色心形图标 |

```
FUNCTION onHeartPickup():
    IF currentHearts < maxHearts THEN
        currentHearts += 1
        triggerHeartGainEffect()
        RETURN true  // 拾取成功
    ELSE
        RETURN false // 满血，拾取无效
    END IF
END FUNCTION
```

#### 3.1.2 护盾道具 (Shield Pickup)

| 属性 | 值 |
|------|-----|
| 效果 | `currentShield += 1` |
| 约束 | 不能超过 `maxShield` |
| 获取方式 | 地图掉落、商店购买 |
| 视觉标识 | 蓝色盾牌图标 |

```
FUNCTION onShieldPickup():
    IF currentShield < maxShield THEN
        currentShield += 1
        triggerShieldGainEffect()
        RETURN true
    ELSE
        RETURN false // 护盾已满，拾取无效
    END IF
END FUNCTION
```

### 3.2 永久属性升级 (Permanent Upgrades)

永久升级在游戏外商店（Meta Shop）中购买，对当前及后续关卡生效。

#### 3.2.1 红心上限 +1

| 升级项 | 效果 |
|--------|------|
| `maxHearts += 1` | 提升生命上限 |
| `currentHearts += 1` | 同时恢复 1 点红心（升级即治疗） |
| 约束 | 新 `maxHearts` 不能超过 `hardCapHearts (8)` |

```
FUNCTION upgradeMaxHearts():
    IF maxHearts >= hardCapHearts THEN
        RETURN false // 已达绝对上限
    END IF
    maxHearts += 1
    currentHearts += 1
    RETURN true
END FUNCTION
```

#### 3.2.2 护盾上限 +1

| 升级项 | 效果 |
|--------|------|
| `maxShield += 1` | 提升护盾上限 |
| `currentShield += 1` | 同时获得 1 点护盾（升级即装备） |
| 约束 | 新 `maxShield` 不能超过 `hardCapShield (3)` |

```
FUNCTION upgradeMaxShield():
    IF maxShield >= hardCapShield THEN
        RETURN false // 已达绝对上限
    END IF
    maxShield += 1
    currentShield += 1
    RETURN true
END FUNCTION
```

#### 3.2.3 升级价格参考（设计提示）

| 升级等级 | 红心上限价格 | 护盾上限价格 |
|----------|-------------|-------------|
| Lv 1 → Lv 2 | 100 金币 | 150 金币 |
| Lv 2 → Lv 3 | 200 金币 | 300 金币 |
| Lv 3 → Lv 4 | 400 金币 | 500 金币 |
| Lv 4 → Lv 5 | 800 金币 | — (已达护盾上限) |
| Lv 5 → Lv 6 | 1200 金币 | — |
| Lv 6 → Lv 7 | 1800 金币 | — |
| Lv 7 → Lv 8 | 2500 金币 | — |

> 具体数值由经济系统课程最终确定，此处仅为参考框架。

---

## 4. 游戏结束触发流程 (Game Over Trigger Flow)

### 4.1 死亡判定时间点

死亡判定在伤害处理流程的**最后一步**执行，确保扣血动画与反馈效果完整播放：

```
[伤害触发] → [扣减护盾/红心] → [播放反馈动画] → [进入无敌状态] → [检测红心 ≤ 0] → [触发死亡]
```

> **关键规则**：死亡判定不在扣血瞬间立即执行，而是在反馈动画播放完毕后执行，确保玩家能看到自己失去了最后一点生命值。

### 4.2 状态机转换

```
PLAYING ──(触发死亡)──> DEATH_ANIMATION ──(动画结束)──> GAME_OVER
                          │
                          ├─ 冻结所有输入
                          ├─ 冻结所有游戏逻辑
                          ├─ 播放死亡动画 (1000ms)
                          └─ 显示 Game Over 界面
```

```typescript
// 状态转换触发
function triggerDeath(): void {
    gameState = GameState.DEATH_ANIMATION;
    freezeAllInput();
    freezeAllGameLogic();
    playDeathAnimation(() => {
        // 动画结束回调
        gameState = GameState.GAME_OVER;
        showGameOverScreen(buildDeathScreenData());
    });
}
```

### 4.3 场景冻结清单

进入 `DEATH_ANIMATION` 状态时，以下系统立即冻结：

| 系统 | 冻结行为 |
|------|----------|
| 玩家输入 | 忽略所有移动/挖掘/交互指令 |
| 游戏时间 | 暂停游戏计时器 |
| 动画系统 | 停止关卡环境动画，仅播放死亡动画 |
| 音频系统 | 停止环境音效，播放死亡音效 |
| AI/怪物 | 停止所有怪物行为（后续课程生效） |
| 物理系统 | 停止所有物理模拟 |

### 4.4 死亡界面数据载荷

Game Over 界面需要展示以下数据：

```typescript
interface DeathScreenData {
  levelId: string;           // 当前关卡 ID
  stepsTaken: number;        // 本关步数
  timeElapsed: number;       // 用时（秒）
  trapsTriggered: number;    // 触发陷阱次数
  heartsRemaining: number;   // 死亡时剩余红心（通常为 0）
  shieldsRemaining: number;  // 死亡时剩余护盾
  keyObtained: boolean;      // 是否已获得钥匙
  exitReached: boolean;      // 是否曾到达出口附近
}
```

### 4.5 死亡界面选项

Game Over 界面提供以下操作：

| 选项 | 效果 |
|------|------|
| 重新开始 (Restart) | 重置当前关卡，恢复初始 `VitalStats` |
| 返回主菜单 (Main Menu) | 返回主界面，保留永久升级进度 |

---

## 附录：完整 TypeScript 接口汇总

```typescript
// 核心生命统计
interface VitalStats {
  currentHearts: number;
  maxHearts: number;
  hardCapHearts: number;
  currentShield: number;
  maxShield: number;
  hardCapShield: number;
}

// 伤害事件
interface DamageEvent {
  source: 'TRAP' | 'MONSTER' | 'ENVIRONMENT';
  amount: number;
  position?: TilePosition;  // 伤害来源位置（可选）
}

// 死亡界面数据
interface DeathScreenData {
  levelId: string;
  stepsTaken: number;
  timeElapsed: number;
  trapsTriggered: number;
  heartsRemaining: number;
  shieldsRemaining: number;
  keyObtained: boolean;
  exitReached: boolean;
}

// 游戏状态枚举（扩展）
enum GameState {
  INIT = 'INIT',
  PLAYING = 'PLAYING',
  DEATH_ANIMATION = 'DEATH_ANIMATION',
  LEVEL_COMPLETE = 'LEVEL_COMPLETE',
  GAME_OVER = 'GAME_OVER'
}

// 默认值常量
const DEFAULT_VITAL_STATS: VitalStats = {
  currentHearts: 3,
  maxHearts: 3,
  hardCapHearts: 8,
  currentShield: 0,
  maxShield: 1,
  hardCapShield: 3,
};

const INVULNERABILITY_DURATION_MS = 1500;
const DEATH_ANIMATION_DURATION_MS = 1000;
const BLINK_INTERVAL_MS = 100;
```

---

*文档版本: v1.0 | 创建日期: 2026-06-25 | 依赖: docs/01_core_gameplay.md*
