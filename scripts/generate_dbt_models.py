"""
generate_dbt_models.py  (v3 — contract-based)
──────────────────────────────────────────────
Reads ODCS YAML contracts from contracts/ and generates dbt SQL + YML.

Features:
  1. SKILL        — skills/dbt_skill.md injected into every prompt
  2. REGISTRY     — dbt/registry.json persistent memory across runs
  3. SKIP         — unchanged contract hash → no LLM call
  4. UPDATE MODE  — changed contract → previous SQL + new mapping → surgical edits
  5. CROSS-RUN REFS — entity referencing a model from a past run gets ref()
  6. DOMAIN FOLDERS — dbt/models/<domain>/<layer>/<entity>.sql
  7. SOURCES.YML  — registry-managed, regenerated on new raw tables
  8. TOPO SORT    — dependencies built before dependents

Usage:
    # Process only changed contracts (GitHub Actions)
    CHANGED_FILES="contracts/book_catalog/dim_books_v1.0.0.yaml" python scripts/generate_dbt_models.py

    # Process all contracts (local)
    python scripts/generate_dbt_models.py
"""

import requests
import json
import os
import sys
import time
import hashlib
import datetime
import yaml
from pathlib import Path
from collections import defaultdict
from requests.exceptions import ChunkedEncodingError, ConnectionError, Timeout, RequestException

# ── Config ────────────────────────────────────────────────────────────
INVOKE_URL   = os.environ.get("INVOKE_URL", "https://integrate.api.nvidia.com/v1/chat/completions")
API_KEY      = os.environ.get("API_KEY", "")
CONTRACTS_DIR= Path("contracts")
DBT_DIR      = Path("dbt/models")
REGISTRY     = Path("dbt/registry.json")
SKILL_PATH   = Path("skills/dbt_skill.md")
DELAY        = 20
MAX_RETRIES  = 5
TIMEOUT      = (10, 300)
NULLISH      = {"nan", "none", "n/a", "na", "derived", ""}

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Accept": "text/event-stream"}


# ─────────────────────────────────────────────────────────────────────
# Registry — persistent memory (committed to git)
# ─────────────────────────────────────────────────────────────────────
def load_registry():
    if REGISTRY.exists():
        r = json.loads(REGISTRY.read_text())
    else:
        r = {}
    r.setdefault("entities", {})
    r.setdefault("raw_tables", {})
    return r


def save_registry(reg):
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, indent=2, sort_keys=True))
    print(f"  Registry saved → {REGISTRY}")


def load_skill():
    if SKILL_PATH.exists():
        return SKILL_PATH.read_text()
    print(f"  WARNING: skill not found at {SKILL_PATH}")
    return ""


# ─────────────────────────────────────────────────────────────────────
# Contract YAML parsing
# ─────────────────────────────────────────────────────────────────────
def get_custom(data, key):
    """Read a value from customProperties list."""
    for cp in data.get("customProperties", []):
        if isinstance(cp, dict) and cp.get("property") == key:
            v = cp.get("value", "")
            if isinstance(v, str) and v.startswith("="):
                return ""
            return str(v).strip() if v else ""
    return ""


def parse_contract(path):
    """Parse a contract YAML into a dict with all fields needed for generation."""
    data = yaml.safe_load(path.read_text()) or {}
    schema = data.get("schema", [])
    cols = schema[0].get("properties", schema[0].get("columns", [])) if schema else []

    entity = data.get("name", path.stem.split("_v")[0])
    domain = data.get("domain", "default")

    # Sources from customProperties
    src_str = get_custom(data, "sources") or get_custom(data, "upstream_entities")
    sources = [s.strip() for s in src_str.split(",") if s.strip()] if src_str else []

    # Layer from customProperties with fallback
    layer = get_custom(data, "layer")
    if not layer:
        n = entity.lower()
        if n.startswith(("fct_", "fact_")):
            layer = "marts"
        elif n.startswith(("int_", "intermediate_")):
            layer = "intermediate"
        else:
            layer = "staging"

    # Build mapping text from schema columns (for LLM prompt)
    mapping_lines = ["Target Column | Source Table | Transformation | Description"]
    mapping_lines.append("-" * 80)
    for c in cols:
        src = ""
        ts = c.get("transformSourceObjects", c.get("transformSources", []))
        if isinstance(ts, list) and ts:
            src = ts[0]
        elif isinstance(ts, str):
            src = ts
        tl = c.get("transformLogic", "")
        mapping_lines.append(
            f"{c.get('name','')} | {src} | {tl} | {c.get('description','')}"
        )

    # Output column names
    output_columns = [c.get("name", "") for c in cols if c.get("name")]

    return {
        "entity":         entity,
        "domain":         domain,
        "layer":          layer,
        "version":        data.get("version", "1.0.0"),
        "sources":        sources,
        "output_columns": output_columns,
        "mapping_text":   "\n".join(mapping_lines),
        "contract_hash":  hashlib.sha256(path.read_bytes()).hexdigest()[:16],
        "contract_file":  str(path),
    }


# ─────────────────────────────────────────────────────────────────────
# LLM call with retry
# ─────────────────────────────────────────────────────────────────────
def call_llm(prompt):
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

            response = requests.post(
                INVOKE_URL, headers=HEADERS, json=payload,
                stream=True, timeout=TIMEOUT
            )

            if response.status_code == 429:
                wait = DELAY * attempt
                print(f"      Rate limited. Waiting {wait}s (retry {attempt}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue

            if response.status_code != 200:
                raise RuntimeError(f"API error {response.status_code}: {response.text}")

            full_answer = ""
            try:
                for line in response.iter_lines():
                    if not line:
                        continue
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
                        except json.JSONDecodeError:
                            pass
            except ChunkedEncodingError:
                if attempt < MAX_RETRIES:
                    time.sleep(DELAY * attempt)
                    continue
                raise

            if len(full_answer) < 10:
                print(f"      Response too short. Retrying...")
                time.sleep(DELAY)
                continue

            print(f"      Got {len(full_answer)} chars")
            return full_answer.strip()

        except (Timeout, ConnectionError) as e:
            print(f"      Network error (attempt {attempt}): {type(e).__name__}")
            time.sleep(DELAY * attempt)
        except RequestException as e:
            print(f"      Request error (attempt {attempt}): {e}")
            time.sleep(DELAY * attempt)

    raise RuntimeError(f"Failed after {MAX_RETRIES} retries.")


# ─────────────────────────────────────────────────────────────────────
# Prompt builders
# ─────────────────────────────────────────────────────────────────────
def reference_block(sources, registry, current_entities):
    """Build source/ref instructions for the LLM."""
    lines = []
    for src in sources:
        if src in registry["entities"]:
            reg = registry["entities"][src]
            cols = reg.get("output_columns", [])
            hint = f" — columns: {', '.join(cols)}" if cols else ""
            lines.append(f"  - {{{{ ref('{src}') }}}}  (existing model{hint})")
        elif src in current_entities:
            cols = current_entities[src].get("output_columns", [])
            hint = f" — columns: {', '.join(cols)}" if cols else ""
            lines.append(f"  - {{{{ ref('{src}') }}}}  (model in this run{hint})")
        else:
            lines.append(f"  - {{{{ source('raw', '{src}') }}}}  (raw table)")
    return "\n".join(lines) or "  - see mapping"


def create_sql_prompt(name, layer, mapping, ref_block, skill):
    return f"""You are a senior dbt developer. CREATE a new dbt SQL model `{name}` (layer: {layer}).

=== HOUSE STYLE (follow exactly) ===
{skill}

=== MAPPING ===
{mapping}

=== HOW TO REFERENCE INPUTS (follow exactly) ===
{ref_block}

Apply ALL transformations exactly.
Output ONLY raw SQL, no markdown, no explanation."""


def update_sql_prompt(name, layer, mapping, ref_block, skill, previous_sql):
    return f"""You are a senior dbt developer. UPDATE an existing dbt SQL model `{name}` (layer: {layer}).
The contract changed. Make SURGICAL changes only — preserve correct structure and logic.

=== HOUSE STYLE (follow exactly) ===
{skill}

=== PREVIOUS MODEL (your earlier output) ===
{previous_sql}

=== NEW MAPPING (source of truth now) ===
{mapping}

=== HOW TO REFERENCE INPUTS (follow exactly) ===
{ref_block}

Output ONLY the complete updated raw SQL, no markdown, no diff."""


def yml_prompt(name, mapping, skill):
    return f"""You are a senior dbt developer. Generate the dbt schema YAML for `{name}`.

=== HOUSE STYLE (follow exactly) ===
{skill}

=== MAPPING ===
{mapping}

Output ONLY raw YAML, no markdown."""


def sources_yml_prompt(raw_tables):
    lines = [f"- table: {t}" for t in sorted(raw_tables)]
    return f"""Write a complete dbt sources.yml file.
Source name: raw
Tables (include ALL):
{chr(10).join(lines)}

Output ONLY raw YAML, no markdown."""


# ─────────────────────────────────────────────────────────────────────
# Save helper
# ─────────────────────────────────────────────────────────────────────
def save_file(content, filepath):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content)
    print(f"      Saved: {filepath}")


# ─────────────────────────────────────────────────────────────────────
# Topological sort
# ─────────────────────────────────────────────────────────────────────
def topo_sort(current_entities, registry):
    names = list(current_entities.keys())
    name_set = set(names)

    deps = {}
    for name, c in current_entities.items():
        deps[name] = {s for s in c["sources"] if s in name_set and s != name}

    ordered, placed = [], set()
    remaining = dict(deps)
    while remaining:
        ready = sorted(n for n, d in remaining.items() if d <= placed)
        if not ready:
            print(f"  WARNING: dependency cycle among {list(remaining)}")
            ordered.extend(sorted(remaining))
            break
        for n in ready:
            ordered.append(n)
            placed.add(n)
            del remaining[n]
    return ordered


# ─────────────────────────────────────────────────────────────────────
# Get contract files to process
# ─────────────────────────────────────────────────────────────────────
def get_contract_files():
    changed = os.environ.get("CHANGED_FILES", "").strip()
    if changed:
        files = [Path(f) for f in changed.split() if f.endswith(".yaml") and Path(f).exists()]
        print(f"Processing {len(files)} changed contract(s): {[str(f) for f in files]}")
    else:
        files = sorted(CONTRACTS_DIR.rglob("*.yaml"))
        print(f"Processing all {len(files)} contract(s) in {CONTRACTS_DIR}/")
    return files


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────
def main():
    if not API_KEY:
        print("ERROR: API_KEY environment variable not set.")
        sys.exit(1)

    registry = load_registry()
    skill    = load_skill()
    print(f"Registry: {len(registry['entities'])} entities, {len(registry['raw_tables'])} raw tables")

    # Parse all contract files
    contract_files = get_contract_files()
    if not contract_files:
        print("No contract files found.")
        return

    current = {}
    for cf in contract_files:
        c = parse_contract(cf)
        current[c["entity"]] = c
        print(f"  Parsed: {c['entity']} (domain={c['domain']}, layer={c['layer']}, sources={c['sources']})")

    # Identify raw tables (sources not in any entity)
    all_entity_ids = set(current.keys()) | set(registry["entities"].keys())
    raw_tables = set()
    for c in current.values():
        for src in c["sources"]:
            if src not in all_entity_ids:
                raw_tables.add(src)

    # ── sources.yml — regenerate on new raw tables ────────────────
    new_raws = raw_tables - set(registry["raw_tables"].keys())
    if new_raws:
        for t in raw_tables:
            registry["raw_tables"][t] = []
        print(f"\n  New raw tables: {sorted(new_raws)} — regenerating sources.yml")
        save_file(
            call_llm(sources_yml_prompt(registry["raw_tables"])),
            DBT_DIR / "sources.yml"
        )
        time.sleep(DELAY)
    else:
        print("\n  sources.yml up to date")

    # ── Topological sort ──────────────────────────────────────────
    ordered = topo_sort(current, registry)
    print(f"  Processing order: {ordered}\n")

    # ── Generate each entity ──────────────────────────────────────
    for name in ordered:
        c          = current[name]
        reg_entry  = registry["entities"].get(name)
        sql_path   = DBT_DIR / c["domain"] / c["layer"] / f"{name}.sql"
        yml_path   = DBT_DIR / c["domain"] / c["layer"] / f"_{name}.yml"
        refs       = reference_block(c["sources"], registry, current)

        # SKIP unchanged
        if reg_entry and reg_entry.get("contract_hash") == c["contract_hash"] and sql_path.exists():
            print(f"  [SKIP] {name} — contract unchanged")
            continue

        # UPDATE existing
        if reg_entry and sql_path.exists():
            print(f"  [UPDATE] {name} ({c['domain']}/{c['layer']})")
            print(f"    source() / ref() → {c['sources']}")
            prev_sql = sql_path.read_text()
            print("    Updating SQL...")
            save_file(
                call_llm(update_sql_prompt(name, c["layer"], c["mapping_text"], refs, skill, prev_sql)),
                sql_path
            )
        else:
            # CREATE new
            print(f"  [CREATE] {name} ({c['domain']}/{c['layer']})")
            print(f"    source() / ref() → {c['sources']}")
            print("    Generating SQL...")
            save_file(
                call_llm(create_sql_prompt(name, c["layer"], c["mapping_text"], refs, skill)),
                sql_path
            )

        time.sleep(DELAY)

        print("    Generating YAML schema...")
        save_file(
            call_llm(yml_prompt(name, c["mapping_text"], skill)),
            yml_path
        )
        time.sleep(DELAY)

        # Update registry
        registry["entities"][name] = {
            "layer":          c["layer"],
            "domain":         c["domain"],
            "version":        c["version"],
            "file":           str(sql_path),
            "contract_yaml":  c["contract_file"],
            "contract_hash":  c["contract_hash"],
            "sources":        c["sources"],
            "refs":           [s for s in c["sources"] if s in all_entity_ids],
            "output_columns": c["output_columns"],
            "last_generated": datetime.datetime.utcnow().isoformat() + "Z",
        }
        save_registry(registry)  # save after each entity — crash-safe

    save_registry(registry)
    print(f"\n✅ All done! Models → {DBT_DIR}/, Registry → {REGISTRY}")


if __name__ == "__main__":
    main()