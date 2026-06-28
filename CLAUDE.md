# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Microsoft Treasure Hunt — a Pygame-based fan remake of the classic Minesweeper-adventure hybrid. Players navigate a procedurally generated grid, dig tiles, avoid traps, collect gold/tools/keys, fight monsters, and progress through levels with permadeath (Rogue-lite) mechanics.

**Progress**: 25 of 60 planned development lessons complete (see `PLAN.md` for full kanban in Chinese).

## Commands

```powershell
# Run all tests
python -m pytest tests/

# Run a single test file directly (assert-based, no pytest needed)
python tests/test_player_state.py

# Run a single test file with pytest verbose
python -m pytest tests/test_interaction_controller.py -v

# Run with coverage
python -m pytest tests/ --cov=src

# Install runtime dependency
pip install pygame

# Install test dependency
pip install pytest
```

**Note**: No `main.py` entry point exists yet. The game is launched via `GameManager.get_instance().run()` — currently only runnable through tests.

## Dependencies

- **Runtime**: `pygame` (no pinned version)
- **Testing**: `pytest` (no pinned version)
- No `pyproject.toml`, `setup.py`, or `requirements.txt` yet

## Architecture

### Four-Layer Design (docs/10_global_architecture.md)

| Layer | Name | Responsibility |
|-------|------|---------------|
| 0 | Foundation | pygame init, display surface, OS integration |
| 1 | Engine | AssetManager, SaveManager, main loop, event dispatch |
| 2 | Game Logic | InteractionController, LevelGenerator, PlayerState, map systems |
| 3 | UI/Presentation | ScreenManager, Camera, HUD, screen rendering |

Communication is strictly top-down. Layer 3 cannot directly access Layer 1 — all cross-layer calls go through GameManager.

### Key Modules & Patterns

| Module | Pattern | Role |
|--------|---------|------|
| `src/game_manager.py` | Singleton | Top-level orchestrator holding all subsystem references; manages the main loop (dt-clamped event → update → render) |
| `src/screen_manager.py` | State machine | Switches between screens via `GameState` enum; lifecycle hooks `on_enter`/`on_exit` |
| `src/screens/base_screen.py` | Abstract base | Interface contract for all screen classes |
| `src/asset_manager.py` | Singleton | Lazy-loads images/sounds/fonts with graceful degradation (placeholder surfaces on failure) |
| `src/save_manager.py` | Static utility | Atomic JSON writes, SHA256 checksum, `.bak` fallback, version migration |
| `src/player_state.py` | Data model | Hearts, shields, gold, tool inventory, keys, permanent upgrades, bag tiers |
| `src/map_data.py` | Data model | 5-layer grid: `terrain`, `obstacles`, `entities`, `traps`, `flags` |
| `src/interaction_controller.py` | Service | Uncover tile, flood fill, chording, obstacle interaction, player movement, dynamite (3×3 blast), map (5×5 scan) |
| `src/level_generator.py` | Service | 3-phase procedural generation: Prim maze → lock-key dependency → trap/entity scatter; includes BFS solvability verification |
| `src/camera.py` | Component | Smooth Lerp-follow camera with boundary clamping and viewport culling |
| `src/hud.py` | Component | Top status bar rendering (hearts, shields, gold, level, tools, keys, weapons, buffs) with graceful text fallback |
| `src/ui_helpers.py` | Component | Shared `Button` class (hover detection, click callback) |

### Game State Machine

```
MAIN_MENU → PLAYING → LEVEL_COMPLETE → MUMMY_SHOP → PLAYING (loop)
                ↓                                      ↓
           GAME_OVER (amulet revive → PLAYING)    GAME_OVER (no amulet → MAIN_MENU)
```

### Project Structure

```
src/
├── screens/          # Screen classes (BaseScreen, MainMenu, Gameplay, LevelComplete, MummyShop, GameOver)
├── config.py         # Constants, enums, color definitions
├── game_manager.py   # Singleton orchestrator + main loop
├── screen_manager.py # Screen state machine
├── player_state.py   # Player data model
├── save_manager.py   # JSON save/load with atomic writes
├── asset_manager.py  # Asset loading with graceful degradation
├── map_data.py       # 5-layer grid data model
├── interaction_controller.py  # Core interaction logic
├── level_generator.py         # Procedural level generation
├── camera.py         # Smooth camera with viewport culling
├── hud.py            # Top HUD status bar
└── ui_helpers.py     # Shared Button component

tests/                # 14 test files, one per source module
docs/                 # Design specs for lessons 1-10 (game design documents)
```

### Notable Conventions

- **No main.py**: The project lacks a launch entry point. `GameManager.get_instance().run()` is the intended call. Tests initialize via `GameManager.get_instance().init_engine(headless=True)`.
- **Sys.path manipulation**: Every source file inserts `src/` into `sys.path` at the top to allow running from any working directory. Every test file does the same for the project root.
- **Lazy imports**: Screen files import `GameManager` inside `on_enter()` methods to avoid circular imports.
- **No `assets/` directory**: AssetManager expects `assets/images/`, `assets/sounds/`, `assets/fonts/` but none exist — all loading degrades gracefully to placeholders.
- **Doc-driven development**: Design specs in `docs/` serve as living contracts. Lessons 1-10 are design docs; lessons 11+ implement them.
- **Two-tier testing**: All test files can run standalone via `python tests/test_*.py` (manual `sys.path` setup) or via `pytest`.
- **PLAN.md**: Project kanban in Chinese tracking 60 lessons; update after completing each lesson.
