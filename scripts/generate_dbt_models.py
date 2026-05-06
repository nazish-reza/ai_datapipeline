"""
generate_dbt_models.py
─────────────────────
Generates dbt SQL + YML from mapping sheets.

Smart ref() resolution:
  For any raw table a model needs, we check if ANY other model at a
  lower layer already processes that raw table. If yes → ref() it.
  No hardcoded prefixes. Works for any naming convention.
"""

import requests
import json
import os
import time
import pandas as pd
from pathlib import Path
from collections import defaultdict
from requests.exceptions import ChunkedEncodingError, ConnectionError, Timeout, RequestException

# ── Config ────────────────────────────────────────────────────────────
INVOKE_URL          = os.environ.get("INVOKE_URL", "https://integrate.api.nvidia.com/v1/chat/completions")
API_KEY             = os.environ.get("API_KEY", "")
MAPPING_DIR         = Path("mapping")
DBT_MODELS_DIR      = Path("dbt/models/bigquery")
DELAY_BETWEEN_CALLS = 20
MAX_RETRIES         = 5
TIMEOUT             = (10, 300)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "text/event-stream"
}

# Layer processing order — lower number = processed first
LAYER_ORDER = {
    "staging":      0,
    "intermediate": 1,
    "marts":        2,
}


# ─────────────────────────────────────────────────────────────────────
# 1. Layer detection
# ─────────────────────────────────────────────────────────────────────
def detect_layer(entity_name: str) -> str:
    name = entity_name.lower()
    if name.startswith(("fct_", "fact_")):
        return "marts"
    elif name.startswith(("stg_", "staging_")):
        return "staging"
    elif name.startswith(("int_", "intermediate_")):
        return "intermediate"
    elif name.startswith("dim_"):
        return "staging"
    else:
        return "staging"


def layer_rank(entity_name: str) -> int:
    return LAYER_ORDER.get(detect_layer(entity_name), 0)


# ─────────────────────────────────────────────────────────────────────
# 2. Detect raw source tables (tables not defined as any sheet/entity)
# ─────────────────────────────────────────────────────────────────────
def detect_source_tables(xl: pd.ExcelFile) -> dict:
    """Returns {raw_table: [columns_used]}"""
    all_entities = set(s.strip().lower() for s in xl.sheet_names)
    source_tables = {}

    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        src_table_col = next((c for c in df.columns if "source" in c.lower() and "table" in c.lower()), None)
        src_col_col   = next((c for c in df.columns if "source" in c.lower() and "column" in c.lower()), None)
        if src_table_col is None:
            continue

        for _, row in df.iterrows():
            src_table = str(row.get(src_table_col, "")).strip().lower()
            src_col   = str(row.get(src_col_col, "")).strip() if src_col_col else ""

            if not src_table or src_table in ("nan", "derived", "n/a", ""):
                continue
            if src_table in all_entities:
                continue

            if src_table not in source_tables:
                source_tables[src_table] = set()
            if src_col and src_col.lower() not in ("nan", "n/a", ""):
                source_tables[src_table].add(src_col)

    return {t: sorted(cols) for t, cols in source_tables.items()}


# ─────────────────────────────────────────────────────────────────────
# 3. Build the model graph
#    raw_table → list of (model_name, layer_rank) that consume it
#    This is built from ALL sheets, not just dims.
# ─────────────────────────────────────────────────────────────────────
def build_model_graph(xl: pd.ExcelFile, raw_tables: dict) -> dict:
    """
    Returns:
        graph = {
            raw_table_name: [
                {"model": "dim_users",  "rank": 0},
                {"model": "fct_orders", "rank": 2},
                ...
            ]
        }
    Sorted by rank ascending (staging models first).
    """
    graph = defaultdict(list)

    for sheet in xl.sheet_names:
        entity_name = sheet.strip()
        df = xl.parse(sheet)

        src_table_col = next((c for c in df.columns if "source" in c.lower() and "table" in c.lower()), None)
        if src_table_col is None:
            continue

        raw_tables_used = set(
            str(v).strip().lower()
            for v in df[src_table_col].dropna().unique()
            if str(v).strip().lower() not in ("nan", "derived", "n/a", "")
            and str(v).strip().lower() in raw_tables
        )

        for raw_table in raw_tables_used:
            graph[raw_table].append({
                "model": entity_name,
                "rank":  layer_rank(entity_name),
            })

    # Sort each entry by rank so lower-layer models come first
    for raw_table in graph:
        graph[raw_table].sort(key=lambda x: x["rank"])

    return dict(graph)


# ─────────────────────────────────────────────────────────────────────
# 4. Intelligent source resolution
#    For each raw table an entity needs:
#    - Find all OTHER models that also use that raw table
#    - If any of them have a LOWER layer rank → ref() the lowest-ranked one
#    - Otherwise → source() directly
#
#    This works for ANY naming convention — no dim_ prefix assumption.
# ─────────────────────────────────────────────────────────────────────
def resolve_sources(
    df: pd.DataFrame,
    entity_name: str,
    raw_tables: dict,
    model_graph: dict,
) -> tuple[list, dict]:
    """
    Returns:
        raw_sources: [table_name, ...]      → use {{ source('raw', table) }}
        ref_sources: {table_name: model}    → use {{ ref(model) }}
    """
    src_table_col = next((c for c in df.columns if "source" in c.lower() and "table" in c.lower()), None)
    if src_table_col is None:
        return [], {}

    my_rank = layer_rank(entity_name)
    raw_sources = []
    ref_sources = {}

    raw_tables_needed = set(
        str(v).strip().lower()
        for v in df[src_table_col].dropna().unique()
        if str(v).strip().lower() not in ("nan", "derived", "n/a", "")
        and str(v).strip().lower() in raw_tables
    )

    for raw_table in raw_tables_needed:
        consumers = model_graph.get(raw_table, [])

        # Find the best upstream model:
        # - Must be a DIFFERENT model (not self)
        # - Must have a LOWER layer rank (processed before us)
        # - Among those, pick the LOWEST rank (most upstream/cleanest)
        upstream_candidates = [
            c for c in consumers
            if c["model"].lower() != entity_name.lower()
            and c["rank"] < my_rank
        ]

        if upstream_candidates:
            # Pick the one with the lowest rank (most upstream)
            # Break ties by preferring model whose name contains the raw table name
            best = min(
                upstream_candidates,
                key=lambda c: (
                    c["rank"],
                    0 if raw_table in c["model"].lower() else 1
                )
            )
            ref_sources[raw_table] = best["model"]
        else:
            raw_sources.append(raw_table)

    return raw_sources, ref_sources


# ─────────────────────────────────────────────────────────────────────
# 5. Determine processing order
#    Sort by layer rank — staging first, marts last.
#    Within same layer, alphabetical for consistency.
# ─────────────────────────────────────────────────────────────────────
def sort_by_layer(sheets: list[str]) -> list[str]:
    return sorted(sheets, key=lambda s: (layer_rank(s.strip()), s.strip().lower()))


# ─────────────────────────────────────────────────────────────────────
# 6. LLM call with retry
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

            full_answer = ""
            chunk_count = 0

            try:
                for line in response.iter_lines():
                    if line:
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
                    wait = DELAY_BETWEEN_CALLS * attempt
                    print(f"Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                else:
                    raise

            if len(full_answer) < 10:
                print(f"Response too short ({len(full_answer)} chars). Retrying...")
                time.sleep(DELAY_BETWEEN_CALLS)
                continue

            print(f"Got {len(full_answer)} chars")
            return full_answer.strip()

        except (Timeout, ConnectionError) as e:
            wait = DELAY_BETWEEN_CALLS * attempt
            print(f"Network error (attempt {attempt}/{MAX_RETRIES}): {type(e).__name__}. Waiting {wait}s...")
            time.sleep(wait)

        except RequestException as e:
            wait = DELAY_BETWEEN_CALLS * attempt
            print(f"Request error (attempt {attempt}/{MAX_RETRIES}): {e}. Waiting {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"Failed after {MAX_RETRIES} retries.")


# ─────────────────────────────────────────────────────────────────────
# 7. Prompts
# ─────────────────────────────────────────────────────────────────────
def sources_yml_prompt(source_tables: dict) -> str:
    lines = [
        f"- table: {t}, columns: {', '.join(cols) if cols else 'unknown'}"
        for t, cols in source_tables.items()
    ]
    return f"""Write a dbt sources.yml file.
Source name: raw
Tables:
{chr(10).join(lines)}

Output ONLY raw YAML, no markdown, no explanation."""


def sql_prompt(
    entity_name: str,
    layer: str,
    mapping_text: str,
    raw_sources: list,
    ref_sources: dict,
) -> str:
    lines = []
    for t in raw_sources:
        lines.append(f"  - {{{{ source('raw', '{t}') }}}}  ← raw table, not yet modelled")
    for raw_table, model in ref_sources.items():
        lines.append(
            f"  - {{{{ ref('{model}') }}}}  ← use this instead of raw `{raw_table}`; "
            f"`{model}` already cleans/transforms `{raw_table}`"
        )

    source_block = "\n".join(lines) or "  - see mapping"

    return f"""You are a senior dbt developer. Generate a dbt SQL model for `{entity_name}` (layer: {layer}).

MAPPING:
{mapping_text}

HOW TO REFERENCE DATA — follow this exactly:
{source_block}

STRICT RULES:
- NEVER use source() for any table that has a ref() listed above
- When using a ref() model, use its OUTPUT column names (already cleaned/snake_case), NOT the raw column names
- Structure: one CTE per source or ref → transformations CTE → final SELECT
- JOIN models on their cleaned key columns (e.g. user_id not `User-ID`)
- Apply ALL transformations from "Transformation (SQL Snippet)" column exactly
- Add a comment block at top listing: model name, description, all source() and ref() used
- Output ONLY raw SQL, no markdown, no explanation"""


def yml_prompt(entity_name: str, mapping_text: str) -> str:
    return f"""You are a senior dbt developer. Generate a dbt schema YAML for `{entity_name}`.

MAPPING:
{mapping_text}

RULES:
- Start with: version: 2
- Add model name and a meaningful description
- List EVERY target column with:
    - name
    - description (from Notes column, or infer from transformation)
    - data_tests:
        * Primary key columns: [not_null, unique]
        * Foreign key columns: [not_null]
        * Categorical derived columns: accepted_values (infer values from transformation logic)
- Output ONLY raw YAML, no markdown"""


# ─────────────────────────────────────────────────────────────────────
# 8. Save
# ─────────────────────────────────────────────────────────────────────
def save_file(content: str, filepath: Path):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content)
    print(f"Saved: {filepath}")


# ─────────────────────────────────────────────────────────────────────
# 9. Process one mapping file
# ─────────────────────────────────────────────────────────────────────
def process_mapping(mapping_file: Path):
    print(f"\n{'='*60}")
    print(f"Processing: {mapping_file}")
    print(f"{'='*60}")

    xl     = pd.ExcelFile(mapping_file)
    sheets = xl.sheet_names
    print(f"Found {len(sheets)} entities: {sheets}")

    # Build the full picture before generating anything
    raw_tables   = detect_source_tables(xl)
    model_graph  = build_model_graph(xl, raw_tables)

    print(f"\nRaw tables   : {list(raw_tables.keys())}")
    print(f"Model graph  :")
    for t, consumers in model_graph.items():
        print(f"  {t} → {[c['model'] for c in consumers]}")

    # sources.yml
    sources_path = DBT_MODELS_DIR / "sources.yml"
    if not sources_path.exists():
        print(f"\nGenerating sources.yml...")
        save_file(call_llm(sources_yml_prompt(raw_tables)), sources_path)
        time.sleep(DELAY_BETWEEN_CALLS)
    else:
        print(f"\nsources.yml already exists — skipping")

    # Process in layer order
    ordered = sort_by_layer(sheets)
    print(f"\nProcessing order: {ordered}\n")

    for sheet in ordered:
        entity_name  = sheet.strip()
        layer        = detect_layer(entity_name)
        df           = xl.parse(sheet)
        mapping_text = df.to_string(index=False)

        # Intelligently resolve source() vs ref()
        raw_srcs, ref_srcs = resolve_sources(df, entity_name, raw_tables, model_graph)

        print(f"[{layer.upper()}] {entity_name}")
        print(f"  source() → {raw_srcs}")
        print(f"  ref()    → {ref_srcs}")

        print("  Generating SQL...")
        save_file(
            call_llm(sql_prompt(entity_name, layer, mapping_text, raw_srcs, ref_srcs)),
            DBT_MODELS_DIR / layer / f"{entity_name}.sql"
        )
        time.sleep(DELAY_BETWEEN_CALLS)

        print("  Generating YAML...")
        save_file(
            call_llm(yml_prompt(entity_name, mapping_text)),
            DBT_MODELS_DIR / layer / f"_{entity_name}.yml"
        )
        time.sleep(DELAY_BETWEEN_CALLS)


# ─────────────────────────────────────────────────────────────────────
# 10. Entry point
# ─────────────────────────────────────────────────────────────────────
def get_mapping_files() -> list[Path]:
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
    for f in get_mapping_files():
        process_mapping(f)
    print(f"\nAll done! Files in: {DBT_MODELS_DIR}/")


if __name__ == "__main__":
    main()