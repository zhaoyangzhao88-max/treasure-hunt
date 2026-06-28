# 第 9 课：全局 UI 布局、摄像机视口裁剪与多屏幕管理器设计规范

> 本文档定义 Microsoft Treasure Hunt 复刻项目中的**全局 UI 屏幕分区与 HUD 像素布局 (Screen Partition & HUD Layout)**、**摄像机平滑定位与边界钳制算法 (Camera Scroll & Boundary Clamping)**、**鼠标点击坐标逆向映射 (Screen-to-Grid Coordinate Transformation)** 以及**多屏幕管理器状态机 (Multi-Screen State Machine)**。本文档与 `01_core_gameplay.md`（游戏主循环、瓦片大小）、`02_hearts_and_shields.md`（红心/护盾 HUD）、`04_tools_and_economy.md`（金币/工具计数器）、`05_mummy_shop_and_amulet.md`（商店界面）、`07_monsters_and_weapons.md`（武器槽位）、`08_bonus_levels_and_clover.md`（四叶草 Buff、奖励关切换）配合使用，构成完整的前端渲染与交互架构契约。所有后续课程应严格遵循本文档所定义的契约。

---

## 目录

1. [屏幕物理分区与 HUD 像素布局 (Screen Partition & HUD Layout)](#1-屏幕物理分区与-hud-像素布局-screen-partition--hud-layout)
2. [摄像机平滑定位与边界钳制算法 (Camera Scroll & Boundary Clamping)](#2-摄像机平滑定位与边界钳制算法-camera-scroll--boundary-clamping)
3. [鼠标点击坐标逆向映射逻辑 (Screen-to-Grid Coordinate Transformation)](#3-鼠标点击坐标逆向映射逻辑-screen-to-grid-coordinate-transformation)
4. [多屏幕管理器状态机 (Multi-Screen State Machine)](#4-多屏幕管理器状态机-multi-screen-state-machine)
5. [系统类接口与算法伪代码 (API & Logic Pseudo-code)](#5-系统类接口与算法伪代码-api--logic-pseudo-code)

---

## 1. 屏幕物理分区与 HUD 像素布局 (Screen Partition & HUD Layout)

### 1.1 分辨率规范 (Resolution Specification)

| 属性 | 值 | 说明 |
|------|-----|------|
| 主分辨率 | **1024 × 768** | 固定设计分辨率，运行时缩放适配 |
| 宽高比 | 4:3 | 标准复古比例 |
| 瓦片大小 | **32 × 32 像素** | 基础瓦片单元（大尺寸模式可选 48×48） |
| HUD 高度 | **96 像素** | 屏幕顶部状态栏 |
| 游戏渲染区高度 | **672 像素** | 768 − 96 = 672 |

### 1.2 屏幕分区示意

```
┌─────────────────────────────────────────────────────────────┐
│                    HUD 状态栏 (Y: 0 – 96)                    │
│  [♥♥♥♥] [🛡🛡] [💰 125] [⛏ 3] [💣 2] [🗺 1] [🔑 2] [🏹 5] [🔪] [🍀] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                                                             │
│               游戏渲染区 (Y: 96 – 768)                       │
│               视口跟随玩家移动                               │
│               仅渲染可见瓦片                                 │
│                                                             │
│                                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 HUD 状态栏组件布局

#### 1.3.1 水平排布次序（从左到右）

| 序号 | 组件 | 像素宽度 | 对齐 | 数据源 |
|------|------|---------|------|--------|
| 1 | 红心槽 (Hearts) | 120px | 左对齐 | `currentHearts / maxHearts` |
| 2 | 护盾槽 (Shields) | 80px | 左对齐 | `currentShields / maxShields` |
| 3 | 金币计数器 (Gold) | 90px | 左对齐 | `gold` |
| 4 | 铁锹计数器 (Shovels) | 60px | 左对齐 | `shovels` |
| 5 | 炸药计数器 (Dynamite) | 60px | 左对齐 | `dynamite` |
| 6 | 地图计数器 (Maps) | 60px | 左对齐 | `maps` |
| 7 | 钥匙堆 (Keys) | 60px | 左对齐 | `keys` |
| 8 | 弓箭槽 (Arrows) | 60px | 左对齐 | `arrows`（上限 9） |
| 9 | 柴刀槽 (Machete) | 48px | 左对齐 | `hasMachete`（布尔图标） |
| 10 | 四叶草状态 (Clover) | 48px | 左对齐 | `luckyClover`（布尔图标） |

**总宽度估算**：120 + 80 + 90 + 60 + 60 + 60 + 60 + 60 + 48 + 48 = **686 像素**，在 1024 宽度内留有余量。

#### 1.3.2 垂直对齐

- 所有 HUD 组件垂直居中于 HUD 区域（Y: 0–96）。
- 图标上边缘：`Y = 12`，下边缘：`Y = 84`（72 像素高图标区）。
- 文字基线：`Y = 72`（底部对齐）。

#### 1.3.3 组件详细定义

**红心槽 (Hearts)**

| 属性 | 值 |
|------|-----|
| 图标 | 红心 ♥（满血）/ 灰心 ♡（空槽） |
| 尺寸 | 每颗心 24×24 像素 |
| 间距 | 4 像素 |
| 显示规则 | `maxHearts` 颗心，前 `currentHearts` 颗为红色 |

**护盾槽 (Shields)**

| 属性 | 值 |
|------|-----|
| 图标 | 盾牌 🛡（激活）/ 灰盾 ○（空槽） |
| 尺寸 | 每颗盾 24×24 像素 |
| 间距 | 4 像素 |
| 显示规则 | `maxShields` 颗盾，前 `currentShields` 颗为蓝色 |

**金币计数器 (Gold)**

| 属性 | 值 |
|------|-----|
| 图标 | 金币 💰 |
| 格式 | 数字（如 `125`） |
| 字体 | 16px 等宽字体 |
| 颜色 | #FFD700（金色） |

**工具计数器 (Shovels / Dynamite / Maps)**

| 属性 | 值 |
|------|-----|
| 图标 | ⛏ / 💣 / 🗺 |
| 格式 | 数字 |
| 字体 | 14px 等宽字体 |
| 颜色 | #FFFFFF（白色） |

**钥匙堆 (Keys)**

| 属性 | 值 |
|------|-----|
| 图标 | 🔑 |
| 格式 | 数字 |
| 字体 | 14px 等宽字体 |
| 颜色 | #FFA500（橙色） |

**弓箭槽 (Arrows)**

| 属性 | 值 |
|------|-----|
| 图标 | 🏹 |
| 格式 | 数字（如 `5`） |
| 上限 | 9 |
| 字体 | 14px 等宽字体 |
| 颜色 | #90EE90（浅绿） |

**柴刀槽 (Machete)**

| 属性 | 值 |
|------|-----|
| 图标 | 🔪 |
| 显示 | 有柴刀时显示，无时隐藏 |
| 尺寸 | 32×32 像素 |
| 颜色 | #C0C0C0（银色） |

**四叶草状态 (Clover)**

| 属性 | 值 |
|------|-----|
| 图标 | 🍀 |
| 显示 | `luckyClover === true` 时显示，否则隐藏 |
| 尺寸 | 32×32 像素 |
| 颜色 | #00FF00（亮绿） |
| 动画 | 激活时缓慢旋转或脉动 |

### 1.4 游戏渲染区 (Game Viewport Zone)

| 属性 | 值 | 说明 |
|------|-----|------|
| 位置 | Y: 96 – 768 | 屏幕底部区域 |
| 宽度 | 1024 像素 | 全屏宽度 |
| 高度 | 672 像素 | 768 − 96 |
| 瓦片网格 | 32×32 | 每行 32 格（1024/32），每列 21 格（672/32） |
| 渲染范围 | 动态 | 由摄像机视口裁剪决定 |

---

## 2. 摄像机平滑定位与边界钳制算法 (Camera Scroll & Boundary Clamping)

### 2.1 摄像机坐标系定义

| 属性 | 说明 |
|------|------|
| `camera_x` | 摄像机视口左上角在地图中的 X 像素坐标 |
| `camera_y` | 摄像机视口左上角在地图中的 Y 像素坐标 |
| 视口宽度 | 1024 像素（等于屏幕分辨率宽度） |
| 视口高度 | 672 像素（等于游戏渲染区高度） |

### 2.2 随动公式 (Smooth Follow with Lerp)

#### 2.2.1 目标坐标计算

摄像机的目标位置以**玩家角色像素坐标为中心**：

```
target_x = player_pixel_x - viewport_width / 2
target_y = player_pixel_y - viewport_height / 2
```

其中 `player_pixel_x = player.grid_x * TILE_SIZE`，`player_pixel_y = player.grid_y * TILE_SIZE`。

#### 2.2.2 平滑插值 (Lerp)

每帧更新时，摄像机当前位置向目标位置平滑插值：

```
camera_x = lerp(camera_x, target_x, CAMERA_LERP_FACTOR)
camera_y = lerp(camera_y, target_y, CAMERA_LERP_FACTOR)
```

**Lerp 公式**：

```
lerp(current, target, factor) = current + (target - current) * factor
```

| 常量 | 推荐值 | 说明 |
|------|--------|------|
| `CAMERA_LERP_FACTOR` | 0.1 – 0.15 | 越小越平滑，越大越灵敏 |

#### 2.2.3 帧率无关平滑

为确保不同帧率下摄像机行为一致，应使用 **dt 加权**：

```
camera_x = lerp(camera_x, target_x, 1 - exp(-CAMERA_SPEED * dt))
```

其中 `CAMERA_SPEED` 推荐值为 **8–12**（单位：1/秒）。

### 2.3 边界限制 (Boundary Clamping)

#### 2.3.1 边界极限值计算

当玩家接近地图边缘时，摄像机必须被钳制在地图边界内，**不能滑出地图外露出黑色空底**：

```
max_camera_x = map_pixel_width - viewport_width
max_camera_y = map_pixel_height - viewport_height
```

其中：
- `map_pixel_width = map_grid_width * TILE_SIZE`
- `map_pixel_height = map_grid_height * TILE_SIZE`

#### 2.3.2 钳制公式

```
camera_x = clamp(camera_x, 0, max(0, max_camera_x))
camera_y = clamp(camera_y, 0, max(0, max_camera_y))
```

**说明**：
- 当 `map_pixel_width <= viewport_width` 时，地图在水平方向上小于屏幕，摄像机 X 固定为 0（或居中）。
- 当 `map_pixel_height <= viewport_height` 时，地图在垂直方向上小于屏幕，摄像机 Y 固定为 0（或居中）。
- `max(0, ...)` 确保不会出现负的上限值。

#### 2.3.3 钳制优先级

**先钳制，后平滑**（每帧更新顺序）：

1. 计算 `target_x`, `target_y`（玩家中心）
2. 钳制 `target_x`, `target_y` 到合法范围
3. Lerp 平滑插值到钳制后的目标

### 2.4 视口裁剪 (Frustum Culling)

#### 2.4.1 裁剪目的

在渲染循环中，仅绘制当前视口范围内可见的瓦片，避免绘制屏幕外的瓦片，提升渲染效率。

#### 2.4.2 可见瓦片范围计算

```
start_col = floor(camera_x / TILE_SIZE)
end_col   = ceil((camera_x + viewport_width) / TILE_SIZE)
start_row = floor(camera_y / TILE_SIZE)
end_row   = ceil((camera_y + viewport_height) / TILE_SIZE)
```

#### 2.4.3 裁剪边界保护

```
start_col = max(0, start_col)
start_row = max(0, start_row)
end_col   = min(map_grid_width, end_col)
end_row   = min(map_grid_height, end_row)
```

#### 2.4.4 渲染循环伪代码

```python
# Pygame 风格伪代码
def render_tiles(screen, tiles, camera_x, camera_y):
    start_col = max(0, int(camera_x // TILE_SIZE))
    end_col = min(GRID_WIDTH, int((camera_x + VIEWPORT_WIDTH) // TILE_SIZE) + 1)
    start_row = max(0, int(camera_y // TILE_SIZE))
    end_row = min(GRID_HEIGHT, int((camera_y + VIEWPORT_HEIGHT) // TILE_SIZE) + 1)

    for row in range(start_row, end_row):
        for col in range(start_col, end_col):
            tile = tiles[row][col]
            screen_x = col * TILE_SIZE - camera_x
            screen_y = row * TILE_SIZE - camera_y + HUD_HEIGHT  # 加上 HUD 偏移
            screen.blit(tile.sprite, (screen_x, screen_y))
```

---

## 3. 鼠标点击坐标逆向映射逻辑 (Screen-to-Grid Coordinate Transformation)

### 3.1 问题描述

玩家在游戏渲染区内点击鼠标，输入为**屏幕绝对坐标** `(mouse_screen_x, mouse_screen_y)`。需要将其精确转化为**网格坐标** `(grid_x, grid_y)`。

### 3.2 转换公式

#### 3.2.1 步骤分解

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | 扣除 HUD 高度 | `adjusted_y = mouse_screen_y - HUD_HEIGHT` |
| 2 | 检查是否在渲染区 | 若 `adjusted_y < 0`，点击在 HUD 区域，忽略 |
| 3 | 叠加摄像机偏移 | `world_x = mouse_screen_x + camera_x`<br>`world_y = adjusted_y + camera_y` |
| 4 | 除以瓦片大小 | `grid_x = floor(world_x / TILE_SIZE)`<br>`grid_y = floor(world_y / TILE_SIZE)` |
| 5 | 边界检查 | 若 `grid_x` 或 `grid_y` 超出地图范围，忽略 |

#### 3.2.2 完整公式

```
grid_x = floor((mouse_screen_x + camera_x) / TILE_SIZE)
grid_y = floor((mouse_screen_y - HUD_HEIGHT + camera_y) / TILE_SIZE)
```

### 3.3 约束与边界条件

| 条件 | 处理 |
|------|------|
| `mouse_screen_y < HUD_HEIGHT` | 点击在 HUD 区域，不触发网格操作 |
| `grid_x < 0` 或 `grid_x >= GRID_WIDTH` | 超出地图水平范围，忽略 |
| `grid_y < 0` 或 `grid_y >= GRID_HEIGHT` | 超出地图垂直范围，忽略 |
| 点击在地图有效范围内 | 触发对应瓦片的交互逻辑 |

### 3.4 伪代码

```typescript
function screenToGrid(
  mouseX: number,
  mouseY: number,
  cameraX: number,
  cameraY: number
): { gridX: number; gridY: number } | null {
  // 步骤 1：检查是否在 HUD 区域
  if (mouseY < HUD_HEIGHT) return null;

  // 步骤 2：计算世界坐标
  const worldX = mouseX + cameraX;
  const worldY = (mouseY - HUD_HEIGHT) + cameraY;

  // 步骤 3：转换为网格坐标
  const gridX = Math.floor(worldX / TILE_SIZE);
  const gridY = Math.floor(worldY / TILE_SIZE);

  // 步骤 4：边界检查
  if (gridX < 0 || gridX >= GRID_WIDTH) return null;
  if (gridY < 0 || gridY >= GRID_HEIGHT) return null;

  return { gridX, gridY };
}
```

### 3.5 逆向映射（网格 → 屏幕）

用于调试或特效定位：

```
screen_x = grid_x * TILE_SIZE - camera_x
screen_y = grid_y * TILE_SIZE - camera_y + HUD_HEIGHT
```

---

## 4. 多屏幕管理器状态机 (Multi-Screen State Machine)

### 4.1 状态集 (Screen State Set)

| 状态 ID | 名称 | 说明 |
|---------|------|------|
| `MAIN_MENU` | 主菜单 | 游戏启动界面，显示"开始"、"继续"、"设置"按钮 |
| `GAMEPLAY` | 主关卡游戏 | 核心玩法循环，玩家探索地图 |
| `BONUS_LEVEL` | 隐藏奖励关 | 独立的小地图 + 倒计时模式 |
| `MUMMY_SHOP` | 贪婪木乃伊商店 | 关卡间商店，购买道具 |
| `LEVEL_COMPLETE` | 关卡完成 | 通关结算界面，显示获得金币 |
| `GAME_OVER` | 游戏结束 | 玩家死亡，显示"重新开始"、"返回主菜单" |

### 4.2 状态转换规则

| 源状态 | 目标状态 | 触发条件 |
|--------|---------|---------|
| `MAIN_MENU` | `GAMEPLAY` | 玩家点击"开始"或"继续" |
| `GAMEPLAY` | `BONUS_LEVEL` | 玩家踏上已显露的楼梯格 |
| `GAMEPLAY` | `MUMMY_SHOP` | 通关后进入商店关卡（每隔 N 关） |
| `GAMEPLAY` | `LEVEL_COMPLETE` | 玩家到达出口传送门 |
| `GAMEPLAY` | `GAME_OVER` | 玩家生命值归零 |
| `BONUS_LEVEL` | `GAMEPLAY` | 倒计时归零或踩陷阱 |
| `MUMMY_SHOP` | `GAMEPLAY` | 玩家完成购物，点击"离开" |
| `LEVEL_COMPLETE` | `GAMEPLAY` | 玩家点击"下一关" |
| `LEVEL_COMPLETE` | `MUMMY_SHOP` | 若下一关是商店关 |
| `GAME_OVER` | `MAIN_MENU` | 玩家点击"返回主菜单" |
| `GAME_OVER` | `GAMEPLAY` | 玩家点击"重新开始"（消耗复活护身符） |

### 4.3 生命周期接口 (Screen Lifecycle Interface)

每个 Screen 必须实现以下标准接口：

```typescript
interface ScreenObject {
  // 进入屏幕时调用（一次）
  on_enter(data?: any): void;

  // 退出屏幕时调用（一次）
  on_exit(): void;

  // 每帧更新逻辑
  update(dt: number): void;

  // 每帧渲染
  render(surface: Surface): void;

  // 处理输入事件
  handle_events(event: Event): void;
}
```

#### 4.3.1 `on_enter(data?)`

- 初始化屏幕内部状态（按钮列表、动画状态、数据加载）。
- `data` 参数用于接收来自前一个屏幕的传递数据。

#### 4.3.2 `on_exit()`

- 清理屏幕资源（停止动画、释放临时纹理）。
- 保存需要跨屏传递的数据到 ScreenManager。

#### 4.3.3 `update(dt)`

- 更新动画帧、按钮悬停状态、计时器。
- `dt` 为上一帧到当前帧的时间差（秒），用于帧率无关更新。

#### 4.3.4 `render(surface)`

- 绘制背景、UI 元素、按钮、文字到主 Surface。

#### 4.3.5 `handle_events(event)`

- 处理鼠标移动、点击、键盘按键等事件。
- 返回 `true` 表示事件已消费，不再传递。

### 4.4 切换过渡规范 (Transition Rules)

#### 4.4.1 数据流转规则

| 切换场景 | 传递数据 | 清理规则 |
|---------|---------|---------|
| GAMEPLAY → BONUS_LEVEL | 无（主关卡状态由 SuspendedLevelState 保存） | 不清理主关卡数据 |
| BONUS_LEVEL → GAMEPLAY | `collectedGold: number` | 清理奖励关地图与倒计时器 |
| GAMEPLAY → LEVEL_COMPLETE | `levelGold: number`, `levelTime: number` | 清理主关卡地图数据 |
| GAMEPLAY → GAME_OVER | `deathCause: string` | 保留永久升级数据（金币、护身符等） |
| GAME_OVER → GAMEPLAY | 无（新游戏） | 清理当前关卡会话，重置临时道具 |
| LEVEL_COMPLETE → MUMMY_SHOP | `currentLevel: number` | 无特殊清理 |
| MUMMY_SHOP → GAMEPLAY | `purchasedItems: ItemList` | 清理商店界面状态 |

#### 4.4.2 过渡动画

| 切换场景 | 动画类型 | 时长 |
|---------|---------|------|
| MAIN_MENU → GAMEPLAY | 淡入 (Fade In) | 0.5s |
| GAMEPLAY → BONUS_LEVEL | 向下沉入 (Slide Down) | 0.4s |
| BONUS_LEVEL → GAMEPLAY | 向上浮出 (Slide Up) | 0.4s |
| GAMEPLAY → LEVEL_COMPLETE | 淡出 (Fade Out) | 0.6s |
| GAMEPLAY → GAME_OVER | 震动 + 红色闪烁 | 0.8s |
| 其他切换 | 硬切 (Cut) | 0s |

### 4.5 状态机流程图

```
                    ┌──────────────┐
                    │  MAIN_MENU   │
                    └──────┬───────┘
                           │ 点击"开始"
                           ▼
                    ┌──────────────┐
            ┌──────│  GAMEPLAY    │──────┐
            │      └──────┬───────┘      │
            │             │              │
    ┌───────┴───┐   ┌─────┴─────┐  ┌─────┴─────┐
    │BONUS_LEVEL│   │LEVEL_COMPLETE│  │ GAME_OVER │
    └───────┬───┘   └─────┬─────┘  └─────┬─────┘
            │             │              │
            │             ▼              │
            │      ┌──────────────┐      │
            │      │ MUMMY_SHOP   │──────┘
            │      └──────────────┘ (复活护身符)
            │             │
            └─────────────┘
               (返回主关卡)
```

---

## 5. 系统类接口与算法伪代码 (API & Logic Pseudo-code)

### 5.1 Camera 类

#### 5.1.1 类定义

```typescript
class Camera {
  public x: number;
  public y: number;
  private lerpFactor: number;
  private speed: number;

  constructor(config: CameraConfig) {
    this.x = 0;
    this.y = 0;
    this.lerpFactor = config.lerpFactor;
    this.speed = config.speed;
  }

  public update(playerX: number, playerY: number, mapWidth: number, mapHeight: number, dt: number): void {
    const viewportWidth = VIEWPORT_WIDTH;
    const viewportHeight = VIEWPORT_HEIGHT;

    // 1. 计算目标坐标（玩家中心）
    let targetX = playerX - viewportWidth / 2;
    let targetY = playerY - viewportHeight / 2;

    // 2. 边界钳制
    const maxX = Math.max(0, mapWidth - viewportWidth);
    const maxY = Math.max(0, mapHeight - viewportHeight);
    targetX = Math.max(0, Math.min(targetX, maxX));
    targetY = Math.max(0, Math.min(targetY, maxY));

    // 3. 帧率无关平滑插值
    const t = 1 - Math.exp(-this.speed * dt);
    this.x += (targetX - this.x) * t;
    this.y += (targetY - this.y) * t;
  }

  public screenToGrid(mouseX: number, mouseY: number): { gridX: number; gridY: number } | null {
    if (mouseY < HUD_HEIGHT) return null;

    const worldX = mouseX + this.x;
    const worldY = (mouseY - HUD_HEIGHT) + this.y;

    const gridX = Math.floor(worldX / TILE_SIZE);
    const gridY = Math.floor(worldY / TILE_SIZE);

    if (gridX < 0 || gridX >= GRID_WIDTH) return null;
    if (gridY < 0 || gridY >= GRID_HEIGHT) return null;

    return { gridX, gridY };
  }

  public getVisibleTiles(): { startCol: number; endCol: number; startRow: number; endRow: number } {
    const startCol = Math.max(0, Math.floor(this.x / TILE_SIZE));
    const endCol = Math.min(GRID_WIDTH, Math.ceil((this.x + VIEWPORT_WIDTH) / TILE_SIZE));
    const startRow = Math.max(0, Math.floor(this.y / TILE_SIZE));
    const endRow = Math.min(GRID_HEIGHT, Math.ceil((this.y + VIEWPORT_HEIGHT) / TILE_SIZE));

    return { startCol, endCol, startRow, endRow };
  }
}
```

#### 5.1.2 使用示例

```typescript
const camera = new Camera({
  lerpFactor: 0.12,
  speed: 10,
  viewportWidth: 1024,
  viewportHeight: 672,
});

// 游戏主循环中
function gameLoop(dt: number): void {
  const playerPixelX = player.gridX * TILE_SIZE;
  const playerPixelY = player.gridY * TILE_SIZE;
  const mapPixelWidth = GRID_WIDTH * TILE_SIZE;
  const mapPixelHeight = GRID_HEIGHT * TILE_SIZE;

  camera.update(playerPixelX, playerPixelY, mapPixelWidth, mapPixelHeight, dt);

  // 渲染
  const { startCol, endCol, startRow, endRow } = camera.getVisibleTiles();
  renderTiles(startCol, endCol, startRow, endRow);
}
```

### 5.2 ScreenManager 类

#### 5.2.1 类定义

```typescript
class ScreenManager {
  private currentScreen: ScreenObject | null;
  private screens: Map<string, ScreenObject>;
  private transition: Transition | null;
  private pendingScreen: string | null;
  private pendingData: any;

  constructor() {
    this.screens = new Map();
    this.currentScreen = null;
    this.transition = null;
    this.pendingScreen = null;
    this.pendingData = null;
  }

  public registerScreen(id: string, screen: ScreenObject): void {
    this.screens.set(id, screen);
  }

  public switchScreen(newScreenId: string, dataPayload?: any): void {
    if (!this.screens.has(newScreenId)) {
      console.error(`Screen "${newScreenId}" not registered.`);
      return;
    }

    // 退出当前屏幕
    if (this.currentScreen) {
      this.currentScreen.on_exit();
    }

    // 切换屏幕
    this.pendingScreen = newScreenId;
    this.pendingData = dataPayload;

    // 启动过渡动画
    this.transition = new Transition('fade', 0.5, () => {
      this._completeSwitch();
    });
  }

  private _completeSwitch(): void {
    const newScreen = this.screens.get(this.pendingScreen!);
    if (newScreen) {
      this.currentScreen = newScreen;
      this.currentScreen.on_enter(this.pendingData);
    }
    this.pendingScreen = null;
    this.pendingData = null;
    this.transition = null;
  }

  public update(dt: number): void {
    if (this.transition) {
      this.transition.update(dt);
    }
    if (this.currentScreen) {
      this.currentScreen.update(dt);
    }
  }

  public render(surface: Surface): void {
    if (this.currentScreen) {
      this.currentScreen.render(surface);
    }
    if (this.transition) {
      this.transition.render(surface);
    }
  }

  public handleEvents(event: Event): void {
    if (this.currentScreen) {
      this.currentScreen.handle_events(event);
    }
  }
}
```

#### 5.2.2 使用示例

```typescript
const screenManager = new ScreenManager();

// 注册所有屏幕
screenManager.registerScreen('main_menu', new MainMenuScreen());
screenManager.registerScreen('gameplay', new GameplayScreen());
screenManager.registerScreen('bonus_level', new BonusLevelScreen());
screenManager.registerScreen('mummy_shop', new MummyShopScreen());
screenManager.registerScreen('level_complete', new LevelCompleteScreen());
screenManager.registerScreen('game_over', new GameOverScreen());

// 切换到主菜单
screenManager.switchScreen('main_menu');

// 游戏主循环
function gameLoop(dt: number): void {
  screenManager.handleEvents(event);
  screenManager.update(dt);
  screenManager.render(mainSurface);
}
```

### 5.3 TypeScript 接口定义

```typescript
// 摄像机配置接口
interface CameraConfig {
  lerpFactor: number;       // 平滑插值因子 (0.1–0.15)
  speed: number;            // 帧率无关速度 (8–12)
  viewportWidth: number;    // 视口宽度 (1024)
  viewportHeight: number;   // 视口高度 (672)
}

// HUD 元素接口
interface HUDElement {
  id: string;               // 元素 ID
  icon: string;             // 图标资源路径
  position: { x: number; y: number };  // 屏幕位置
  size: { width: number; height: number };
  visible: boolean;         // 是否可见
  data: () => any;          // 数据绑定函数
  render: (surface: Surface) => void;  // 自定义渲染方法
}

// 屏幕对象接口
interface ScreenObject {
  id: string;
  isActive: boolean;
  on_enter(data?: any): void;
  on_exit(): void;
  update(dt: number): void;
  render(surface: Surface): void;
  handle_events(event: Event): void;
}

// 屏幕管理器接口
interface ScreenManager {
  currentScreen: ScreenObject | null;
  registerScreen(id: string, screen: ScreenObject): void;
  switchScreen(newScreenId: string, dataPayload?: any): void;
  update(dt: number): void;
  render(surface: Surface): void;
  handleEvents(event: Event): void;
}

// 过渡动画接口
interface Transition {
  type: 'fade' | 'slide' | 'cut';
  duration: number;         // 秒
  progress: number;         // 0–1
  onComplete: () => void;
  update(dt: number): void;
  render(surface: Surface): void;
}

// 屏幕状态枚举
enum ScreenState {
  MAIN_MENU = 'main_menu',
  GAMEPLAY = 'gameplay',
  BONUS_LEVEL = 'bonus_level',
  MUMMY_SHOP = 'mummy_shop',
  LEVEL_COMPLETE = 'level_complete',
  GAME_OVER = 'game_over',
}

// 屏幕切换数据载荷
interface ScreenTransitionData {
  from: ScreenState;
  to: ScreenState;
  payload?: any;
  timestamp: number;
}
```

---

## 附录 A：与其他文档的契约关系

| 关联文档 | 关联点 |
|---------|--------|
| `01_core_gameplay.md` | 游戏主循环、瓦片大小定义、玩家移动触发摄像机更新 |
| `02_hearts_and_shields.md` | 红心/护盾 HUD 显示数据源 |
| `03_interactive_elements.md` | 瓦片交互触发鼠标点击映射 |
| `04_tools_and_economy.md` | 金币/铁锹/炸药/地图计数器 HUD 数据源 |
| `05_mummy_shop_and_amulet.md` | 商店屏幕 (MUMMY_SHOP)、护身符图标 |
| `06_map_generation.md` | 地图尺寸用于摄像机边界计算 |
| `07_monsters_and_weapons.md` | 弓箭/柴刀槽位 HUD 数据源 |
| `08_bonus_levels_and_clover.md` | 四叶草 Buff 图标、BONUS_LEVEL 屏幕切换 |

## 附录 B：关键常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `SCREEN_WIDTH` | 1024 | 主屏幕分辨率宽度 |
| `SCREEN_HEIGHT` | 768 | 主屏幕分辨率高度 |
| `HUD_HEIGHT` | 96 | HUD 状态栏高度 |
| `VIEWPORT_WIDTH` | 1024 | 游戏渲染区宽度 |
| `VIEWPORT_HEIGHT` | 672 | 游戏渲染区高度 (768−96) |
| `TILE_SIZE` | 32 | 瓦片像素大小 |
| `GRID_WIDTH` | 32 | 每行瓦片数 (1024/32) |
| `GRID_HEIGHT` | 21 | 每列瓦片数 (672/32) |
| `CAMERA_LERP_FACTOR` | 0.12 | 摄像机平滑因子 |
| `CAMERA_SPEED` | 10 | 摄像机帧率无关速度 |
