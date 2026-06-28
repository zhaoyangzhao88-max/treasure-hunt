# 第 10 课：全局软件架构、主循环与资产管理器设计规范

> 本文档定义 Microsoft Treasure Hunt 复刻项目中的**四层架构蓝图 (Layered Architecture)**、**Pygame 主循环与帧率控制 (Main Loop & Framerate Control)**、**Delta Time 规范 (dt-based Update)**、**资产管理器与优雅降级 (AssetManager & Graceful Degradation)**、**数据持久化与存档 (SaveManager & Serialization)**。本文档与 `01_core_gameplay.md`（核心玩法）、`02_hearts_and_shields.md`（红心/护盾）、`03_interactive_elements.md`（地图交互）、`04_tools_and_economy.md`（经济系统）、`05_mummy_shop_and_amulet.md`（商店/复活）、`06_map_generation.md`（地图生成）、`07_monsters_and_weapons.md`（怪物/武器）、`08_bonus_levels_and_clover.md`（奖励关）、`09_ui_layout_and_screens.md`（UI/屏幕管理器）配合使用，作为整合全部底层模块的"顶层设计契约"。所有后续课程（11–60）应严格遵循本文档所定义的架构约束。

---

## 目录

1. [全局架构蓝图与依赖关系 (Architecture Blueprint)](#1-全局架构蓝图与依赖关系-architecture-blueprint)
2. [主循环、帧率控制与 Delta Time (Main Loop & Framerate Control)](#2-主循环帧率控制与-delta-time-main-loop--framerate-control)
3. [资产加载管理器与优雅降级 (AssetManager & Graceful Degradation)](#3-资产加载管理器与优雅降级-assetmanager--graceful-degradation)
4. [数据持久化与存档设计 (SaveManager & Serialization)](#4-数据持久化与存档设计-savemanager--serialization)
5. [系统级核心伪代码与 TypeScript 接口 (Core System API)](#5-系统级核心伪代码与-typescript-接口-core-system-api)

---

## 1. 全局架构蓝图与依赖关系 (Architecture Blueprint)

### 1.1 架构拓扑图 (Architecture Topology)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              main.py :: main()                                  │
│                              sys.exit(pygame.quit())                             │
└─────────────────────────────────────�───────────────────────────────────────────┘
                                      │ 创建 & 持有
                                      ▼
�─────────────────────────────────────────────────────────────────────────────────┐
│                              GameManager (单例)                                  │
│  ┌──────────────┬──────────────┬──────────────┬──────────────�─────────────�    │
│  │ AssetManager │ ScreenManager│ SaveManager  │ PlayerState  │ LevelEngine │    │
│  │   (单例)      │  (屏幕状态机) │  (序列化)     │  (运行时数据) │ (关卡运行时) │    │
│  └──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┴──────┬──────┘    │
└─────────┼──────────────┼──────────────�──────────────┼──────────────┼───────────┘
          │              │              │              │              │
          │              │              │              │              ▼
          │              │              │              │     ┌────────────────────┐
          │              │              │              │     │ LevelEngine 子模块  │
          │              │              │              │     │ �────────────────┐ │
          │              │              │              │     │ │ TileMap        │ │
          │              │              │              │     │ │ MonsterSpawner │ │
          │              │              │              │     │ │ ItemDropper   │ │
          │              │              │              │     │ │ BonusPortal    │ │
          │              │              │              │     │ │ ShopZone       │ │
          │              │              │              │     │ └────────────────┘ │
          │              │              │              │     └────────────────────┘
          │              │              │              │
          ▼              ▼              ▼              ▼
   ┌────────────┐  ┌──────────┐  ┌───────────�  �───────────┐
   │ 磁盘文件    │  │ pygame   │  │ save.json │  │ 内存运行时 │
   │ png/ogg/wav│  │ Display  │  │ (持久化)   │  │ 状态对象   │
   └────────────┘  └──────────�  └───────────┘  └───────────┘
```

### 1.2 四层架构层级 (Four-Layer Architecture)

| 层级 | 名称 | 职责 | 可依赖于 | 对应文档 |
|------|------|------|---------|---------|
| **Layer 0** |) | 操作系统、pygame 初始化、display surface | 仅 pygame 自身 | — |
| **Layer 1** | 引擎层 | AssetManager、主循环、事件分发、SaveManager | Layer 0 | 本文档 |
| **Layer 2** | 游戏逻辑层 | LevelEngine、TileMap、MonsterSpawner、PlayerState、物理/碰撞 | Layer 0–1 | docs/01–08 |
| **Layer 3** | UI / 表现层 | ScreenManager、HUD、摄像机、动画 | Layer 0–2 | docs/09 |

**通信边界**: 只允许**自顶向下的单向调用**，同层模块通过 GameManager 中介通信；Layer 3 不得直接访问 Layer 1 的磁盘/asset 操作，必须经过 GameManager 上下文。

### 1.3 核心管理器职责一览 (Manager Responsibility Matrix)

| 类 | 模式 | 文件 | 生命周期 | 核心职责 |
|----|------|-----|---------|---------|
| `GameManager` | 单例 (Singleton) | `src/engine/game_manager.py` | 整个应用 | 顶层协调者，持有所有 Manager 引用 |
| `AssetManager` | 单例 (Singleton) | `src/engine/asset_manager.py` | 整个应用 | 加载/缓存图片、音频、字体；容错回退 |
| `ScreenManager` | 状态机 | `src/engine/screen_manager.py` | 整个应用 | 切换 Title / Playing / Pause / Shop / GameOver 屏幕 |
| `SaveManager` | 静态工具类 | `src/engine/save_manager.py` | 按需调用 | 读写 `save.json`，安全写入 + 数据校验 |
| `PlayerState` | 普通对象 | `src/game/player_state.py` | 每关开始时重置 | 持有玩家当前运行时属性 |
| `LevelEngine` | 普通对象 | `src/game/level_engine.py` | 每关运行时 | 管理 TileMap、怪物、道具、出口，对应 docs/01–08 |

### 1.4 模块-文档映射 (Module-to-Doc Traceability)

| 模块 | 依赖的底层规范文档 |
|------|------------------|
| `GameManager`, 主循环 | 本文档 (docs/10) |
| `AssetManager` | 本文档 (docs/10) |
| `SaveManager` | 本文档 (docs/10) |
| `ScreenManager` | docs/09（屏幕分区、状态机） |
| `PlayerState` | docs/01（核心玩法）、docs/02（红心/护盾）、docs/04（金币） |
| `LevelEngine.TileMap` | docs/03（地图交互）、docs/06（生成） |
| `LevelEngine.MonsterSpawner` | docs/07（怪物/武器） |
| `LevelEngine.ShopZone` | docs/05（商店/复活） |
| `LevelEngine.BonusPortal` | docs/08（奖励关/四叶草） |

---

## 2. 主循环、帧率控制与 Delta Time (Main Loop & Framerate Control)

### 2.1 事件循环规范 (Event Loop Specification)

#### 2.1.1 Pygame 事件拦截清单

| 事件类型 | 处理方式 | 说明 |
|----------|---------|------|
| `pygame.QUIT` | 触发 `game_manager.running = False`，优雅退出 | 窗口关闭按钮 |
| `pygame.KEYDOWN` + `K_F1` | 切换到 Help / 关于屏幕 | 全局帮助 |
| `pygame.KEYDOWN` + `K_F11` | 切换全屏显示 | `pygame.display.toggle_fullscreen()` |
| `pygame.KEYDOWN` + `K_ESCAPE` | 暂停 / 恢复（Pause 屏幕） | 仅在游戏中有效 |
| `pygame.KEYDOWN` + `K_M` | 静音 / 取消静音 | 切换 BGM/SFX 音量 |
| `pygame.VIDEORESIZE` | 更新 display surface，重新计算缩放 | 仅窗口模式 |
| 其他 `KEYDOWN` 事件 | 委托给 `ScreenManager.handle_key(event)` | 上下文按键 |

#### 2.1.2 全局快捷键登记

| 按键 | 动作 | 优先级 | 备注 |
|------|------|--------|------|
| `Ctrl + Q` | 强制退出（写入存档） | 最高 | 等同于 `pygame.QUIT` |
| `F1` | 显示帮助屏幕 | 高 | 覆盖当前屏幕（除 Title） |
| `F11` | 切换全屏 | 中 | 切换 display flags |
| `ESC` | 暂停 / 返回 | 中 | 状态机切换 |
| `M` | 静音切换 | 低 | 修改 GameConfig 音频标志 |

### 2.2 帧率钳制 (Framerate Capping)

| 属性 | 值 | 说明 |
|------|-----|------|
| 目标 FPS | **60** | 标准复古帧率 |
| `clock` | `pygame.time.Clock()` | 帧率控制器 |
| 钳制方式 | `clock.tick(FPS)` | 每帧结束时调用；内部通过 `pygame.time.wait` / `delay` 控制帧间隔 |
| 物理更新模式 | **可变时间步长 (Variable Timestep)** | 基于 `dt`，非帧计数 |
| 渲染模式 | **每帧渲染** | 无需累积；显示最新状态 |

> **警告**：不使用固定步长累加器 (accumulator)。在本游戏的 32×32 像素 tile 粒度下，每帧用 `dt` 更新位置已经足够精确，不会产生可感知抖动；固定步长会增加复杂度且收益甚微。如果后续需要严格确定性回放，可另加定步长物理，但**默认采用 dt**。

### 2.3 Delta Time (dt) 计算规范

#### 2.3.1 计算公式

```python
# 每帧 tick 返回自上次 tick 的毫秒数 (int)
dt_ms = clock.tick(FPS)        # 单位: 毫秒
dt    = dt_ms / 1000.0         # 单位: 秒（浮点数）
```

#### 2.3.2 dt 钳制 (dt Clamping)

某些系统（如 OS 调度、GC、长时间断点调试）可能导致 dt 极端跳变。**必须钳制 dt 到 `[0.0, MAX_DT]`**：

| 参数 | 值 | 说明 |
|------|-----|------|
| `MAX_DT` | `0.25` 秒 (250 ms) | 最大允许 dt，超出视为卡顿时截断 |
| 典型 `dt` | ≈ `0.0167` 秒 (16.7 ms) | 60 FPS 下一帧 |

```python
dt = min(dt, MAX_DT)  # 防止卡顿时角色穿墙
```

#### 2.3.3 dt 使用场景

所有涉及**时间相关数值更新**的逻辑**必须**使用 `dt`，不得使用帧计数：

| 场景 | 公式示例 | 错误示例 (帧率绑定) |
|------|---------|-------------------|
| 玩家位置 | `player.x += player.speed * dt` | `player.x += 4` |
| 无敌闪烁 | `player.invincible_timer -= dt` | `player.invincible_timer -= 1` |
| BGM 淡入 | `bgm_volume = min(1.0, bgm_volume + dt * 0.5)` | `bgm_volume += 0.008` |
| 怪物 AI | `monster.think_timer -= dt` | `monster.think_timer -= 1` |
| 屏幕过渡 | `fade_alpha = min(255, fade_alpha + 300 * dt)` | `fade_alpha += 5` |
| 金币飘字 | `coin_text.y -= 40 * dt` | `coin_text.y -= 0.67` |

#### 2.3.4 时间单位统一表

| 模块 | 输入单位 | 存储单位 | 渲染单位 |
|------|---------|---------|---------|
| 位移 | 像素/秒 (px/s) | 像素 (px) | 像素 (int) |
| 速度 | 像素/秒² | 像素/秒 (float) | — |
| 计时器 | 秒 (s) | 秒 (float) | 秒 (float) |
| 动画帧 | 帧/秒 (fps) | 秒/帧 (float) | 帧索引 (int) |
| 透明度 | — | 0–255 (int) | 0–255 (int) |

---

## 3. 资产加载管理器与优雅降级 (AssetManager & Graceful Degradation)

### 3.1 AssetManager 设计

#### 3.1.1 单例模式 (Singleton)

- 通过 `AssetManager.instance()` 类方法获取全局唯一实例
- `__init__` 只在首次创建时执行，后续 `instance()` 直接返回已有实例
- 提供 ` AssetManager.instance().reset()` 仅用于测试场景

#### 3.1.2 内部缓存结构

| 缓存字典 | 键类型 | 值类型 | 说明 |
|---------|--------|--------|------|
| `_images: dict[str, pygame.Surface]` | 资产名 | Surface | 已加载图片 |
| `_sounds: dict[str, pygame.mixer.Sound]` | 资产名 | Sound | 已加载音效 |
| `_fonts: dict[str, pygame.font.Font]` | `"name_size"` | Font | 已加载字体 |
| `_tilesheets: dict[str, list[Surface]]` | tilesheet 名 | Surface 列表 | 已切割的瓦片列表 |

#### 3.1.3 加载策略：预加载 + 懒加载

| 阶段 | 预加载资产 | 懒加载时机 |
|------|----------|-----------|
| **启动时** | 标题画面 BGM、Logo、默认字体 | — |
| **关卡开始前** | 关卡 tilesheet、玩家动画帧、怪物动画帧、HUI 图标、环境 BGM、互动 SFX | — |
| **关卡加载中** | — | 达到特定房间/区域时按需加载（如进入奖励关时懒加载 bonus tilesheet） |
| **退出关卡时** | — | 释放非持久化资产（保留标题 BGM、字体） |

### 3.2 资产清单表 (Asset Inventory)

| 资产类别 | 路径前缀 | 命名规范 | 占位回退方式 |
|---------|---------|---------|------------|
| 瓦片集 (Tilesheet) | `assets/tiles/` | `{theme}_tiles.png` (32×32 网格) | 灰色 `#808080` Surface |
| 角色动画 | `assets/sprites/` | `{entity}_{state}_{frame}.png` (32×32) | 粉色 `#FF00FF` Surface |
| UI 图标 | `assets/ui/` | `{icon_name}.png` (24×24) | 白色方框 Surface |
| BGM | `assets/audio/bgm/` | `{track_name}.ogg` | 静默（跳过播放） |
| SFX | `assets/audio/sfx/` | `{effect_name}.wav` | 静默（跳过播放） |
| 字体 | `assets/fonts/` | `{font_name}.ttf` | `pygame.font.SysFont("arial", size)` |

### 3.3 加载容错机制 (Graceful Degradation)

#### 3.3.1 设计目标

> **游戏绝不因缺失资产而闪退**。任何资产加载失败都应：
> 1. 拦截 `pygame.error` / `FileNotFoundError` / `OSError`
> 2. 在 stderr 打印警告日志
> 3. 返回功能等效的占位符（placeholder）Surface / 静默播放器
> 4. 允许游戏继续运行

#### 3.3.2 占位符规格

| 资产类型 | 占位符尺寸 | 占位符内容 | 绘制策略 |
|---------|-----------|----------|---------|
| 瓦片图片 (32×32) | 32×32 | 灰色 `#808080` 实心方块 | 全方块填充 |
| 精灵动画 (32×32) | 32×32 | 品红 `#FF00FF` 方块 + 白色边框 (`pygame.draw.rect`) | 突出显示"缺图" |
| UI 图标 (24×24) | 24×24 | 白色方块 + 黑色十字 `+` | 明显但未遮挡 |
| 字体 `{size}` | — | `SysFont("arial", size)` | 系统字体兜底 |
| 音频 (BGM/SFX) | — | `None`（不播放） | `if sound: sound.play()` |

#### 3.3.3 容错流程图

```
load_image("wall", "assets/tiles/wall.png")
        │
        ├── 缓存命中 ──→ 直接返回缓存 Surface
        │
        ▼ (缓存未命中)
   try:
        surface = pygame.image.load(path).convert_alpha()
        _images[key] = surface
        return surface
   except (pygame.error, FileNotFoundError, OSError) as e:
        print(f"WARNING: Failed to load image '{path}': {e}", file=sys.stderr)
        placeholder = pygame.Surface((32, 32))
        placeholder.fill((128, 128, 128))   # 灰色占位
        _images[key] = placeholder
        return placeholder
```

### 3.4 公共方法签名

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `load_image(key, path, size=None)` | `key: str, path: str, size: tuple[int, int] \| None` | `pygame.Surface` | 加载并缓存；size 非空时缩放 |
| `load_sound(key, path)` | `key: str, path: str` | `pygame.mixer.Sound \| None` | 失败返回 `None`，不抛异常 |
| `load_font(key, path, size)` | `key: str, path: str, size: int` | `pygame.font.Font` | 字体加载，失败返回系统字体 |
| `load_tilesheet(key, path, frame_width, frame_height)` | — | `list[Surface]` | 切割并缓存瓦片列表 |
| `unload(key)` | `key: str` | `None` | 从缓存移除并释放 Surface |
| `unload_all()` | — | `None` | 清空所有缓存 |
| `get_memory_usage()` | — | `dict` | 各缓存项数量，用于调试 |

---

## 4. 数据持久化与存档设计 (SaveManager & Serialization)

### 4.1 存档路径与生命周期

| 属性 | 值 | 说明 |
|------|-----|------|
| 存档目录 | `%USERPROFILE%/.microsoft-treasure-hunt/` | 跨平台使用 `os.path.expanduser("~")` |
| 存档文件 | `save.json` | 主存档 |
| 临时文件 | `save.json.tmp` | 写入中 |
| 备份文件 | `save.json.bak` | 上一份有效存档（滚动备份） |
| 格式 | JSON (UTF-8) | 人类可读，便于调试 |
| 创建时机 | **首次写入时**自动创建目录 | `os.makedirs(..., exist_ok=True)` |

### 4.2 存档数据结构 (Save Payload Schema)

```json
{
  "version": 1,
  "timestamp": "2026-06-25T12:34:56Z",
  "player": {
    "maxHearts": 6,
    "maxShields": 3,
    "maxBagCapacityTier": 2,
    "gold": 500,
    "highestLevelCleared": 12,
    "totalRuns": 42,
    "totalMonstersSlain": 178,
    "totalGoldEarned": 98500,
    "permanentUnlocks": ["shovel_tier_2", "dynamite_tier_1"]
  },
  "settings": {
    "bgmVolume": 0.7,
    "sfxVolume": 0.9,
    "fullscreen": false,
    "language": "zh-CN"
  },
  "checksum": "sha256:abcdef123456..."
}
```

### 4.3 字段语义表

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `version` | `int` | 存档格式版本号，用于迁移 | `1` |
| `timestamp` | `string (ISO8601)` | 最后保存时间 | 写入时生成 |
| `player.maxHearts` | `int` | 最大红心数（Roguelite 升级） | `3` |
| `player.maxShields` | `int` | 最大护盾数 | `0` |
| `player.maxBagCapacityTier` | `int` | 背包容量梯队（0–5） | `0` |
| `player.gold` | `int` | 当前金币（用于商店消费） | `0` |
| `player.highestLevelCleared` | `int` | 历史最高通关关卡 | `0` |
| `player.totalRuns` | `int` | 总运行次数（含失败） | `0` |
| `player.totalMonstersSlain` | `int` | 累计击杀怪物 | `0` |
| `player.totalGoldEarned` | `int` | 累计获取金币 | `0` |
| `player.permanentUnlocks` | `string[]` | 永久解锁项标识列表 | `[]` |
| `settings.bgmVolume` | `float` | BGM 音量 0.0–1.0 | `0.7` |
| `settings.sfxVolume` | `float` | SFX 音量 0.0–1.0 | `0.9` |
| `settings.fullscreen` | `bool` | 全屏标志 | `false` |
| `settings.language` | `string` | 界面语言 | `"zh-CN"` |
| `checksum` | `string` | SHA256 签名（仅对 data 部分） | 写入时计算 |

### 4.4 安全写入与数据校验 (Safe Write & Checksum)

#### 4.4.1 原子写入协议 (Atomic Write Protocol)

```
步骤 1: 序列化 payload（不含 checksum）→ bytes
步骤 2: 计算 SHA256(payload_bytes) → hex
步骤 3: 将 checksum 填入字段，再次序列化
步骤 4: 写入 save.json.tmp
步骤 5: os.replace(tmp, save)  （Windows 下原子替换；先 os.remove 再 os.rename 兜底）
步骤 6: 将 save.json 复制为 save.json.bak（滚动备份）
```

#### 4.4.2 读取与校验

```
步骤 1: 尝试读取 save.json
       - 失败则尝试 save.json.bak
       - 两者皆失败则创建默认存档
步骤 2: 解析 JSON
       - 失败则使用备份文件
       - 两者皆失败则创建默认存档
步骤 3: 分离 checksum 字段，对剩余 data 重新计算 SHA256
       - 不匹配则视为腐败，尝试备份
步骤 4: 版本号检查 → 若 version < CURRENT_VERSION 执行迁移
步骤 5: 返回 PlayerState 对象
```

#### 4.4.3 校验公式

```python
import hashlib

def _compute_checksum(data: dict) -> str:
    payload_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

def _verify_saved(save_data: dict) -> bool:
    stored_checksum = save_data.get("checksum", "")
    payload = {k: v for k, v in save_data.items() if k != "checksum"}
    return _compute_checksum(payload) == stored_checksum
```

### 4.5 SaveManager 公共接口

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `save(payload: dict)` | 存档数据 | `bool` (成功标志) | 带校验的安全原子写入 |
| `load()` | — | `dict \| None` | 加载并校验，失败返回 None |
| `has_save()` | — | `bool` | 检查是否存在有效存档 |
| `delete()` | — | `None` | 删除存档（重新开始） |
| `migrate(old_data, from_version)` | 旧数据 + 源版本号 | `dict` (迁移后) | 版本迁移逻辑 |

---

## 5. 系统级核心伪代码与 TypeScript 接口 (Core System API)

### 5.1 主循环伪代码 (main_loop Pseudocode)

```python
# src/engine/main.py
import sys
import pygame
from engine.game_manager import GameManager
from engine.asset_manager import AssetManager
from engine.save_manager import SaveManager

FPS     = 60
MAX_DT  = 0.25

def main():
    pygame.init()
    screen = pygame.display.set_mode((1024, 768))
    pygame.display.set_caption("Microsoft Treasure Hunt")
    clock = pygame.time.Clock()

    # 初始化各管理器
    asset_mgr  = AssetManager.instance()
    save_mgr   = SaveManager()
    game_mgr   = GameManager(asset_mgr, save_mgr, screen, clock)

    try:
        _main_loop(game_mgr, clock)
    finally:
        game_mgr.shutdown()
        pygame.quit()
        sys.exit()

def _main_loop(game_mgr, clock):
    game_mgr.startup()            # 加载标题屏幕、显示 Logo
    while game_mgr.running:
        # 1) 计算 dt
        dt_ms = clock.tick(FPS)
        dt    = min(dt_ms / 1000.0, MAX_DT)

        # 2) 事件处理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game_mgr.running = False
                break
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F1:
                    game_mgr.screen_mgr.switch_to("help")
                elif event.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                elif event.key == pygame.K_m:
                    game_mgr.config.muted = not game_mgr.config.muted
                elif event.key == pygame.K_ESCAPE:
                    game_mgr.screen_mgr.toggle_pause()
                else:
                    game_mgr.screen_mgr.handle_key(event)

        if not game_mgr.running:
            break

        # 3) 游戏逻辑更新 (dt-based)
        game_mgr.update(dt)

        # 4) 渲染
        game_mgr.render(screen)

        # 5) 刷新显示
        pygame.display.flip()

    # 循环退出前：自动保存
    game_mgr.autosave()
```

### 5.2 AssetManager 类伪代码

```python
# src/engine/asset_manager.py
import pygame
import sys

DEFAULT_PLACEHOLDER_SIZE = (32, 32)
DEFAULT_PLACEHOLDER_COLOR = (128, 128, 128)
SPRITE_PLACEHOLDER_COLOR  = (255, 0, 255)

class AssetManager:
    _instance = None

    def __init__(self):
        self._images   = {}
        self._sounds   = {}
        self._fonts    = {}
        self._tilesheets = {}

    @classmethod
    def instance(cls) -> "AssetManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_image(self, key: str, path: str, size=None) -> pygame.Surface:
        if key in self._images:
            return self._images[key]
        try:
            surface = pygame.image.load(path).convert_alpha()
            if size:
                surface = pygame.transform.scale(surface, size)
        except (pygame.error, FileNotFoundError, OSError) as e:
            print(f"WARNING: Failed to load image '{path}': {e}", file=sys.stderr)
            surface = self._create_placeholder(path)
        self._images[key] = surface
        return surface

    def load_sound(self, key: str, path: str):
        if key in self._sounds:
            return self._sounds[key]
        try:
            sound = pygame.mixer.Sound(path)
        except (pygame.error, FileNotFoundError, OSError) as e:
            print(f"WARNING: Failed to load sound '{path}': {e}", file=sys.stderr)
            sound = None
        self._sounds[key] = sound
        return sound

    def _create_placeholder(self, path: str) -> pygame.Surface:
        placeholder = pygame.Surface(DEFAULT_PLACEHOLDER_SIZE).convert_alpha()
        placeholder.fill(DEFAULT_PLACEHOLDER_COLOR)
        return placeholder
```

### 5.3 SaveManager 类伪代码

```python
# src/engine/save_manager.py
import os, json, hashlib, time

SAVE_DIR  = os.path.join(os.path.expanduser("~"), ".microsoft-treasure-hunt")
SAVE_FILE = os.path.join(SAVE_DIR, "save.json")
SAVE_TEMP = SAVE_FILE + ".tmp"
SAVE_BAK  = SAVE_FILE + ".bak"

class SaveManager:
    def __init__(self):
        os.makedirs(SAVE_DIR, exist_ok=True)

    def save(self, payload: dict) -> bool:
        try:
            payload["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            payload["checksum"]  = self._compute_checksum(payload)
            json_str = json.dumps(payload, indent=2, ensure_ascii=False)
            # 原子写入
            with open(SAVE_TEMP, "w", encoding="utf-8") as f:
                f.write(json_str)
            # Windows 下 os.replace 保证原子替换
            os.replace(SAVE_TEMP, SAVE_FILE)
            # 滚动备份
            if os.path.exists(SAVE_FILE):
                if os.path.exists(SAVE_BAK):
                    os.remove(SAVE_BAK)
                os.replace(SAVE_FILE, SAVE_BAK)
            return True
        except OSError as e:
            print(f"ERROR: Save failed: {e}", file=sys.stderr)
            return False

    def load(self):
        for path in (SAVE_FILE, SAVE_BAK):
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 校验
                stored = data.get("checksum", "")
                payload = {k: v for k, v in data.items() if k != "checksum"}
                if self._compute_checksum(payload) != stored:
                    print(f"WARNING: Checksum mismatch in {path}, trying backup...", file=sys.stderr)
                    continue
                return data
            except (json.JSONDecodeError, OSError) as e:
                print(f"WARNING: Failed to read {path}: {e}", file=sys.stderr)
                continue
        return None

    def has_save(self) -> bool:
        return os.path.exists(SAVE_FILE)

    def _compute_checksum(self, data) -> str:
        payload_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
```

### 5.4 TypeScript 接口定义 (Core Type Definitions)

#### 5.4.1 GameConfig

```typescript
/** 全局游戏配置 — 仅运行时可变，不持久化到存档 **/
interface GameConfig {
  /** 设计分辨率（固定为 1024×768） */
  readonly designWidth: 1024;
  readonly designHeight: 768;

  /** 瓦片大小 (px) */
  readonly tileSize: 32;

  /** HUD 高度 (px) */
  readonly hudHeight: 96;

  /** 目标帧率 */
  readonly fps: 60;

  /** 是否静音 */
  muted: boolean;

  /** BGM 音量 0.0–1.0 */
  bgmVolume: number;

  /** SFX 音量 0.0–1.0 */
  sfxVolume: number;

  /** 全屏标志 */
  fullscreen: boolean;
}
```

#### 5.4.2 PersistentData

```typescript
/** 存档持久化数据 — 写入 save.json 的完整结构 */
interface PersistentData {
  /** 存档格式版本（用于迁移） */
  version: number;

  /** ISO8601 时间戳 */
  timestamp: string;

  /** 玩家 Roguelite 属性 */
  player: PlayerData;

  /** 用户设置 */
  settings: UserSettings;

  /** SHA256 校验和（排除自身字段后计算） */
  checksum: string;
}

/** 玩家 Roguelite 属性 */
interface PlayerData {
  /** 最大红心数（初始 3） */
  maxHearts: number;

  /** 最大护盾数 */
  maxShields: number;

  /** 背包容量梯队 (0–5) */
  maxBagCapacityTier: number;

  /** 当前金币 */
  gold: number;

  /** 历史最高通关关卡 */
  highestLevelCleared: number;

  /** 总运行次数 */
  totalRuns: number;

  /** 累计击杀怪物数 */
  totalMonstersSlain: number;

  /** 累计获取金币数 */
  totalGoldEarned: number;

  /** 永久解锁项标识列表 */
  permanentUnlocks: string[];
}

/** 用户设置 */
interface UserSettings {
  bgmVolume: number;
  sfxVolume: number;
  fullscreen: boolean;
  /** BCP-47 语言标签，如 "zh-CN" | "en-US" */
  language: string;
}
```

#### 5.4.3 AssetRegistry

```typescript
/** 资产注册表 — 记录已加载资产的元数据 */
interface AssetRegistry {
  /** 缓存键 → 文件路径映射 */
  images: Record<string, AssetMeta>;
  sounds: Record<string, AssetMeta>;
  fonts: Record<string, FontMeta>;
  tilesheets: Record<string, TilesheetMeta>;
}

/** 资产元数据 */
interface AssetMeta {
  /** 文件绝对或相对路径 */
  path: string;

  /** 是否为占位符回退 */
  isPlaceholder: boolean;

  /** 字节大小（仅图片/音频有效） */
  byteSize?: number;
}

/** 字体元数据（继承 AssetMeta） */
interface FontMeta extends AssetMeta {
  /** 字号 */
  size: number;
}

/** 瓦片集元数据 */
interface TilesheetMeta extends AssetMeta {
  /** 单帧宽度 */
  frameWidth: number;
  /** 单帧高度 */
  frameHeight: number;
  /** 总帧数 */
  frameCount: number;
}
```

#### 5.4.4 SavePayload

```typescript
/** 存档载荷 — 写入 save.json 时不含 checksum 的 payload 部分 */
interface SavePayload {
  version: number;
  timestamp: string;
  player: PlayerData;
  settings: UserSettings;
}

/** 存档操作结果 */
type SaveResult =
  | { success: true; timestamp: string }
  | { success: false; error: string };
```

---

## 附录 A：依赖关系快速参考 (Quick Dependency Reference)

当需要修改任何管理器时，必须首先确认其**下游依赖者**不会被破坏：

| 修改对象 | 受影响模块 | 需回归验证 |
|---------|----------|----------|
| `GameManager` | 仅 `main.py` | 启动流程、shutdown 流程 |
| `AssetManager` | `LevelEngine`、`ScreenManager`、HUD 渲染 | 所有关卡/屏幕切换后图形正常 |
| `SaveManager` | 平台进度写入、Roguelite 升级流程 | 写入后重启、恶意篡改存档 |
| `main_loop` | 所有计时、动画、物理 | 60 FPS 下运动平滑；dt clamp 后不卡穿墙 |

## 附录 B：常量汇总 (Constants Summary)

| 常量 | 值 | 来源 |
|------|-----|------|
| `DESIGN_WIDTH` | `1024` | docs/09 |
| `DESIGN_HEIGHT` | `768` | docs/09 |
| `TILE_SIZE` | `32` | docs/09 |
| `HUD_HEIGHT` | `96` | docs/09 |
| `FPS` | `60` | 本文档 §2.2 |
| `MAX_DT` | `0.25 秒` | 本文档 §2.3.2 |
| `SAVE_VERSION` | `1` | 本文档 §4.2 |
| `DEFAULT_PLACEHOLDER_SIZE` | `(32, 32)` | 本文档 §3.3.2 |
| `DEFAULT_PLACEHOLDER_COLOR` | `(128, 128, 128)` | 本文档 §3.3.2 |
| `SPRITE_PLACEHOLDER_COLOR` | `(255, 0, 255)` | 本文档 §3.3.2 |

---

> **维护注意**：本文档是全局架构的"宪法"。修改前必须同步更新下游 01–10 课中任何冲突的契约，并在 PR 描述中列出受影响的文档列表。
