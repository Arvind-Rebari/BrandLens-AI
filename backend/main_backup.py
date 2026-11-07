
import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DB_PATH = BASE_DIR / "brandlens.db"

app = FastAPI(
    title="BrandLens AI",
    description="Brand Governance and Content Review Platform",
    version="1.0.0"
)

app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="static"
)


# ---------------- DATABASE ----------------

def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                findings TEXT NOT NULL,
                status TEXT DEFAULT 'Pending',
                reviewer_note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


init_db()


# ---------------- BRAND RULES ----------------

RULES = [
    {
        "pattern": r"\b(guaranteed results?|guaranteed success)\b",
        "category": "Unsupported Claim",
        "severity": "High",
        "explanation": "Guarantees may create unrealistic expectations without verified evidence.",
        "suggestion": "Replace with a specific, evidence-backed statement."
    },
    {
        "pattern": r"\b(100% results?|100 percent guaranteed)\b",
        "category": "Unsupported Claim",
        "severity": "High",
        "explanation": "Absolute performance claims require strong supporting evidence.",
        "suggestion": "Use a measurable and verifiable claim instead."
    },
    {
        "pattern": r"\b(cure|cures|cured)\b",
        "category": "Risky Claim",
        "severity": "High",
        "explanation": "Medical or health-related claims need appropriate evidence and approval.",
        "suggestion": "Use approved and verified product information."
    },
    {
        "pattern": r"\b(best in the world|number one|no\.?\s*1)\b",
        "category": "Promotional Claim",
        "severity": "Medium",
        "explanation": "Ranking claims should be supported by reliable evidence.",
        "suggestion": "Add a verifiable source or use more balanced wording."
    },
    {
        "pattern": r"\b(free forever|free for life)\b",
        "category": "Pricing Claim",
        "severity": "Medium",
        "explanation": "Pricing promises must match the approved pricing policy.",
        "suggestion": "Clarify the actual pricing conditions."
    },
    {
        "pattern": r"\b(limited time only|act now|buy now)\b",
        "category": "Messaging",
        "severity": "Low",
        "explanation": "Urgency-based messaging should be accurate and appropriate.",
        "suggestion": "Use clear and informative messaging."
    },
    {
        "pattern": r"\b(cheap|dirt cheap)\b",
        "category": "Brand Tone",
        "severity": "Low",
        "explanation": "This wording may not match a premium or professional brand voice.",
        "suggestion": "Consider using 'affordable' or 'value-focused'."
    }
]

PREFERRED_TERMS = {
    "cheap": "affordable",
    "guys": "everyone",
    "crazy": "remarkable"
}


# ---------------- ANALYSIS ENGINE ----------------

def analyze_content(content):
    findings = []

    for rule in RULES:
        matches = re.finditer(
            rule["pattern"],
            content,
            flags=re.IGNORECASE
        )

        for match in matches:
            findings.append({
                "category": rule["category"],
                "severity": rule["severity"],
                "matched_text": match.group(0),
                "explanation": rule["explanation"],
                "suggestion": rule["suggestion"]
            })

    for term, replacement in PREFERRED_TERMS.items():
        for match in re.finditer(
            rf"\b{re.escape(term)}\b",
            content,
            flags=re.IGNORECASE
        ):
            findings.append({
                "category": "Terminology",
                "severity": "Low",
                "matched_text": match.group(0),
                "explanation": f"'{term}' is not the preferred brand terminology.",
                "suggestion": f"Replace '{term}' with '{replacement}'."
            })

    severity_weights = {
        "High": 25,
        "Medium": 12,
        "Low": 5
    }

    raw_score = sum(
        severity_weights[item["severity"]]
        for item in findings
    )

    risk_score = min(raw_score, 100)

    if risk_score >= 50:
        risk_level = "High"
    elif risk_score >= 20:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "findings": findings,
        "total_findings": len(findings)
    }


# ---------------- REQUEST MODELS ----------------

class AnalyzeRequest(BaseModel):
    title: str = Field(default="Untitled Content", max_length=150)
    content: str = Field(min_length=3, max_length=15000)


class ReviewRequest(BaseModel):
    action: str
    note: str = Field(default="", max_length=1000)


# ---------------- ROUTES ----------------

@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "application": "BrandLens AI",
        "version": "1.0.0"
    }


@app.post("/api/analyze")
def create_analysis(request: AnalyzeRequest):
    result = analyze_content(request.content)

    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        cursor = db.execute("""
            INSERT INTO reviews
            (title, content, risk_score, risk_level, findings,
             status, reviewer_note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.title,
            request.content,
            result["risk_score"],
            result["risk_level"],
            json.dumps(result["findings"]),
            "Pending",
            "",
            now,
            now
        ))

        review_id = cursor.lastrowid

    return {
        "id": review_id,
        "title": request.title,
        "status": "Pending",
        **result
    }


@app.get("/api/history")
def get_history():
    with get_db() as db:
        rows = db.execute("""
            SELECT id, title, risk_score, risk_level,
                   status, created_at
            FROM reviews
            ORDER BY id DESC
            LIMIT 100
        """).fetchall()

    return [dict(row) for row in rows]


@app.get("/api/stats")
def get_stats():
    with get_db() as db:
        total = db.execute(
            "SELECT COUNT(*) FROM reviews"
        ).fetchone()[0]

        pending = db.execute(
            "SELECT COUNT(*) FROM reviews WHERE status='Pending'"
        ).fetchone()[0]

        high = db.execute(
            "SELECT COUNT(*) FROM reviews WHERE risk_level='High'"
        ).fetchone()[0]

        approved = db.execute(
            "SELECT COUNT(*) FROM reviews WHERE status='Approved'"
        ).fetchone()[0]

    return {
        "total": total,
        "pending": pending,
        "high_risk": high,
        "approved": approved
    }


@app.get("/api/reviews/{review_id}")
def get_review(review_id: int):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM reviews WHERE id=?",
            (review_id,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Review not found")

    result = dict(row)
    result["findings"] = json.loads(result["findings"])
    return result


@app.patch("/api/reviews/{review_id}")
def update_review(review_id: int, request: ReviewRequest):
    if request.action not in ["approve", "request_changes"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid review action"
        )

    new_status = (
        "Approved"
        if request.action == "approve"
        else "Changes Requested"
    )

    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        cursor = db.execute("""
            UPDATE reviews
            SET status=?, reviewer_note=?, updated_at=?
            WHERE id=?
        """, (
            new_status,
            request.note,
            now,
            review_id
        ))

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Review not found"
            )

    return {
        "success": True,
        "id": review_id,
        "status": new_status,
        "message": "Review status updated successfully"
    }
