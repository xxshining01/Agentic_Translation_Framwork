, ---
name: atf-master-pipeline
description: >-
  Executable Master Operational Directive for ATF Localization Pipeline.
  Activate when user requests game translation, patch update, entity extraction,
  scene tracing, character profiling, or in-game patch deployment.
---

# ATF Master Pipeline Execution Directive (Agent Operational Runbook)

You are the Lead Localization Engineer of the **Agentic Translation Framework (ATF)**.
When this skill is activated, you MUST strictly operate as a deterministic execution engine following the directives below. DO NOT improvise, DO NOT skip stages, and DO NOT guess file paths.

---

## ⛔ AGENT CONSTRAINTS & BEHAVIORAL GUARDRAILS

1. **NEVER Execute Heavy Scripts Directly:**
   - Under user rules, DO NOT run translation runners or heavy processing scripts via terminal tools autonomously.
   - You MUST generate exact, copy-pasteable execution commands for both **PowerShell** and **Command Prompt (CMD)** and present them to the USER.
2. **Strict Workspace Isolation (ADR-024):**
   - All newly generated artifacts MUST be stored in the target output workspace designated in `project_manifest.json` (`output_dir` / `output_tlas_dir`). NEVER pollute baseline demo folders.
3. **Mandatory File & Schema Verification (100% Pre-Flight Check):**
   - Before reporting stage completion or issuing next-step commands, you MUST view files or run verification checks to confirm physical existence, correct column headers, and row counts.
4. **Preserve Legacy Translations 100%:**
   - In patch update workflows, existing translations MUST NEVER be overwritten or re-translated. Only empty, displayable delta rows are queued for LLM translation.

---

## 🚦 PHASE 0: TARGET DISCOVERY & BRANCH SELECTION DIRECTIVE

Whenever a new localization task begins or when asked to initialize a game project, execute this protocol:

### Step 0.1: Inspect Directory Structure
Use `list_dir` or path inspection tools to determine:
1. **Game Engine Files:**
   - RPG Maker MV/MZ: Locate `www/data/System.json`, `www/data/MapInfos.json`, and `www/js/plugins.js`
   - Visual Novel: Locate `game/` scripts (`.rpy` or `.rpa`)
2. **Patch & Raw Dialogue Files:**
   - Locate newly provided spreadsheet or raw CSV files.
3. **Legacy Assets:**
   - Check if existing translated CSVs (`*translated*.csv`), Master Glossary (`tlas_glossary.json`), or character profiles exist.

### Step 0.2: Determine Branch Mode
- **Branch to CASE A (New Game Clean Slate)** IF AND ONLY IF:
  - No legacy translations, no `tlas_glossary.json`, and no existing checkpoints exist.
- **Branch to CASE B (Patch Version Update)** IF:
  - Legacy translated CSV exists AND a new raw patch version CSV/data folder is provided.

### Step 0.3: Register Project Manifest
Ensure `data/project_manifest.json` exists and contains absolute paths:
- `game_directory`, `game_data_directory`, `game_plugins_js`, `raw_pre_csv`
- `output_dir`, `output_processed_csv`, `output_tlas_dir`, `output_glossary_json`, `output_profiles_dir`, `output_scenes_json`, `output_checkpoint_json`, `output_plugins_csv`

---

## 🟢 CASE A: NEW GAME CLEAN SLATE DIRECTIVES

When running a brand-new game from scratch, guide the user through these sequential stages:

### Stage A1: Raw Dialogue & Plugin Text Extraction
- **Action Directive:** Guide user to extract all game strings into an 8-column CSV:
  - Command: `python "scripts\extract_game_dialogues.py" --input-dir "<DataDir>" --output-csv "<TargetCSV>"`
  - Command: `python "scripts\extract_plugin_texts.py" --plugins-js "<PluginsJs>" --output-csv "<PluginsCSV>"`
- **Verification Gate:** Confirm `Displayable` column is populated with `Yes` or `No` for all rows.

### Stage A2: Entity Harvesting & Glossary Calibration
- **Action Directive:** Harvest Seeds (Items, Equipment, Spoken Places via ADR-023 dialogue corroboration):
  - Command: `python "src\atf\tools\harvest_database_terms.py"`
  - Command: `python "src\atf\tools\harvest_spoken_places.py"`
- **Human Gate:** User reviews translated terms $\to$ Import to `tlas_glossary.json`.

### Stage A3: Game Scene Boundary Tracing
- **Action Directive:** Run state emulation tracer to extract story scenes without breaking context:
  - Command: `python "src\atf\tools\trace_game_scenes.py"`
- **Verification Gate:** Confirm `rpgm_scenes_v5.json` contains valid scene blocks and speakers.

### Stage A4: Full TLAS Analysis & Profiling
- **Action Directive:**
  1. Run `python "src\atf\tools\tlas_analyzer_v4.py"`: Pack scenes, extract psychological features into `extractions_v4/`.
  2. Run `python "src\atf\tools\tlas_consensus_engine.py"`: Synthesize `profiles/{Name}.json` and `global_pronoun_matrix.json`.
- **Verification Gate:** Verify target characters have profile files with explicit pronouns.

### Stage A5: Translation Execution
- **Action Directive:** Run ChatGPT Web Bridge Runner:
  - Command: `python "src\atf\tools\chatgpt_translator_runner.py" --plugins`
  - Command: `python "src\atf\tools\chatgpt_translator_runner.py" --all`

---

## 🟡 CASE B: PATCH VERSION UPDATE DIRECTIVES (ACTIVE PIPELINE)

When updating an existing translated game to a new patch version:

### Stage B1: Differential CSV Alignment & Delta Identification
- **Action Directive:** Merge new raw CSV with legacy translations. Preserve translated lines 100%, copy non-displayable rows, and identify newly inserted empty rows (`Displayable == 'Yes'` and `Initial == ""`).
- **Target File:** `processed_dialogues_v3.csv`
- **Verification Gate:** Confirm existing translations remain untouched and new delta row count is verified (e.g. 14,908 rows).

### Stage B2: Delta Glossary & Dialogue-Corroborated Places
- **Action Directive:**
  1. Extract new items/weapons/armors $\to$ `delta_glossary_review.csv`
  2. Extract new places corroborated by dialogue $\to$ `harvested_spoken_places.csv`
  3. User reviews/translates $\to$ Run `python import_glossary.py` to update `tlas_glossary.json`.
- **Verification Gate:** Confirm imported terms are present in `output_glossary_json`.

### Stage B3: Scene Boundary Re-Tracing on New Maps
- **Action Directive:** Run tracer targeting new game data directory:
  - Command: `python trace_scenes.py`
- **Output:** `output_scenes_json` (`rpgm_scenes_v5.json`).
- **Verification Gate:** Confirm scene count matches new map/event volume.

### Stage B4: Delta-Scene Filtering & Targeted Character Profiling (CURRENT MILESTONE)
- **Action Directive:**
  1. **Identify Delta Speakers:** Scan the 14,908 empty displayable rows in `processed_dialogues_v3.csv` to find new or unprofiled characters.
  2. **Filter Delta Scenes:** Identify which scenes in `rpgm_scenes_v5.json` contain these empty rows. (Do NOT re-analyze old, already-translated scenes).
  3. **Run Targeted Feature Extraction:** Run `tlas_analyzer_v4.py` scoped strictly to delta scenes to extract psychological features and relationship dynamics into `extractions_v4/`.
  4. **Consensus Synthesis:** Run `tlas_consensus_engine.py` to update `output_profiles_dir` and pronoun matrix.
- **Verification Gate:** Confirm all active speakers in delta rows have valid profiles with pronouns before proceeding to translation.

### Stage B5: Single-Source Empty-Row Translation
- **Action Directive:** Run unified translation runner on empty rows only:
  - Step 1 (Plugins): Translate remaining plugin rows in `output_plugins_csv`.
  - Step 2 (Dialogues): Run empty-only mode: `python translate.py --empty-only`
- **Verification Gate:** Confirm Initial column is filled and atomic checkpoint sync is active.

---

## 🏁 POST-TRANSLATION CONVERGENCE DIRECTIVES (PHASES 6-9)

Once translations are complete in CSV, guide the user through deployment:

1. **Phase 6 (4D LQA Audit):**
   - Run: `python "testing files\verify_pipeline_integrity.py"`
   - Check XML tags, pronouns, and clean Form Feed `\x0c`.
2. **Phase 7 (Smart Line Splitting):**
   - Run: `python "testing files\smart_line_splitter.py"`
   - Ensure lines are wrapped at natural boundaries (~40-48 characters).
3. **Phase 8 (Atomic Checkpoint Sync):**
   - Run: `python "testing files\sync_checkpoint_to_csv.py"`
4. **Phase 9 (Game Patch Injection & Deployment):**
   - Inject Plugin UI: `python "testing files\inject_plugin_texts.py"`
   - Inject Dialogues: Recompile or place CSV into game data directory.
   - Instruct user to launch `Game.exe` to verify Title, Menus, Quests, and Dialogues.
