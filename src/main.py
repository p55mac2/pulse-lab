import logging
import os
import sys
from pathlib import Path

import psycopg2
from flask import (
    Flask,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("pulse-check")

app = Flask(__name__)


def db_configured():
    return bool(os.getenv("DATABASE_URL"))


def db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def init_db():
    if not db_configured():
        log.warning("DATABASE_URL is not set — starting without a database.")
        return
    try:
        schema = (Path(__file__).parent.parent / "schema.sql").read_text()
        with db() as conn, conn.cursor() as cur:
            # serialize workers: IF NOT EXISTS races at the catalog level
            cur.execute("SELECT pg_advisory_lock(4414)")
            cur.execute(schema)
            cur.execute("SELECT pg_advisory_unlock(4414)")
        log.info("Schema applied.")
    except Exception:
        log.exception("Could not apply schema at startup.")


def current_player(cur, player_id):
    if not player_id:
        return None
    cur.execute(
        """
        SELECT id, handle, company, fav_food, fav_movie, fav_holiday
        FROM players WHERE id = %s
        """,
        (player_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    keys = ("id", "handle", "company", "fav_food", "fav_movie", "fav_holiday")
    return dict(zip(keys, row))


def player_stats(cur, player_id):
    cur.execute(
        """
        SELECT COUNT(*), COALESCE(MAX(score), 0)
        FROM attempts WHERE player_id = %s
        """,
        (player_id,),
    )
    count, best = cur.fetchone()
    cur.execute(
        """
        SELECT target_seconds, delta_seconds, score, played_at
        FROM attempts WHERE player_id = %s
        ORDER BY played_at DESC LIMIT 5
        """,
        (player_id,),
    )
    recent = [
        {"target": t, "delta": d, "score": s, "played_at": p}
        for t, d, s, p in cur.fetchall()
    ]
    return {"count": count, "best": best, "recent": recent}


def leaderboard(cur, limit=10):
    """Best score per player across everyone in this database."""
    cur.execute(
        """
        SELECT p.id, p.handle, p.company, MAX(a.score), COUNT(*)
        FROM attempts a JOIN players p ON p.id = a.player_id
        GROUP BY p.id, p.handle, p.company
        ORDER BY MAX(a.score) DESC, p.handle
        LIMIT %s
        """,
        (limit,),
    )
    return [
        {"player_id": i, "handle": h, "company": c, "best": b, "attempts": n}
        for i, h, c, b, n in cur.fetchall()
    ]


@app.get("/")
def index():
    if not db_configured():
        return render_template("index.html", player=None, no_database=True)
    player_id = request.cookies.get("player_id")
    with db() as conn, conn.cursor() as cur:
        player = current_player(cur, player_id)
        if not player:
            resp = make_response(render_template("index.html", player=None))
            resp.delete_cookie("player_id")
            return resp
        stats = player_stats(cur, player["id"])
        board = leaderboard(cur)
    return render_template(
        "index.html",
        player=player,
        stats=stats,
        board=board,
        save_error=request.args.get("save_error") == "1",
    )


@app.post("/register")
def register():
    handle = request.form.get("handle", "").strip()
    company = request.form.get("company", "").strip()
    fav_food = request.form.get("fav_food", "").strip()
    fav_movie = request.form.get("fav_movie", "").strip()
    fav_holiday = request.form.get("fav_holiday", "").strip()
    if not handle:
        return redirect(url_for("index"))
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO players (handle, company, fav_food, fav_movie, fav_holiday)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (handle) DO UPDATE SET
                    company = EXCLUDED.company, fav_food = EXCLUDED.fav_food,
                    fav_movie = EXCLUDED.fav_movie, fav_holiday = EXCLUDED.fav_holiday
                RETURNING id
                """,
                (handle, company, fav_food, fav_movie, fav_holiday),
            )
            player_id = cur.fetchone()[0]
    except Exception:
        log.exception("Failed to register player handle=%r", handle)
        return "Registration failed — see application logs.", 500
    resp = make_response(redirect(url_for("index")))
    resp.set_cookie("player_id", str(player_id), max_age=60 * 60 * 24)
    log.info("Player registered: handle=%r id=%s", handle, player_id)
    return resp


@app.post("/score")
def score():
    player_id = request.cookies.get("player_id")
    target = request.form.get("target", "")
    delta = request.form.get("delta", "")
    points = request.form.get("points", "")
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO attempts (player_id, target_seconds, delta_seconds, score)
                VALUES (%s, %s, %s, %s)
                """,
                (player_id, target, delta, points),
            )
    except Exception:
        log.exception(
            "Failed to save attempt: player_id=%r target=%r delta=%r points=%r",
            player_id,
            target,
            delta,
            points,
        )
        return redirect(url_for("index", save_error=1))
    log.info("Attempt saved: player_id=%s target=%s delta=%s points=%s", player_id, target, delta, points)
    return redirect(url_for("index"))


@app.get("/health")
def health():
    if not db_configured():
        return jsonify(status="degraded", reason="database not configured"), 503
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return jsonify(status="ok")
    except Exception:
        log.exception("Health check failed")
        return jsonify(status="degraded"), 503


@app.get("/summary")
def summary():
    if os.getenv("INFERENCE_ENABLED", "").lower() != "true":
        return jsonify(summary="Inference summary is not enabled (set INFERENCE_ENABLED=true)."), 501
    # Stretch module: call the inference service to summarize recent play activity.
    return jsonify(summary="Inference wiring not implemented in this build."), 501


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
