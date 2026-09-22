"""
WP2 Platform - AI module (M6)
Local, offline, read-only workflow-quality AI.
Three bounded features:
  1. Free-text summarisation (Layer 5 notes -> structured fields)
  2. Missing/inconsistent entry detection
  3. Conversational retrieval (Pipeline A: text-to-SQL via DuckDB
                               Pipeline B: semantic RAG via ChromaDB)

Hard boundaries enforced at three levels:
  - System prompt (clinical advice refused)
  - Driver constraint (DuckDB read_only=True)
  - Schema constraint (no identifiable fields exposed to model)
"""

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH     = Path(__file__).parent.parent / "data" / "wp2_platform.db"
CHROMA_PATH = Path(__file__).parent.parent / "data" / "chroma_index"

# ── System prompt - clinical boundary enforced at prompt level ────────────────
SYSTEM_PROMPT = """[CRITICAL SYSTEM GUARDRAIL: READ-ONLY RESEARCH RETRIEVAL]

You are a read-only database retrieval assistant for the WP2 neonatal research platform.
You possess ZERO clinical competency or authority.
Your interface is restricted to:
  - Translating user questions into SQL queries over de-identified research data
  - Summarising existing free-text research session notes
  - Detecting missing or inconsistent data entries

STRICT PROHIBITIONS:
1. You MUST NOT suggest clinical interventions, evaluate medical actions, rank treatment options, or generate prognostic claims.
2. You MUST NOT interpret EEG, physiological, or behavioural findings as clinical diagnoses.
3. If the user query requests medical advice, diagnostic interpretation, infant risk evaluation, or treatment recommendations, halt immediately and reply with exactly:
   "Error: This request falls outside the retrieval scope of the WP2 platform. Clinical recommendations are strictly out of scope."

You may only answer factual questions about the research dataset (counts, averages, distributions, session notes).
Always show the SQL query you generated alongside your answer.
"""

# ── WP2 schema exposed to the model (de-identified fields only) ───────────────
WP2_SCHEMA = """
Tables in the WP2 research database (de-identified, read-only):

infants (one row per infant):
  l1_infant_id TEXT, l1_gestational_age_weeks INTEGER, l1_gestational_age_days INTEGER,
  l1_birth_weight_g REAL, l1_sex TEXT, l1_primary_diagnosis TEXT,
  l1_brain_injury_ivh TEXT, l1_brain_injury_pvl TEXT, l1_cld_bpd TEXT,
  l1_sepsis_confirmed TEXT, l1_rop_result TEXT, l1_hearing_result TEXT,
  l1_discharge_los INTEGER, l1_antenatal_corticosteroids TEXT, l1_surfactant TEXT

sessions (one row per session):
  session_id TEXT, l1_infant_id TEXT,
  l2_session_datetime TEXT, l2_session_number INTEGER,
  l2_intervention_type TEXT, l2_protocol_id TEXT,
  l2_ambient_noise TEXT, l2_lighting TEXT,
  l2_corrected_gestational_age REAL, l2_respiratory_support TEXT, l2_fio2 REAL,
  l2_skin_to_skin TEXT, l2_parent_present TEXT,
  l4_behavioural_state_start TEXT, l4_behavioural_state_end TEXT,
  l4_session_tolerated TEXT,
  l5_overall_outcome TEXT, l5_clinician_impression TEXT,
  l5_free_text_notes TEXT, l5_adverse_event TEXT,
  l6_parental_anxiety INTEGER, l6_parent_participation TEXT,
  l7_eeg_recording_linked TEXT, l7_eeg_quality_flag TEXT,
  l8_completeness_score REAL, l8_consistency_check TEXT

intervention_units (one row per stimulus block):
  unit_id TEXT, session_id TEXT, l1_infant_id TEXT, unit_order INTEGER,
  l3_unit_condition TEXT, l3_unit_duration REAL, l3_unit_delivery_mode TEXT,
  l3music_spl_at_incubator REAL,
  l4_heart_rate_pre_bpm REAL, l4_heart_rate_during_bpm REAL, l4_heart_rate_post_bpm REAL,
  l4_spo2_pre_pct REAL, l4_spo2_during_pct REAL, l4_spo2_post_pct REAL,
  l4_stress_signs TEXT, l4_engagement_signs TEXT

Coded fields use concept codes (e.g. COND_CLASSICAL, ITYPE_MUSIC, OUT_COMPLETE).
All queries must use is_void=0 filter on infants and sessions.
"""

# ── Guardrail check ───────────────────────────────────────────────────────────
CLINICAL_KEYWORDS = [
    "diagnos", "treat", "recommend", "prognos", "prescri", "should i",
    "what dose", "medication", "therapy for", "clinical decision",
    "intervention for", "risk of", "survival", "mortality prediction"
]

def is_clinical_request(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in CLINICAL_KEYWORDS)


# ── Ollama availability check ─────────────────────────────────────────────────
def check_ollama() -> tuple[bool, str]:
    try:
        import urllib.request
        req = urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2)
        data = json.loads(req.read())
        models = [m["name"] for m in data.get("models", [])]
        llama_models = [m for m in models if "llama3" in m.lower() or "llama-3" in m.lower()]
        if llama_models:
            return True, llama_models[0]
        elif models:
            return True, models[0]
        else:
            return False, "Ollama running but no models installed. Run: ollama pull llama3"
    except Exception as e:
        return False, f"Ollama not running. Start with: ollama serve"


# ── Call Ollama ───────────────────────────────────────────────────────────────
def call_ollama(prompt: str, model: str, system: str = SYSTEM_PROMPT) -> str:
    import urllib.request
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt}
        ],
        "stream": False
    }).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["message"]["content"].strip()


# ── Log AI interaction ────────────────────────────────────────────────────────
def log_ai(user_prompt: str, generated_sql: str | None,
           retrieved_ids: str | None, llm_response: str,
           guardrail_triggered: bool, model_version: str) -> None:
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            INSERT INTO sys_ai_audit_trail
                (timestamp, user_id, user_prompt, generated_sql, retrieved_note_ids,
                 llm_response, guardrail_triggered, model_version,
                 vocabulary_version, schema_version)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            "USR_AI",
            user_prompt[:1000],
            generated_sql,
            retrieved_ids,
            llm_response[:2000],
            1 if guardrail_triggered else 0,
            model_version,
            "1.1.0", "1.1"
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════════════
# PIPELINE A - Text-to-SQL over DuckDB (structured queries)
# ═════════════════════════════════════════════════════════════════════════════
def pipeline_a_query(question: str, model: str) -> dict:
    """
    Translate a natural-language question to SQL, execute read-only on DuckDB,
    return result + generated SQL.
    """
    import duckdb

    # Guardrail check
    if is_clinical_request(question):
        msg = ("Error: This request falls outside the retrieval scope of the "
               "WP2 platform. Clinical recommendations are strictly out of scope.")
        log_ai(question, None, None, msg, True, model)
        return {"answer": msg, "sql": None, "guardrail": True}

    # Ask model to generate SQL
    sql_prompt = f"""You are a SQL expert for the WP2 neonatal research database.
Generate a single valid DuckDB SQL query to answer this question.
Return ONLY the SQL query, nothing else - no explanation, no markdown.

Database schema:
{WP2_SCHEMA}

Question: {question}

Important rules:
- Always filter: infants.is_void=0 and sessions.is_void=0
- Use concept codes in WHERE clauses (e.g. l3_unit_condition = 'COND_CLASSICAL')
- Only SELECT queries allowed
- Reference tables as: infants, sessions, intervention_units
"""

    try:
        sql = call_ollama(sql_prompt, model, system="You are a SQL generator. Return only valid SQL.")
        # Clean up markdown fences if model added them
        sql = re.sub(r"```sql\s*|```\s*", "", sql).strip()

        # Safety: reject any write operations
        sql_upper = sql.upper()
        forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"]
        for kw in forbidden:
            if kw in sql_upper:
                msg = f"Generated SQL contained forbidden keyword '{kw}' - blocked."
                log_ai(question, sql, None, msg, True, model)
                return {"answer": msg, "sql": sql, "guardrail": True}

        # Execute via DuckDB read-only
        dc = duckdb.connect(":memory:")
        dc.execute(f"ATTACH '{DB_PATH}' AS wp2 (TYPE SQLITE, READ_ONLY TRUE)")

        # Prefix table names with wp2. if not already done
        if "wp2." not in sql:
            for tbl in ["infants", "sessions", "intervention_units"]:
                sql = re.sub(rf'\b{tbl}\b', f'wp2.{tbl}', sql)

        result = dc.execute(sql).fetchdf()
        dc.close()

        # Format result as natural language via model
        result_str = result.to_string(index=False) if not result.empty else "No results found."

        answer_prompt = f"""The user asked: {question}

The SQL query returned:
{result_str}

Write a clear, concise natural-language answer based on these results.
Do not add any clinical interpretation or recommendations."""

        answer = call_ollama(answer_prompt, model)
        log_ai(question, sql, None, answer, False, model)
        return {"answer": answer, "sql": sql, "result_df": result, "guardrail": False}

    except Exception as e:
        msg = f"Query error: {e}"
        log_ai(question, None, None, msg, False, model)
        return {"answer": msg, "sql": None, "guardrail": False}


# ═════════════════════════════════════════════════════════════════════════════
# PIPELINE B - Semantic RAG over free-text notes (ChromaDB)
# ═════════════════════════════════════════════════════════════════════════════
def check_chromadb() -> bool:
    try:
        import chromadb
        return True
    except ImportError:
        return False


def index_notes(force: bool = False) -> tuple[bool, str]:
    """
    Index all l5_free_text_notes into ChromaDB using local embeddings.
    Returns (success, message).
    """
    try:
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))

        embed_fn = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"  # lightweight local model, CPU-friendly
        )

        collection = client.get_or_create_collection(
            name="wp2_session_notes",
            embedding_function=embed_fn
        )

        # Fetch notes from DB
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("""
            SELECT session_id, l1_infant_id, l2_session_datetime,
                   l5_free_text_notes
            FROM sessions
            WHERE l5_free_text_notes IS NOT NULL
              AND l5_free_text_notes != ''
              AND is_void = 0
        """).fetchall()
        conn.close()

        if not rows:
            return False, "No free-text notes to index yet."

        # Check existing
        existing_ids = set(collection.get()["ids"])
        new_docs, new_ids, new_metas = [], [], []

        for session_id, infant_id, dt, notes in rows:
            if session_id not in existing_ids or force:
                new_docs.append(notes)
                new_ids.append(session_id)
                new_metas.append({
                    "session_id": session_id,
                    "infant_id": infant_id,
                    "datetime": str(dt)
                })

        if new_docs:
            collection.upsert(documents=new_docs, ids=new_ids, metadatas=new_metas)
            return True, f"Indexed {len(new_docs)} note(s). Total: {len(existing_ids) + len(new_docs)}."
        else:
            return True, f"Index up to date ({len(existing_ids)} notes indexed)."

    except ImportError:
        return False, "chromadb not installed. Run: pip install chromadb sentence-transformers"
    except Exception as e:
        return False, f"Indexing error: {e}"


def pipeline_b_query(question: str, model: str, k: int = 5) -> dict:
    """
    Semantic search over free-text notes via ChromaDB,
    then synthesise answer with Llama 3.
    """
    if is_clinical_request(question):
        msg = ("Error: This request falls outside the retrieval scope of the "
               "WP2 platform. Clinical recommendations are strictly out of scope.")
        log_ai(question, None, None, msg, True, model)
        return {"answer": msg, "sources": [], "guardrail": True}

    try:
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        embed_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        collection = client.get_collection(
            name="wp2_session_notes",
            embedding_function=embed_fn
        )

        results = collection.query(query_texts=[question], n_results=min(k, collection.count()))
        docs     = results["documents"][0]
        metas    = results["metadatas"][0]
        distances = results["distances"][0]

        if not docs:
            return {"answer": "No relevant notes found.", "sources": [], "guardrail": False}

        # Build context for the model
        context_parts = []
        source_ids = []
        for doc, meta, dist in zip(docs, metas, distances):
            sid = meta.get("session_id", "?")
            iid = meta.get("infant_id", "?")
            dt  = meta.get("datetime", "")[:10]
            context_parts.append(f"[Session {sid} | Infant {iid} | {dt}]:\n{doc}")
            source_ids.append(sid)

        context = "\n\n".join(context_parts)

        synthesis_prompt = f"""The user asked: {question}

Here are the most relevant session notes from the WP2 research database:

{context}

Write a concise factual summary answering the question based only on these notes.
Cite the session IDs you used.
Do not add clinical interpretations or recommendations."""

        answer = call_ollama(synthesis_prompt, model)
        log_ai(question, None, json.dumps(source_ids), answer, False, model)

        return {
            "answer": answer,
            "sources": list(zip(source_ids, docs, distances)),
            "guardrail": False
        }

    except Exception as e:
        msg = f"RAG error: {e}"
        log_ai(question, None, None, msg, False, model)
        return {"answer": msg, "sources": [], "guardrail": False}


# ═════════════════════════════════════════════════════════════════════════════
# FEATURE 1 - Free-text summarisation
# ═════════════════════════════════════════════════════════════════════════════
def summarise_notes(session_id: str, notes: str, model: str) -> dict:
    """
    Summarise free-text notes and suggest structured field values.
    No auto-write - suggestions only.
    """
    if not notes or not notes.strip():
        return {"suggestions": [], "summary": "No notes to summarise."}

    prompt = f"""You are reviewing a free-text clinical research note from a NICU session.
Extract structured information and suggest values for the following fields:
- Overall session outcome (Complete / Partial / Aborted-infant / Aborted-clinical)
- Clinician global impression (1-Very poor / 2-Poor / 3-Neutral / 4-Good / 5-Very good)
- Stress signs observed (Yes/No)
- Engagement signs observed (Yes/No)
- Adverse event (Yes/No)

Note text:
\"\"\"{notes}\"\"\"

Respond in JSON format:
{{
  "summary": "one sentence summary of the note",
  "suggestions": [
    {{"field": "field_name", "suggested_value": "value", "confidence": "high/medium/low", "reason": "brief reason"}}
  ]
}}
Return only valid JSON, nothing else."""

    try:
        raw = call_ollama(prompt, model, system="You are a JSON generator for clinical research data. Return only valid JSON.")
        raw = re.sub(r"```json\s*|```\s*", "", raw).strip()
        result = json.loads(raw)
        log_ai(f"summarise:{session_id}", None, None, str(result), False, model)
        return result
    except Exception as e:
        return {"suggestions": [], "summary": f"Summarisation error: {e}"}


# ═════════════════════════════════════════════════════════════════════════════
# FEATURE 2 - Missing/inconsistent entry detection
# ═════════════════════════════════════════════════════════════════════════════
def detect_issues(session_record: dict, model: str) -> list[str]:
    """
    Scan a session record and list missing or inconsistent fields.
    Complements (does not replace) the rule-based validation engine.
    """
    # Rule-based quick checks first (no model needed)
    issues = []

    outcome = session_record.get("l5_overall_outcome")
    tolerated = session_record.get("l4_session_tolerated")
    adverse = session_record.get("l5_adverse_event")

    if tolerated == "No" and outcome == "OUT_COMPLETE":
        issues.append("Session not tolerated but outcome is Complete - please verify")
    if adverse == "Yes" and outcome == "OUT_COMPLETE":
        issues.append("Adverse event flagged but outcome is Complete - please verify")
    if not session_record.get("l2_clinician_id"):
        issues.append("Clinician ID is missing")
    if not session_record.get("l2_ambient_noise"):
        issues.append("Ambient noise level not recorded")
    if not session_record.get("l4_behavioural_state_start"):
        issues.append("Behavioural state at session start not recorded")
    if not session_record.get("l5_clinician_impression"):
        issues.append("Clinician global impression not recorded")

    # AI-assisted scan for subtler issues
    try:
        record_str = json.dumps({
            k: v for k, v in session_record.items()
            if v is not None and not k.startswith("l8_")
        }, indent=2)

        prompt = f"""Review this research session record and identify any missing, 
implausible, or internally inconsistent fields. 
Be concise - list only genuine issues, not style preferences.

Record:
{record_str}

Return a JSON array of strings, each describing one issue.
Example: ["Heart rate during is higher than pre and post by >40 bpm - unusual", "No EEG quality flag despite EEG being linked"]
Return [] if no issues found."""

        raw = call_ollama(prompt, model, system="You are a data quality checker. Return only a JSON array.")
        raw = re.sub(r"```json\s*|```\s*", "", raw).strip()
        ai_issues = json.loads(raw)
        if isinstance(ai_issues, list):
            issues.extend(ai_issues)
    except Exception:
        pass  # Rule-based issues already collected above

    log_ai(f"detect_issues:{session_record.get('session_id','?')}",
           None, None, str(issues), False, model)
    return issues
