"""
generate_dbt_models.py
─────────────────────
Runs inside GitHub Actions. Reads all .xlsx files from the mapping/ folder
(or only changed ones if CHANGED_FILES env var is set), generates dbt SQL
and YML files, and writes them to dbt/models/bigquery.
"""

import requests
import json
import os
import time
import pandas as pd
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────
INVOKE_URL = os.environ.get("INVOKE_URL", "")
API_KEY = os.environ.get("API_KEY", "")
MAPPING_DIR = Path("mapping")       # folder with .xlsx mapping files
DBT_MODELS_DIR = Path("dbt/models/bigquery")  # output folder inside repo
DELAY_BETWEEN_CALLS = 20                    # seconds between LLM calls
MAX_RETRIES = 3
TIMEOUT = (10, 300)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "text/event-stream"
}


# ─────────────────────────────────────────────────────────────────────
# 1. Determine which mapping files to process
# ─────────────────────────────────────────────────────────────────────
def get_mapping_files() -> list[Path]:
    """
    If CHANGED_FILES env var is set (from GitHub Actions), only process those.
    Otherwise process all .xlsx files in mapping/ folder.
    """
    changed = os.environ.get("CHANGED_FILES", "").strip()

    if changed:
        files = [
            Path(f) for f in changed.split()
            if f.endswith(".xlsx") and Path(f).exists()
        ]
        print(f"Processing {len(files)} changed mapping file(s): {[str(f) for f in files]}")
    else:
        files = list(MAPPING_DIR.glob("**/*.xlsx"))
        print(f"Processing all {len(files)} mapping file(s) in {MAPPING_DIR}/")

    return files


# ─────────────────────────────────────────────────────────────────────
# 2. Detect layer from entity name prefix
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


# ─────────────────────────────────────────────────────────────────────
# 3. Auto-detect raw source tables across all sheets
# ─────────────────────────────────────────────────────────────────────
def detect_source_tables(xl: pd.ExcelFile) -> dict:
    all_target_entities = set(s.strip().lower() for s in xl.sheet_names)
    source_tables = {}

    for sheet in xl.sheet_names:
        df = xl.parse(sheet)

        src_table_col = next(
            (c for c in df.columns if "source" in c.lower() and "table" in c.lower()), None
        )
        src_col_col = next(
            (c for c in df.columns if "source" in c.lower() and "column" in c.lower()), None
        )

        if src_table_col is None:
            continue

        for _, row in df.iterrows():
            src_table = str(row.get(src_table_col, "")).strip().lower()
            src_col   = str(row.get(src_col_col, "")).strip() if src_col_col else ""

            if not src_table or src_table in ("nan", "derived", "n/a", ""):
                continue
            if src_table in all_target_entities:
                continue

            if src_table not in source_tables:
                source_tables[src_table] = set()
            if src_col and src_col.lower() not in ("nan", "n/a", ""):
                source_tables[src_table].add(src_col)

    return {t: sorted(cols) for t, cols in source_tables.items()}


# ─────────────────────────────────────────────────────────────────────
# 4. LLM call with retry + timeout
# ─────────────────────────────────────────────────────────────────────
def call_llm(prompt: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            payload = {
                "model": "mistralai/mistral-medium-3.5-128b",
                "reasoning_effort": "high",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 16384,
                "temperature": 0.70,
                "top_p": 1.00,
                "stream": True,
            }

            response = requests.post(
                INVOKE_URL,
                headers=HEADERS,
                json=payload,
                stream=True,
                timeout=TIMEOUT
            )

            if response.status_code == 429:
                wait = DELAY_BETWEEN_CALLS * attempt
                print(f"Rate limited. Waiting {wait}s (retry {attempt}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue

            if response.status_code != 200:
                raise RuntimeError(f"API error {response.status_code}: {response.text}")

            full_answer = ""
            chunk_count = 0

            for line in response.iter_lines():
                if line:
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: ") and decoded != "data: [DONE]":
                        try:
                            chunk = json.loads(decoded[6:])
                            choices = chunk.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            if delta.get("content"):
                                full_answer += delta["content"]
                                chunk_count += 1
                                if chunk_count % 20 == 0:
                                    print(f"Receiving... ({len(full_answer)} chars)")
                        except json.JSONDecodeError:
                            pass

            print(f"Got {len(full_answer)} chars")
            return full_answer.strip()

        except requests.exceptions.Timeout:
            print(f"Timed out (attempt {attempt}/{MAX_RETRIES}). Retrying...")
            time.sleep(DELAY_BETWEEN_CALLS)
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error (attempt {attempt}/{MAX_RETRIES}): {e}")
            time.sleep(DELAY_BETWEEN_CALLS)

    raise RuntimeError(f"Failed after {MAX_RETRIES} retries.")


# ─────────────────────────────────────────────────────────────────────
# 5. Prompts
# ─────────────────────────────────────────────────────────────────────
def sources_yml_prompt(source_tables: dict) -> str:
    lines = []
    for table, columns in source_tables.items():
        cols = ", ".join(columns) if columns else "unknown"
        lines.append(f"- table: {table}, columns: {cols}")
    return f"""Write a dbt sources.yml file.
Source name: raw
Tables:
{chr(10).join(lines)}

Output ONLY raw YAML, no markdown, no explanation."""


def sql_prompt(entity_name: str, layer: str, mapping_text: str, entity_sources: list) -> str:
    source_hint = ", ".join(entity_sources) if entity_sources else "see mapping"
    return f"""You are a senior dbt developer. Generate a dbt SQL model for `{entity_name}` (layer: {layer}).

MAPPING:
{mapping_text}

RULES:
- Raw source tables: {source_hint}
- Use {{{{ source('raw', '<table_name>') }}}} for raw tables
- Use {{{{ ref('<model_name>') }}}} for other dbt models
- Apply ALL transformations from "Transformation (SQL Snippet)" exactly
- Structure: one CTE per source → transformed CTE → final SELECT
- JOIN multiple sources on appropriate keys if needed
- Add a comment block at top: model name, description, source tables
- Output ONLY raw SQL, no markdown"""


def yml_prompt(entity_name: str, mapping_text: str) -> str:
    return f"""You are a senior dbt developer. Generate a dbt schema YAML for `{entity_name}`.

MAPPING:
{mapping_text}

RULES:
- Start with: version: 2
- Add model name and description
- List EVERY target column with:
    - name
    - description (from Notes, or infer from transformation)
    - data_tests:
        * Primary key: [not_null, unique]
        * Foreign key: [not_null]
        * Categorical: accepted_values where values can be inferred
- Output ONLY raw YAML, no markdown"""


# ─────────────────────────────────────────────────────────────────────
# 6. Save file into dbt/models/
# ─────────────────────────────────────────────────────────────────────
def save_file(content: str, filepath: Path):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content)
    print(f"Saved: {filepath}")


# ─────────────────────────────────────────────────────────────────────
# 7. Process one mapping file
# ─────────────────────────────────────────────────────────────────────
def process_mapping(mapping_file: Path):
    print(f"\n{'='*60}")
    print(f"Processing: {mapping_file}")
    print(f"{'='*60}")

    xl = pd.ExcelFile(mapping_file)
    sheets = xl.sheet_names
    print(f"Found {len(sheets)} entities: {sheets}")

    # Detect raw source tables
    source_tables = detect_source_tables(xl)
    print(f"Raw source tables: {list(source_tables.keys())}")

    # Generate sources.yml (once per mapping file)
    sources_path = DBT_MODELS_DIR / "sources.yml"
    if not sources_path.exists():
        print(f"\nGenerating sources.yml...")
        sources_content = call_llm(sources_yml_prompt(source_tables))
        save_file(sources_content, sources_path)
        time.sleep(DELAY_BETWEEN_CALLS)
    else:
        print(f"\nsources.yml already exists — skipping")

    # Generate SQL + YML per entity
    for sheet in sheets:
        entity_name = sheet.strip()
        layer = detect_layer(entity_name)

        print(f"\n[{layer.upper()}] {entity_name}")
        df = xl.parse(sheet)
        mapping_text = df.to_string(index=False)

        src_table_col = next(
            (c for c in df.columns if "source" in c.lower() and "table" in c.lower()), None
        )
        entity_sources = []
        if src_table_col:
            entity_sources = [
                str(v).strip().lower()
                for v in df[src_table_col].dropna().unique()
                if str(v).strip().lower() not in ("nan", "derived", "n/a", "")
                and str(v).strip().lower() in source_tables
            ]

        print(f"Sources: {entity_sources}")

        # SQL
        print("Generating SQL...")
        sql_content = call_llm(sql_prompt(entity_name, layer, mapping_text, entity_sources))
        save_file(sql_content, DBT_MODELS_DIR / layer / f"{entity_name}.sql")
        time.sleep(DELAY_BETWEEN_CALLS)

        # YAML
        print("Generating YAML...")
        yml_content = call_llm(yml_prompt(entity_name, mapping_text))
        save_file(yml_content, DBT_MODELS_DIR / layer / f"_{entity_name}.yml")
        time.sleep(DELAY_BETWEEN_CALLS)


# ─────────────────────────────────────────────────────────────────────
# 8. Main
# ─────────────────────────────────────────────────────────────────────
def main():
    if not API_KEY:
        raise EnvironmentError("API_KEY environment variable is not set.")

    mapping_files = get_mapping_files()

    if not mapping_files:
        print("No mapping files found. Exiting.")
        return

    for mapping_file in mapping_files:
        process_mapping(mapping_file)

    print(f"\nAll done! dbt files written to: {DBT_MODELS_DIR}/")


if __name__ == "__main__":
    main()