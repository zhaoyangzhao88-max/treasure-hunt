# Microsoft Treasure Hunt — 开发看板

## 当前进度: 第 38 课 / 60 课 (38/60) ✅ 已完成

---

## 当前任务详细拆解 (Active Task Backlog)

- [x] 38.1 更新 PLAN.md，加入第 38 课的任务流
- [x] 38.2 编写并实现小地图渲染模块 `src/minimap.py` 与 `Minimap` 类
- [x] 38.3 升级 `src/screens/gameplay_screen.py`，集成小地图实例与 Tab 键切换
- [x] 38.4 升级 `src/screens/bonus_level_screen.py`，集成小地图支持
- [x] 38.5 编写单元测试 `tests/test_minimap.py` 验证自适应缩放、Tab 切换、渲染无崩溃、视口框线与玩家标记
- [x] 38.6 运行验证所有测试（234 项全通过），更新看板并归档任务

---

## 历史任务归档 (Archived Tasks)

### 第 38 课：实时小地图（Minimap）系统开发

- [x] 38.1 更新 PLAN.md，加入第 38 课的任务流
- [x] 38.2 编写并实现小地图渲染模块 `src/minimap.py` 与 `Minimap` 类
- [x] 38.3 升级 `src/screens/gameplay_screen.py`，集成小地图实例与 Tab 键切换
- [x] 38.4 升级 `src/screens/bonus_level_screen.py`，集成小地图支持
- [x] 38.5 编写单元测试 `tests/test_minimap.py` 验证自适应缩放、Tab 切换、渲染无崩溃、视口框线与玩家标记
- [x] 38.6 运行验证所有测试（234 项全通过），更新看板并归档任务

### 第 37 课：玩法指南与控制键位蒙层（HelpOverlay）开发与游戏内时停暂停机制实现

- [x] 37.1 更新 PLAN.md，加入第 37 课的任务流
- [x] 37.2 编写并实现玩法指南蒙层类 `src/help_overlay.py` 与 `HelpOverlay` 类
- [x] 37.3 升级 `src/screens/gameplay_screen.py`，注册蒙层实例，拦截按键 H/F1 触发开启关闭，并在开启时冻结更新与输入
- [x] 37.4 升级 `src/screens/bonus_level_screen.py`，实现同样的暂停与蒙层支持，暂停其 30s 核心倒计时
- [x] 37.5 编写单元测试 `tests/test_help_overlay.py` 验证 H/F1 切换触发、暂停期间键盘移动失效、鼠标点击失效、特效更新静止、以及渲染无崩溃
- [x] 37.6 运行验证所有测试（221 项全通过），更新看板并归档任务

### 第 36 课：多环境地貌（Biomes）色彩与主题自适应渲染引擎开发

- [x] 36.1 更新 PLAN.md，加入第 36 课的任务流
- [x] 36.2 在 `src/config.py` 中定义 `Biome` 枚举类，并规划 4 大地貌在不同关卡区间下的色板与 BGM 绑定参数
- [x] 36.3 升级 `src/tile_renderer.py`，使其支持接收 Biome 状态并在 Fallback 模式下自适应切换地形、障碍与空地颜色
- [x] 36.4 升级 `src/screens/gameplay_screen.py` 与 `src/audio_manager.py`，让进入关卡时自动计算 Biome 并联动切换对应的地貌专属 BGM
- [x] 36.5 编写单元测试 `tests/test_biomes_and_themes.py` 验证不同关卡的 Biome 确定性、各 Biome 色板一致性以及地貌 BGM 的自动调度
- [x] 36.6 运行验证所有测试（215 项全通过），更新看板并归档任务

### 第 35 课：全局音频管理器与场景背景音乐自适应切换机制开发

- [x] 35.1 更新 PLAN.md，加入第 35 课的任务流
- [x] 35.2 编写并实现全局音频管理器类 `src/audio_manager.py`
- [x] 35.3 集成 AudioManager 到 `GameManager`，在 `init_engine()` 中初始化
- [x] 35.4 重构所有 7 个屏幕类的 `on_enter()` 方法，加入场景自适应 BGM 启动
- [x] 35.5 重构 SettingsScreen 的音量控制按钮，将 `pygame.mixer.music.set_volume` 委托给 AudioManager，并同步 SFX 音量
- [x] 35.6 编写单元测试 `tests/test_audio_manager.py` 验证去重、音量、切换与无混音器安全性
- [x] 35.7 运行验证所有测试（212 项全通过），更新看板并归档任务

### 第 34 课：角色帧动画系统与多状态精灵切片管理器开发

- [x] 34.1 更新 PLAN.md，加入第 34 课的任务流
- [x] 34.2 编写并实现帧动画及多状态控制器类 `src/animation.py`
- [x] 34.3 升级 `src/tile_renderer.py`，使 `draw_tile()` 中的角色与怪物渲染支持 `Animator` 控制器的当前帧以及矢量退化动效
- [x] 34.4 升级 `src/screens/gameplay_screen.py`，在角色移动、挖掘、受击时切换播放对应动画状态并实时更新
- [x] 34.5 编写单元测试 `tests/test_animation.py` 验证帧率步进、非循环动画终止、状态切换、以及数学弹性兜底矩阵计算
- [x] 34.6 运行验证所有测试（204 项全通过），更新看板并归档任务

### 第 33 课：爆破粒子、浮动文本与屏幕震颤（Game Juice）特效系统开发

- [x] 33.1 更新 PLAN.md，加入第 33 课的任务流
- [x] 33.2 编写并实现独立的动感特效物理引擎模块 `src/effects.py`
- [x] 33.3 升级 `src/screens/gameplay_screen.py`，注册粒子与浮动字管理器，在开掘、爆破、受击和收集事件处触发特效
- [x] 33.4 升级 `src/camera.py`，支持在 Screen Shake 激活时对偏移量进行噪声叠加
- [x] 33.5 编写单元测试 `tests/test_effects.py` 验证粒子的生命衰减、浮动字位移与渐隐、以及屏幕震颤状态递减
- [x] 33.6 运行验证所有测试（196 项全通过），更新看板并归档任务

### 第 32 课：程序化加权掉落表与多级宝箱（普通宝箱/上锁宝箱）机制开发

- [x] 32.1 更新 PLAN.md，加入第 32 课的任务流
- [x] 32.2 编写并实现独立的加权掉落表模块 `src/loot_table.py`
- [x] 32.3 升级 `src/interaction_controller.py`，实现步入普通宝箱开启、点击上锁宝箱钥匙解锁判定以及物资爆出数据流
- [x] 32.4 升级 `src/level_generator.py`，将普通宝箱和上锁宝箱散布至密室卡点，并升级泥土下的道具掉落计算
- [x] 32.5 升级 `src/tile_renderer.py`，支持宝箱与锁宝箱在退化渲染模式下的美观绘制
- [x] 32.6 编写单元测试 `tests/test_loot_and_chests.py` 验证动态救济概率、宝箱步入暴兵、钥匙解锁消耗与大奖产生
- [x] 32.7 运行验证所有测试（181 项全通过），更新看板并归档任务

### 第 31 课：核心测试集除错与生命周期净化（Bug Squash）

- [x] 31.1 更新 PLAN.md，加入第 31 课的任务流
- [x] 31.2 审计 `src/screens/gameplay_screen.py` 中的 `on_enter` 方法，增加 `purge_temporary_items()` 防护性判空校验
- [x] 31.3 审计并修复 `tests/test_gameplay_screen.py` 与 `tests/test_tile_renderer.py` 中因 GameManager 单例未初始化导致的潜在崩溃
- [x] 31.4 运行全局测试 `python -m pytest tests/`，验证整个测试套件实现"100% 绿色、0 失败"
- [x] 31.5 更新看板并归档任务

### 第 30 课：根入口文件（main.py）与引擎启动自检程序开发

- [x] 30.1 更新 PLAN.md，加入第 30 课的任务流
- [x] 30.2 升级 `src/game_manager.py`，实现自举装载序列，在 `init_engine()` 中实例化并注册全部 7 个场景界面，默认切入 `GameState.MAIN_MENU`
- [x] 30.3 在项目根目录下编写全局启动主入口文件 `main.py`，支持环境自检、完整场景注册、自适应初始化、以及顶层崩溃日志转储机制
- [x] 30.4 编写单元集成冒烟测试 `tests/test_main_entry.py` 验证自检机制、所有 GameState 的场景类绑定无一遗漏、以及异常崩溃转储
- [x] 30.5 运行验证所有测试，更新看板并归档任务

### 第 29 课：设置与选项界面开发及音效音量动态调节机制

- [x] 29.1 更新 PLAN.md，加入第 29 课的任务流
- [x] 29.2 升级 `src/config.py`，在 `GameState` 枚举类中追加 `SETTINGS` 状态
- [x] 29.3 升级 `src/asset_manager.py`，使 `get_sound()` 获取的音效能自动应用全局 SFX 音量设置
- [x] 29.4 编写并实现设置选项场景类 `src/screens/settings_screen.py`（含音乐/音效增减、全屏切换与 Back 存盘）
- [x] 29.5 升级 `src/screens/main_menu_screen.py`，接入"选项"跳转按钮并重构排版高度
- [x] 29.6 编写单元测试 `tests/test_settings_screen.py` 验证音量增减阈值控制、存盘序列化、以及状态机顺畅转换
- [x] 29.7 运行验证所有测试（166 项全通过），更新看板并归档任务

### 第 28 课：怪物、武器收集与多级战斗判定开发

- [x] 28.1 更新 PLAN.md，加入第 28 课的任务流
- [x] 28.2 升级 `src/level_generator.py`，支持在程序化地图中合理散落怪物、弓箭与柴刀实体
- [x] 28.3 升级 `src/interaction_controller.py`，实现多级战斗判定方法 `attack_monster()` 并重构移动拦截逻辑
- [x] 28.4 升级 `src/screens/gameplay_screen.py`，在鼠标点击相邻怪物时触发战斗，并在关卡重载时触发跨关武器钥匙清空
- [x] 28.5 编写单元测试 `tests/test_monsters_and_weapons.py` 验证怪物生成比例、柴刀/弓箭击杀、无武器扣血、以及跨关清空
- [x] 28.6 运行验证所有测试（155 项全通过），更新看板并归档任务

### 第 27 课：工作区杂质清理与 Spritesheet 瓦片渲染器（TileRenderer）开发

- [x] 27.1 清理本地项目根目录下所有与本项目无关的冗余文件与文件夹
- [x] 27.2 编写并实现精灵图集切割与瓦片渲染器 `src/tile_renderer.py` 及其 `TileRenderer` 类
- [x] 27.3 升级 `src/screens/gameplay_screen.py` 的渲染方法，接入 `TileRenderer` 实现真实画面渲染代替调试色块
- [x] 27.4 升级 `src/screens/bonus_level_screen.py` 的渲染方法，接入 `TileRenderer` 确保统一
- [x] 27.5 编写单元测试 `tests/test_tile_renderer.py` 验证切片坐标、缺失资产优雅退化渲染、及渲染图层正确性
- [x] 27.6 运行验证所有 141 项测试，更新看板并归档任务

### 第 25 课：游戏结束死亡界面（GameOverScreen）与重生/死亡循环机制开发

- [x] 25.1 更新 PLAN.md，加入第 25 课的任务流
- [x] 25.2 编写并实现死亡结算场景类 `src/screens/game_over_screen.py`
- [x] 25.3 编写单元测试 `tests/test_game_over_screen.py` 验证有无护身符时的分支渲染、时空溯源算法、Rogue-lite 属性继承与重置落盘、以及状态机跳转
- [x] 25.4 运行验证，更新看板并归档任务

### 第 26 课：隐藏奖励关界面（BonusLevelScreen）与倒计时机制开发

- [x] 26.1 更新 PLAN.md，加入第 26 课的任务流
- [x] 26.2 扩展 `GameManager`，支持暂存/恢复主关卡数据的挂起字段 `suspended_level_state`
- [x] 26.3 升级 `src/screens/gameplay_screen.py`，实现踩楼梯时挂起现场并切换至 `GameState.BONUS_LEVEL`，以及从奖励关返回时的现场复原恢复逻辑
- [x] 26.4 编写并实现隐藏奖励关场景类 `src/screens/bonus_level_screen.py`（含 30秒倒计时、无伤踩雷退场、四叶草赋予等）
- [x] 26.5 编写单元测试 `tests/test_bonus_level_screen.py` 验证挂起恢复、进入满血、倒计时自动结算、踩雷无伤退场及四叶草加倍赋予
- [x] 26.6 运行验证，更新看板并归档任务

### 第 24 课：贪婪木乃伊商店界面（MummyShopScreen）开发

- [x] 24.1 更新 PLAN.md，加入第 24 课的任务流
- [x] 24.2 编写并实现商店场景类 `src/screens/mummy_shop_screen.py`
- [x] 24.3 编写单元测试 `tests/test_mummy_shop_screen.py` 验证商品列表渲染、购买约束判定、金币扣除、自动存盘及离开路由跳转
- [x] 24.4 运行验证，更新看板并归档任务

### 第 23 课：关卡通过结算界面（LevelCompleteScreen）开发

- [x] 23.1 更新 PLAN.md，加入第 23 课的任务流
- [x] 23.2 将 `Button` 类从主菜单模块重构提取至新建的 `src/ui_helpers.py` 中，并使主菜单引用该模块
- [x] 23.3 编写并实现关卡结算场景类 `src/screens/level_complete_screen.py`
- [x] 23.4 编写单元测试 `tests/test_level_complete_screen.py` 验证结算显示、自动保存及下一关/商店智能路由跳转
- [x] 23.5 运行验证，更新看板并归档任务

### 第 22 课：主动工具（炸药、地图）业务逻辑与交互动作实现

- [x] 22.1 更新 PLAN.md，加入第 22 课的任务流
- [x] 22.2 在 `src/interaction_controller.py` 中编写并实现 `use_dynamite()` 与 `use_map()` 核心业务算法
- [x] 22.3 在 `src/screens/gameplay_screen.py` 中引入输入模式机制，拦截键盘按键 B/M/2/3 触发爆破与扫描交互
- [x] 22.4 编写单元测试 `tests/test_active_tools.py` 验证炸药 3x3 无伤清扫、地图 5x5 自动插旗以及输入状态机转换
- [x] 22.5 运行验证，更新看板并归档任务

### 第 21 课：顶部 HUD 状态栏数据渲染开发

- [x] 21.1 更新 PLAN.md，加入第 21 课的任务流
- [x] 21.2 编写并实现 `src/hud.py` 状态栏渲染类
- [x] 21.3 在 `src/screens/gameplay_screen.py` 中引入并实例化渲染 HUD
- [x] 21.4 编写单元测试 `tests/test_hud.py` 验证 HUD 数值绑定、降级文本渲染
- [x] 21.5 运行验证，更新看板并归档任务

### 第 20 课：核心游戏探索界面（GameplayScreen）基础骨架与平滑摄像机控制开发

### 第 20 课：核心游戏探索界面（GameplayScreen）基础骨架与平滑摄像机控制开发

- [x] 20.1 更新 PLAN.md，加入第 20 课的任务流
- [x] 20.2 在 `src/camera.py` 中编写平滑随动与裁剪摄像机类 `Camera`
- [x] 20.3 编写核心探索界面 `src/screens/gameplay_screen.py`，集成地图、控制器、摄像机与按键监听
- [x] 20.4 编写单元测试 `tests/test_gameplay_screen.py` 验证地图初始化、摄像机追踪裁剪与点击还原
- [x] 20.5 运行验证，更新看板并归档任务

### 第 19 课：游戏主菜单界面（MainMenuScreen）开发与音效串联

- [x] 19.1 更新 PLAN.md，加入第 19 课的任务流
- [x] 19.2 编写主菜单按钮辅助类 `Button` 并实现主菜单界面 `src/screens/main_menu_screen.py`
- [x] 19.3 编写单元测试 `tests/test_main_menu_screen.py` 验证按钮悬停、点击反馈、音效调用和场景切换
- [x] 19.4 运行验证，更新看板并归档任务

### 第 18 课：全局游戏管理器（GameManager）与多屏幕基础架构开发

- [x] 18.1 更新 PLAN.md，加入第 18 课的任务流
- [x] 18.2 编写并实现屏幕生命周期基类 `src/screens/base_screen.py`
- [x] 18.3 编写并实现多屏幕管理器 `src/screen_manager.py`
- [x] 18.4 编写并实现全局主控游戏管理器 `src/game_manager.py`
- [x] 18.5 编写单元测试 `tests/test_game_manager.py` 验证屏幕生命周期、状态机流转与 dt 计算
- [x] 18.6 运行验证，更新看板并归档任务

### 第 17 课：程序化关卡生成引擎（LevelGenerator）与可解性验证开发

- [x] 17.1 更新 PLAN.md，加入第 17 课的任务流
- [x] 17.2 编写并实现关卡生成引擎 `src/level_generator.py` 及其 `LevelGenerator` 类
- [x] 17.3 编写单元测试 `tests/test_level_generator.py` 验证参数随关卡缩放、雷区生成与可解性求解器
- [x] 17.4 运行验证，更新看板并归档任务

### 第 16 课：核心交互逻辑与扫雷连锁开掘（Flood Fill / Chording）控制器开发

- [x] 16.1 更新 PLAN.md，加入第 16 课的任务流
- [x] 16.2 编写并实现交互控制器模块 `src/interaction_controller.py`
- [x] 16.3 编写单元测试 `tests/test_interaction_controller.py` 验证开掘、连锁消除、双击连开、障碍移除与步入收集
- [x] 16.4 运行验证，更新看板并归档任务

### 第 15 课：地图核心数据模型与多层网格数据结构开发

- [x] 15.1 更新 PLAN.md，加入第 15 课的任务流
- [x] 15.2 编写并实现地图核心模型 `src/map_data.py` 及其多层数据管理类 `GameMap`
- [x] 15.3 编写单元测试 `tests/test_map_data.py` 验证网格越界、邻域雷数计算、通行判定与红旗标记
- [x] 15.4 运行验证，更新看板并归档任务

### 第 14 课：集中式资产管理器（AssetManager）开发与无损退化机制实现

- [x] 14.1 更新 PLAN.md，加入第 14 课的任务流
- [x] 14.2 编写并实现资产管理器类 `src/asset_manager.py` 与空置声音类 `DummySound`
- [x] 14.3 编写单元测试 `tests/test_asset_manager.py` 验证懒加载、缓存与优雅退化降级机制
- [x] 14.4 运行验证，更新看板并归档任务

### 第 13 课：本地存档管理器（SaveManager）开发

- [x] 13.1 更新 PLAN.md，加入第 13 课的任务流
- [x] 13.2 编写并实现本地安全存档模块 `src/save_manager.py`
- [x] 13.3 编写单元测试 `tests/test_save_manager.py` 验证原子写、备份恢复与哈希校验
- [x] 13.4 运行验证，更新看板并归档任务

### 第 12 课：玩家状态（生命值、背包工具、经济）核心数据模型开发

- [x] 12.1 更新 PLAN.md，加入第 12 课的任务流
- [x] 12.2 编写并实现玩家状态管理模块 `src/player_state.py`
- [x] 12.3 编写单元测试或脚本验证 `PlayerState` 的数值、扣减、升级与重置规则
- [x] 12.4 运行验证，更新看板并归档任务

### 第 11 课：初始化项目基础环境与全局配置文件

- [x] 11.1 更新 PLAN.md，加入第 11 课的任务流
- [x] 11.2 创建项目的 .gitignore 配置文件
- [x] 11.3 规划并创建基础目录结构（src/ 与 assets/）
- [x] 11.4 编写并实现全局常量与配置文件 src/config.py
- [x] 11.5 验证新创建的文件与结构

### 第 1 课：核心玩法与胜败判定规范设计

- [x] 1.1 初始化根目录下的 `PLAN.md`
- [x] 1.2 在 `docs/01_core_gameplay.md` 中编写"核心玩法与胜败判定规范设计"
- [x] 1.3 验证文档结构并输出文件树与规范摘要

### 第 2 课：红心、护盾与伤害机制规范设计

- [x] 2.1 更新 PLAN.md，加入第 2 课的任务流
- [x] 2.2 在 `docs/02_hearts_and_shields.md` 中编写红心与护盾机制规范
- [x] 2.3 验证并更新看板，归档任务

### 第 3 课：地图交互元素、障碍物与钥匙/门机制规范设计

- [x] 3.1 更新 PLAN.md，加入第 3 课的任务流
- [x] 3.2 在 `docs/03_interactive_elements.md` 中编写地图交互元素与钥匙/门机制规范
- [x] 3.3 验证并更新看板，归档任务

### 第 4 课：工具道具使用逻辑与背包/经济系统规范设计

- [x] 4.1 更新 PLAN.md，加入第 4 课的任务流
- [x] 4.2 在 `docs/04_tools_and_economy.md` 中编写工具逻辑、背包与经济系统规范
- [x] 4.3 验证并更新看板，归档任务

### 第 5 课：贪婪木乃伊商店与复活护身符机制规范设计

- [x] 5.1 更新 PLAN.md，加入第 5 课的任务流
- [x] 5.2 在 `docs/05_mummy_shop_and_amulet.md` 中编写商店与复活机制规范
- [x] 5.3 验证并更新看板，归档任务

### 第 6 课：程序化地图生成与可解性验证算法规范设计

- [x] 6.1 更新 PLAN.md，加入第 6 课的任务流
- [x] 6.2 在 `docs/06_map_generation.md` 中编写程序化地图生成与可解性验证规范
- [x] 6.3 验证文档结构并输出文件树与规范摘要

### 第 7 课：怪物与武器系统规范设计

- [x] 7.1 更新 PLAN.md，加入第 7 课的任务流
- [x] 7.2 在 `docs/07_monsters_and_weapons.md` 中编写怪物与武器机制规范
- [x] 7.3 验证并更新看板，归档任务

### 第 8 课：地下秘道、隐藏奖励关与幸运四叶草双倍收益机制规范设计

- [x] 8.1 更新 PLAN.md，加入第 8 课的任务流
- [x] 8.2 在 `docs/08_bonus_levels_and_clover.md` 中编写奖励关与四叶草机制规范
- [x] 8.3 验证并更新看板，归档任务

### 第 9 课：全局 UI 布局、摄像机视口裁剪与多屏幕管理器设计规范

- [x] 9.1 更新 PLAN.md，加入第 9 课的任务流
- [x] 9.2 在 `docs/09_ui_layout_and_screens.md` 中编写全局 UI 与多屏幕管理器规范
- [x] 9.3 验证并更新看板，归档任务

### 第 10 课：全局软件架构、主循环与资产管理器设计规范

- [x] 10.1 更新 PLAN.md，加入第 10 课的任务流
- [x] 10.2 在 `docs/10_global_architecture.md` 中编写全局架构、主循环与资产管理器规范
- [x] 10.3 验证并更新看板，归档任务

---

## 课程总览

| 课号 | 标题 | 状态 |
|------|------|------|
| 第 1 课 | 核心玩法与胜败判定规范设计 | ✅ 已完成 |
| 第 2 课 | 红心、护盾与伤害机制规范设计 | ✅ 已完成 |
| 第 3 课 | 地图交互元素、障碍物与钥匙/门机制规范设计 | ✅ 已完成 |
| 第 4 课 | 工具道具使用逻辑与背包/经济系统规范设计 | ✅ 已完成 |
| 第 5 课 | 贪婪木乃伊商店与复活护身符机制规范设计 | ✅ 已完成 |
| 第 6 课 | 程序化地图生成与可解性验证算法规范设计 | ✅ 已完成 |
| 第 7 课 | 怪物与武器系统规范设计 | ✅ 已完成 |
| 第 8 课 | 地下秘道、隐藏奖励关与幸运四叶草双倍收益机制规范设计 | ✅ 已完成 |
| 第 9 课 | 全局 UI 布局、摄像机视口裁剪与多屏幕管理器设计规范 | ✅ 已完成 |
| 第 10 课 | 全局软件架构、主循环与资产管理器设计规范 | ✅ 已完成 |
| 第 11 课 | 初始化项目基础环境与全局配置文件 | ✅ 已完成 |
| 第 12 课 | 玩家状态（生命值、背包工具、经济）核心数据模型开发 | ✅ 已完成 |
| 第 13 课 | 本地存档管理器（SaveManager）开发 | ✅ 已完成 |
| 第 14 课 | 集中式资产管理器（AssetManager）开发与无损退化机制实现 | ✅ 已完成 |
| 第 15 课 | 地图核心数据模型与多层网格数据结构开发 | ✅ 已完成 |
| 第 16 课 | 核心交互逻辑与扫雷连锁开掘（Flood Fill / Chording）控制器开发 | ✅ 已完成 |
| 第 17 课 | 程序化关卡生成引擎（LevelGenerator）与可解性验证开发 | ✅ 已完成 |
| 第 18 课 | 全局游戏管理器（GameManager）与多屏幕基础架构开发 | ✅ 已完成 |
| 第 19 课 | 游戏主菜单界面（MainMenuScreen）开发与音效串联 | ✅ 已完成 |
| 第 20 课 | 核心游戏探索界面（GameplayScreen）基础骨架与平滑摄像机控制开发 | ✅ 已完成 |
| 第 21 课 | 顶部 HUD 状态栏数据渲染开发 | ✅ 已完成 |
| 第 22 课 | 主动工具（炸药、地图）业务逻辑与交互动作实现 | ✅ 已完成 |
| 第 23 课 | 关卡通过结算界面（LevelCompleteScreen）开发 | ✅ 已完成 |
| 第 24 课 | 贪婪木乃伊商店界面（MummyShopScreen）开发 | ✅ 已完成 |
| 第 25 课 | 游戏结束死亡界面（GameOverScreen）与重生/死亡循环机制开发 | ✅ 已完成 |
| 第 26 课 | 隐藏奖励关界面（BonusLevelScreen）与倒计时机制开发 | ✅ 已完成 |
| 第 27 课 | 工作区杂质清理与 Spritesheet 瓦片渲染器（TileRenderer）开发 | ✅ 已完成 |
| 第 28 课 | 怪物、武器收集与多级战斗判定开发 | ✅ 已完成 |
| 第 29 课 | 设置与选项界面开发及音效音量动态调节机制 | ✅ 已完成 |
| 第 30 课 | 根入口文件（main.py）与引擎启动自检程序开发 | ✅ 已完成 |
| 第 31 课 | 核心测试集除错与生命周期净化（Bug Squash） | ✅ 已完成 |
| 第 32 课 | 程序化加权掉落表与多级宝箱（普通宝箱/上锁宝箱）机制开发 | ✅ 已完成 |
| 第 33 课 | 爆破粒子、浮动文本与屏幕震颤（Game Juice）特效系统开发 | ✅ 已完成 |
| 第 34 课 | 角色帧动画系统与多状态精灵切片管理器开发 | ✅ 已完成 |
| 第 35 课 | 全局音频管理器与场景自适应 BGM 切换 | ✅ 已完成 |
| 第 36 课 | 多环境地貌（Biomes）色彩与主题自适应渲染引擎开发 | ✅ 已完成 |
| 第 37 课 | 玩法指南与控制键位蒙层（HelpOverlay）开发与游戏内时停暂停机制实现 | ✅ 已完成 |
| 第 38 课 | 实时小地图（Minimap）系统开发 | ✅ 已完成 |
| 第 39 ~ 59 课 | 待定 | ⬜ 未开始 |
| 第 60 课 | 待定 | ⬜ 未开始 |
