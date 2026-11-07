
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
    version="1.1.0"
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
# These rules detect specific text patterns.
# Scores are calculated only when a rule is triggered.

RULES = [
    {
        "pattern": r"\b(guaranteed results?|guaranteed success|guarantees success)\b",
        "category": "Unsupported Claims",
        "severity": "High",
        "explanation": "This wording promises a guaranteed outcome. Such a claim should have strong supporting evidence.",
        "suggestion": "Replace the guarantee with a specific, measurable statement supported by evidence."
    },
    {
        "pattern": r"\b(100% results?|100 percent guaranteed|100% guaranteed)\b",
        "category": "Unsupported Claims",
        "severity": "High",
        "explanation": "An absolute performance claim may mislead readers if it cannot be proven.",
        "suggestion": "State the verified performance information and include supporting evidence."
    },
    {
        "pattern": r"\b(cure|cures|cured|cure[s] all)\b",
        "category": "Health and Safety Claims",
        "severity": "High",
        "explanation": "A medical or health-related claim may require appropriate scientific evidence and approval.",
        "suggestion": "Use approved health information and provide reliable supporting evidence."
    },
    {
        "pattern": r"\b(best in the world|best in india|number one|no\.?\s*1|#1)\b",
        "category": "Promotional Claims",
        "severity": "Medium",
        "explanation": "A superiority or ranking claim should be supported by a reliable source.",
        "suggestion": "Provide a verifiable source for the ranking or use more balanced wording."
    },
    {
        "pattern": r"\b(free forever|free for life|completely free)\b",
        "category": "Pricing and Offers",
        "severity": "Medium",
        "explanation": "A free-service promise should match the actual pricing terms and conditions.",
        "suggestion": "Clarify the offer duration, conditions and any applicable charges."
    },
    {
        "pattern": r"\b(50% off|70% off|90% off|100% off|huge discount|massive discount)\b",
        "category": "Pricing and Offers",
        "severity": "Medium",
        "explanation": "A discount claim should match the actual approved price and offer conditions.",
        "suggestion": "Verify the original price, discounted price and offer conditions before publishing."
    },
    {
        "pattern": r"\b(limited time only|limited time offer|act now|buy now|last chance|hurry up)\b",
        "category": "Urgency Messaging",
        "severity": "Low",
        "explanation": "Urgency-based wording should reflect a genuine deadline or stock limitation.",
        "suggestion": "Use this message only when the deadline or limitation is real and verifiable."
    },
    {
        "pattern": r"\b(cheap|dirt cheap)\b",
        "category": "Brand Tone",
        "severity": "Low",
        "explanation": "This wording may not match a professional or premium brand voice.",
        "suggestion": "Consider using 'affordable' or 'value-focused' if that matches the brand voice."
    }
]


PREFERRED_TERMS = {
    "guys": "everyone",
    "crazy": "remarkable"
}


# ---------------- RISK CALCULATION ----------------

SEVERITY_RISK = {
    "High": 35,
    "Medium": 20,
    "Low": 10
}


def calculate_combined_risk(findings):
    """
    Combines actual detected finding contributions.

    Each finding contributes according to its severity.
    Multiple findings increase the score, with a maximum of 100.
    No findings means zero detected risk.
    """

    remaining_risk = 1.0

    for finding in findings:
        contribution = SEVERITY_RISK[finding["severity"]] / 100
        remaining_risk *= (1 - contribution)

    return round((1 - remaining_risk) * 100)


def get_risk_level(score):
    if score >= 50:
        return "High"
    elif score >= 20:
        return "Medium"
    return "Low"


def build_category_scores(findings):
    """
    Returns only categories in which actual findings were detected.
    No fabricated category percentages are added.
    """

    categories = {}

    for finding in findings:
        category = finding["category"]
        categories.setdefault(category, []).append(finding)

    category_scores = []

    for category, category_findings in categories.items():
        score = calculate_combined_risk(category_findings)

        category_scores.append({
            "category": category,
            "risk_score": score,
            "risk_level": get_risk_level(score),
            "findings_count": len(category_findings)
        })

    category_scores.sort(
        key=lambda item: item["risk_score"],
        reverse=True
    )

    return category_scores


# ---------------- ANALYSIS ENGINE ----------------

def analyze_content(content):
    findings = []

    # Check configured brand rules.
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
                "start": match.start(),
                "end": match.end(),
                "explanation": rule["explanation"],
                "suggestion": rule["suggestion"],
                "risk_contribution": SEVERITY_RISK[rule["severity"]]
            })

    # Check preferred terminology.
    for term, replacement in PREFERRED_TERMS.items():
        matches = re.finditer(
            rf"\b{re.escape(term)}\b",
            content,
            flags=re.IGNORECASE
        )

        for match in matches:
            findings.append({
                "category": "Brand Terminology",
                "severity": "Low",
                "matched_text": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "explanation": (
                    f"'{term}' is not the preferred brand terminology "
                    "configured in this version."
                ),
                "suggestion": f"Consider replacing '{term}' with '{replacement}'.",
                "risk_contribution": SEVERITY_RISK["Low"]
            })

    # Keep findings in the order in which they appear in the content.
    findings.sort(key=lambda item: item["start"])

    # Calculate the overall score from actual findings.
    risk_score = calculate_combined_risk(findings)
    risk_level = get_risk_level(risk_score)

    # Only categories with detected issues are returned.
    category_scores = build_category_scores(findings)

    if findings:
        analysis_summary = (
            f"Detected {len(findings)} potential issue(s) "
            f"across {len(category_scores)} category or categories "
            "covered by the configured checks."
        )
    else:
        analysis_summary = (
            "No issues were detected by the currently configured "
            "text checks. This does not guarantee full brand compliance."
        )

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "findings": findings,
        "total_findings": len(findings),
        "category_scores": category_scores,
        "analysis_summary": analysis_summary
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
        "version": "1.1.0"
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

    # Recalculate category scores from the stored findings.
    result["category_scores"] = build_category_scores(
        result["findings"]
    )

    result["analysis_summary"] = (
        f"Stored review contains {len(result['findings'])} "
        "detected finding(s) from the configured checks."
    )

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
