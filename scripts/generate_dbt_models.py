"""
generate_dbt_models.py  (v2 — registry-based)
─────────────────────────────────────────────
Generates dbt SQL + YML from mapping sheets with persistent memory.

Key features:
  1. SKILL        — skills/dbt_skill.md injected into every prompt (house style)
  2. REGISTRY     — dbt/registry.json remembers every entity ever generated:
                    layer, file, mapping hash, inputs, output columns.
  3. SKIP         — unchanged mapping hash → no LLM call at all
  4. UPDATE MODE  — changed mapping → LLM gets the PREVIOUS SQL and is asked
                    to surgically update it, not regenerate from scratch
  5. CROSS-RUN REFS — a new entity whose input is a model built in a past
                    run (even from a different mapping file) gets ref()'d
                    with its known output columns
  6. LAYERS       — optional "Layer" column in the sheet wins; otherwise the
                    layer is inferred from dependencies (no prefix sniffing)
  7. SOURCES.YML  — registry-managed; regenerated only when new raw tables
                    appear, always containing the full known set
"""

import requests
import json
import os
import time
import hashlib
import datetime
import pandas as pd
from pathlib import Path
from collections import defaultdict
from requests.exceptions import ChunkedEncodingError, ConnectionError, Timeout, RequestException

# ── Config ────────────────────────────────────────────────────────────
INVOKE_URL          = os.environ.get("INVOKE_URL", "https://integrate.api.nvidia.com/v1/chat/completions")
API_KEY             = os.environ.get("API_KEY", "")
MAPPING_DIR         = Path("mapping")
DBT_MODELS_DIR      = Path("dbt/models/bigquery")
REGISTRY_PATH       = Path("dbt/registry.json")
SKILL_PATH          = Path("skills/dbt_skill.md")
DELAY_BETWEEN_CALLS = 20
MAX_RETRIES         = 5
TIMEOUT             = (10, 300)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "text/event-stream"
}

NULLISH = ("nan", "derived", "n/a", "na", "none", "")


# ─────────────────────────────────────────────────────────────────────
# Registry — persistent memory across runs (committed to git)
# ─────────────────────────────────────────────────────────────────────
def load_registry() -> dict:
    if REGISTRY_PATH.exists():
        reg = json.loads(REGISTRY_PATH.read_text())
    else:
        reg = {}
    reg.setdefault("entities", {})
    reg.setdefault("raw_tables", {})
    return reg


def save_registry(reg: dict):
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2, sort_keys=True))
    print(f"Registry saved: {REGISTRY_PATH}")


def load_skill() -> str:
    if SKILL_PATH.exists():
        return SKILL_PATH.read_text()
    print(f"WARNING: skill file not found at {SKILL_PATH} — proceeding without it")
    return ""


# ─────────────────────────────────────────────────────────────────────
# Mapping sheet parsing
# ─────────────────────────────────────────────────────────────────────
def find_col(df: pd.DataFrame, *keywords) -> str | None:
    """Find first column whose name contains ALL keywords (case-insensitive)."""
    for c in df.columns:
        cl = c.lower()
        if all(k in cl for k in keywords):
            return c
    return None


def sheet_hash(df: pd.DataFrame) -> str:
    """Stable content fingerprint of a mapping sheet."""
    normalized = df.fillna("").astype(str).to_csv(index=False)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def parse_mapping_file(mapping_file: Path) -> dict:
    """
    Parse every sheet into:
      { entity_name: {
          df, hash, mapping_text,
          inputs: set of lowercase source-table values,
          target_columns: [...],
          layer_override: str | None
      }}
    """
    xl = pd.ExcelFile(mapping_file)
    entities = {}

    for sheet in xl.sheet_names:
        name = sheet.strip()
        df = xl.parse(sheet)

        src_col   = find_col(df, "source", "table")
        tgt_col   = find_col(df, "target", "column") or find_col(df, "column")
        layer_col = find_col(df, "layer")

        inputs = set()
        if src_col:
            inputs = {
                str(v).strip().lower()
                for v in df[src_col].dropna().unique()
                if str(v).strip().lower() not in NULLISH
            }

        target_columns = []
        if tgt_col:
            target_columns = [
                str(v).strip()
                for v in df[tgt_col].dropna()
                if str(v).strip().lower() not in NULLISH
            ]

        layer_override = None
        if layer_col:
            vals = {
                str(v).strip().lower()
                for v in df[layer_col].dropna().unique()
                if str(v).strip().lower() not in NULLISH
            }
            valid = vals & {"staging", "intermediate", "marts"}
            if valid:
                layer_override = sorted(valid)[0]

        entities[name] = {
            "df": df,
            "hash": sheet_hash(df),
            "mapping_text": df.to_string(index=False),
            "inputs": inputs,
            "target_columns": target_columns,
            "layer_override": layer_override,
            "mapping_file": str(mapping_file),
        }

    return entities


# ─────────────────────────────────────────────────────────────────────
# Input classification: raw table vs model (current run or registry)
# ─────────────────────────────────────────────────────────────────────
def classify_inputs(entity_inputs: set, current_entities: dict, registry: dict):
    """
    For each input table name, decide:
      - model in current run        → ref (will exist after this run)
      - model in registry           → ref (built in a previous run)
      - otherwise                   → raw source table
    Returns (raw_inputs: list, ref_inputs: dict {input_name: model_name})
    """
    current_lower  = {e.lower(): e for e in current_entities}
    registry_lower = {e.lower(): e for e in registry["entities"]}

    raw_inputs, ref_inputs = [], {}
    for inp in sorted(entity_inputs):
        if inp in current_lower:
            ref_inputs[inp] = current_lower[inp]
        elif inp in registry_lower:
            ref_inputs[inp] = registry_lower[inp]
        else:
            raw_inputs.append(inp)
    return raw_inputs, ref_inputs


# ─────────────────────────────────────────────────────────────────────
# Layer: override column wins; else dependency inference; registry
# value is sticky (an entity never silently moves folders)
# ─────────────────────────────────────────────────────────────────────
def infer_layers(current_entities: dict, registry: dict) -> dict:
    """
    Returns {entity_name: layer}.

    Priority:
      1. Registry (sticky — already assigned in a past run)
      2. "Layer" column override in the sheet
      3. Dependency inference:
         - reads only raw tables                 → staging
         - reads models, consumed by others      → intermediate
         - reads models, terminal (no consumers) → marts
    """
    layers = {}

    # who consumes whom (within current run + registry refs)
    consumed_by = defaultdict(set)
    for name, ent in current_entities.items():
        _, refs = classify_inputs(ent["inputs"], current_entities, registry)
        for model in refs.values():
            consumed_by[model.lower()].add(name)

    for name, ent in current_entities.items():
        reg_entry = registry["entities"].get(name)

        if reg_entry and reg_entry.get("layer"):
            layers[name] = reg_entry["layer"]          # sticky
        elif ent["layer_override"]:
            layers[name] = ent["layer_override"]       # sheet override
        else:
            raw, refs = classify_inputs(ent["inputs"], current_entities, registry)
            if not refs:
                layers[name] = "staging"
            elif consumed_by.get(name.lower()):
                layers[name] = "intermediate"
            else:
                layers[name] = "marts"

    return layers


# ─────────────────────────────────────────────────────────────────────
# Topological sort — dependencies built before dependents.
# Registry entities count as already satisfied.
# ─────────────────────────────────────────────────────────────────────
def topo_sort(current_entities: dict, registry: dict) -> list:
    names = list(current_entities.keys())
    name_lower = {n.lower(): n for n in names}

    deps = {}
    for name, ent in current_entities.items():
        _, refs = classify_inputs(ent["inputs"], current_entities, registry)
        # only dependencies that are in THIS run matter for ordering
        deps[name] = {
            name_lower[m.lower()]
            for m in refs.values()
            if m.lower() in name_lower and m.lower() != name.lower()
        }

    ordered, placed = [], set()
    remaining = dict(deps)
    while remaining:
        ready = sorted(n for n, d in remaining.items() if d <= placed)
        if not ready:
            # cycle — fall back to alphabetical to avoid infinite loop
            print(f"WARNING: dependency cycle among {list(remaining)} — using alphabetical order")
            ordered.extend(sorted(remaining))
            break
        for n in ready:
            ordered.append(n)
            placed.add(n)
            del remaining[n]
    return ordered


# ─────────────────────────────────────────────────────────────────────
# LLM call with retry
# ─────────────────────────────────────────────────────────────────────
def call_llm(prompt: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            payload = {
                "model":            "mistralai/mistral-medium-3.5-128b",
                "reasoning_effort": "high",
                "messages":         [{"role": "user", "content": prompt}],
                "max_tokens":       16384,
                "temperature":      0.70,
                "top_p":            1.00,
                "stream":           True,
            }
            response = requests.post(INVOKE_URL, headers=HEADERS, json=payload, stream=True, timeout=TIMEOUT)

            if response.status_code == 429:
                wait = DELAY_BETWEEN_CALLS * attempt
                print(f"Rate limited. Waiting {wait}s (retry {attempt}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue
            if response.status_code != 200:
                raise RuntimeError(f"API error {response.status_code}: {response.text}")

            full_answer, chunk_count = "", 0
            try:
                for line in response.iter_lines():
                    if not line:
                        continue
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: ") and decoded != "data: [DONE]":
                        try:
                            chunk   = json.loads(decoded[6:])
                            choices = chunk.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            if delta.get("content"):
                                full_answer += delta["content"]
                                chunk_count += 1
                                if chunk_count % 20 == 0:
                                    print(f"      Receiving... ({len(full_answer)} chars)")
                        except json.JSONDecodeError:
                            pass
            except ChunkedEncodingError as e:
                print(f"Stream cut off after {len(full_answer)} chars (attempt {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(DELAY_BETWEEN_CALLS * attempt)
                    continue
                raise

            if len(full_answer) < 10:
                print(f"Response too short ({len(full_answer)} chars). Retrying...")
                time.sleep(DELAY_BETWEEN_CALLS)
                continue

            print(f"Got {len(full_answer)} chars")
            return full_answer.strip()

        except (Timeout, ConnectionError) as e:
            print(f"Network error (attempt {attempt}/{MAX_RETRIES}): {type(e).__name__}")
            time.sleep(DELAY_BETWEEN_CALLS * attempt)
        except RequestException as e:
            print(f"Request error (attempt {attempt}/{MAX_RETRIES}): {e}")
            time.sleep(DELAY_BETWEEN_CALLS * attempt)

    raise RuntimeError(f"Failed after {MAX_RETRIES} retries.")


# ─────────────────────────────────────────────────────────────────────
# Prompt builders
# ─────────────────────────────────────────────────────────────────────
def reference_block(raw_inputs: list, ref_inputs: dict, registry: dict, current_entities: dict) -> str:
    """Tells the LLM exactly how to reference every input, with known columns."""
    lines = []
    for t in raw_inputs:
        lines.append(f"- {{{{ source('raw', '{t}') }}}}  (raw table)")
    for inp, model in ref_inputs.items():
        cols = []
        if model in registry["entities"]:
            cols = registry["entities"][model].get("output_columns", [])
        elif model in current_entities:
            cols = current_entities[model].get("target_columns", [])
        col_hint = f" — output columns: {', '.join(cols)}" if cols else ""
        lines.append(
            f"- {{{{ ref('{model}') }}}}  (existing model replacing raw `{inp}`; "
            f"use its cleaned column names{col_hint})"
        )
    return "\n".join(lines) if lines else "- see mapping"


def create_sql_prompt(name, layer, mapping_text, ref_block, skill) -> str:
    return f"""You are a senior dbt developer. CREATE a new dbt SQL model `{name}` (layer: {layer}).

=== HOUSE STYLE (follow exactly) ===
{skill}

=== MAPPING ===
{mapping_text}

=== HOW TO REFERENCE EVERY INPUT (follow exactly) ===
{ref_block}

Apply ALL transformations from the "Transformation (SQL Snippet)" column exactly.
Output ONLY raw SQL, no markdown, no explanation."""


def update_sql_prompt(name, layer, mapping_text, ref_block, skill, previous_sql) -> str:
    return f"""You are a senior dbt developer. UPDATE an existing dbt SQL model `{name}` (layer: {layer}).
The mapping sheet has changed. Modify the previous model to match the NEW mapping.
PRESERVE all structure, style, and logic that is still correct — make surgical changes only.

=== HOUSE STYLE (follow exactly) ===
{skill}

=== PREVIOUS MODEL (your earlier output) ===
{previous_sql}

=== NEW MAPPING (the source of truth now) ===
{mapping_text}

=== HOW TO REFERENCE EVERY INPUT (follow exactly) ===
{ref_block}

Apply ALL transformations from the "Transformation (SQL Snippet)" column exactly.
Output ONLY the full updated raw SQL, no markdown, no explanation, no diff — the complete file."""


def yml_prompt(name, mapping_text, skill) -> str:
    return f"""You are a senior dbt developer. Generate the dbt schema YAML for `{name}`.

=== HOUSE STYLE (follow exactly) ===
{skill}

=== MAPPING ===
{mapping_text}

Output ONLY raw YAML, no markdown, no explanation."""


def sources_yml_prompt(raw_tables: dict) -> str:
    lines = [
        f"- table: {t}, columns: {', '.join(cols) if cols else 'unknown'}"
        for t, cols in sorted(raw_tables.items())
    ]
    return f"""Write a complete dbt sources.yml file.
Source name: raw
Tables (this is the FULL list — include every one):
{chr(10).join(lines)}

Output ONLY raw YAML, no markdown, no explanation."""


# ─────────────────────────────────────────────────────────────────────
# Raw-table column collection (for sources.yml + registry)
# ─────────────────────────────────────────────────────────────────────
def collect_raw_columns(current_entities: dict, raw_table_names: set) -> dict:
    cols = defaultdict(set)
    for ent in current_entities.values():
        df = ent["df"]
        src_t = find_col(df, "source", "table")
        src_c = find_col(df, "source", "column")
        if not src_t:
            continue
        for _, row in df.iterrows():
            t = str(row.get(src_t, "")).strip().lower()
            c = str(row.get(src_c, "")).strip() if src_c else ""
            if t in raw_table_names and c and c.lower() not in NULLISH:
                cols[t].add(c)
    return {t: sorted(c) for t, c in cols.items()}


# ─────────────────────────────────────────────────────────────────────
# Save helper
# ─────────────────────────────────────────────────────────────────────
def save_file(content: str, filepath: Path):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content)
    print(f"Saved: {filepath}")


# ─────────────────────────────────────────────────────────────────────
# Process one mapping file
# ─────────────────────────────────────────────────────────────────────
def process_mapping(mapping_file: Path, registry: dict, skill: str):
    print(f"\n{'='*60}\nProcessing: {mapping_file}\n{'='*60}")

    current = parse_mapping_file(mapping_file)
    print(f"Entities in file: {list(current)}")

    # ── classify all inputs & find raw tables ─────────────────────
    all_raw = set()
    for name, ent in current.items():
        raw, refs = classify_inputs(ent["inputs"], current, registry)
        ent["raw_inputs"], ent["ref_inputs"] = raw, refs
        all_raw.update(raw)

    # ── sources.yml (registry-managed: regenerate on NEW raw table) ─
    raw_cols = collect_raw_columns(current, all_raw)
    new_tables = [t for t in raw_cols if t not in registry["raw_tables"]]
    # also merge any new columns on known tables
    cols_changed = any(
        set(raw_cols.get(t, [])) - set(registry["raw_tables"].get(t, []))
        for t in raw_cols
    )
    if new_tables or cols_changed:
        for t, c in raw_cols.items():
            merged = sorted(set(registry["raw_tables"].get(t, [])) | set(c))
            registry["raw_tables"][t] = merged
        print(f"\nNew/changed raw tables detected: {new_tables or '(columns updated)'}")
        print("Regenerating sources.yml with full known table set...")
        save_file(
            call_llm(sources_yml_prompt(registry["raw_tables"])),
            DBT_MODELS_DIR / "sources.yml"
        )
        time.sleep(DELAY_BETWEEN_CALLS)
    else:
        print("\nsources.yml up to date — skipping")

    # ── layers + processing order ──────────────────────────────────
    layers  = infer_layers(current, registry)
    ordered = topo_sort(current, registry)
    print(f"\nLayers: {layers}")
    print(f"Order : {ordered}\n")

    # ── generate each entity ───────────────────────────────────────
    for name in ordered:
        ent       = current[name]
        layer     = layers[name]
        reg_entry = registry["entities"].get(name)
        sql_path  = DBT_MODELS_DIR / layer / f"{name}.sql"
        yml_path  = DBT_MODELS_DIR / layer / f"_{name}.yml"

        ref_block = reference_block(ent["raw_inputs"], ent["ref_inputs"], registry, current)

        # ── SKIP: unchanged ────────────────────────────────────────
        if reg_entry and reg_entry.get("mapping_hash") == ent["hash"] and sql_path.exists():
            print(f"[SKIP] {name} — mapping unchanged")
            continue

        # ── UPDATE: existing model, mapping changed ────────────────
        if reg_entry and sql_path.exists():
            print(f"[UPDATE] {name} ({layer})")
            print(f"  source() → {ent['raw_inputs']}")
            print(f"  ref()    → {ent['ref_inputs']}")
            previous_sql = sql_path.read_text()
            print("  Updating SQL...")
            save_file(
                call_llm(update_sql_prompt(name, layer, ent["mapping_text"], ref_block, skill, previous_sql)),
                sql_path
            )
        # ── CREATE: new entity ─────────────────────────────────────
        else:
            print(f"[CREATE] {name} ({layer})")
            print(f"  source() → {ent['raw_inputs']}")
            print(f"  ref()    → {ent['ref_inputs']}")
            print("  Generating SQL...")
            save_file(
                call_llm(create_sql_prompt(name, layer, ent["mapping_text"], ref_block, skill)),
                sql_path
            )
        time.sleep(DELAY_BETWEEN_CALLS)

        print("  Generating YAML...")
        save_file(call_llm(yml_prompt(name, ent["mapping_text"], skill)), yml_path)
        time.sleep(DELAY_BETWEEN_CALLS)

        # ── record in registry ─────────────────────────────────────
        registry["entities"][name] = {
            "layer":          layer,
            "file":           str(sql_path),
            "mapping_hash":   ent["hash"],
            "sources":        ent["raw_inputs"],
            "refs":           sorted(set(ent["ref_inputs"].values())),
            "output_columns": ent["target_columns"],
            "mapping_file":   ent["mapping_file"],
            "last_generated": datetime.datetime.utcnow().isoformat() + "Z",
        }
        save_registry(registry)   # save after every entity — crash-safe


# ─────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────
def get_mapping_files() -> list:
    changed = os.environ.get("CHANGED_FILES", "").strip()
    if changed:
        files = [Path(f) for f in changed.split() if f.endswith(".xlsx") and Path(f).exists()]
        print(f"Processing {len(files)} changed file(s): {[str(f) for f in files]}")
    else:
        files = list(MAPPING_DIR.glob("**/*.xlsx"))
        print(f"Processing all {len(files)} file(s) in {MAPPING_DIR}/")
    return files


def main():
    if not API_KEY:
        raise EnvironmentError("API_KEY environment variable is not set.")

    registry = load_registry()
    skill    = load_skill()
    print(f"Registry: {len(registry['entities'])} known entities, "
          f"{len(registry['raw_tables'])} known raw tables")

    for f in get_mapping_files():
        process_mapping(f, registry, skill)

    save_registry(registry)
    print(f"\nAll done! Models in {DBT_MODELS_DIR}/, memory in {REGISTRY_PATH}")


if __name__ == "__main__":
    main()