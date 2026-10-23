from flask import Flask, request, redirect, url_for, render_template_string
import sqlite3
import json
from datetime import datetime, timezone

app = Flask(__name__)
DB = "namecheck.db"

# Four official hackathon scenarios.
# All results below are synthetic test fixtures.
SCENARIOS = {
    "TC1": {
        "title": "Name free everywhere",
        "name": "SilverLeaf Innovations",
        "expected": "Green across the matrix",
        "evidence": [
            ("Domain", "Available", "D-TC1", "No premium price in fixture",
             "https://example.com/demo/domain-tc1"),
            ("Trademark", "Clear in test data", "T-TC1", "No similar mark in fixture",
             "https://example.com/demo/trademark-tc1"),
            ("Social", "Available in test data", "S-TC1", "No matching profile in fixture",
             "https://example.com/demo/social-tc1"),
        ],
    },
    "TC2": {
        "title": "Similar mark in the same class",
        "name": "GreenNest",
        "expected": "Trademark risk flagged",
        "evidence": [
            ("Domain", "Available", "D-TC2", "Synthetic registrar response",
             "https://example.com/demo/domain-tc2"),
            ("Trademark", "Risk found", "T-TC2",
             "Similar mark: Green Nest; same-class conflict requires review",
             "https://example.com/demo/trademark-tc2"),
            ("Social", "Unchecked", "S-TC2", "No verified source response",
             "https://example.com/demo/social-tc2"),
        ],
    },
    "TC3": {
        "title": "Domain available at premium price",
        "name": "BrightOrbit",
        "expected": "Premium domain price shown",
        "evidence": [
            ("Domain", "Premium", "D-TC3",
             "Illustrative premium price: INR 25000 per year",
             "https://example.com/demo/domain-tc3"),
            ("Trademark", "Unchecked", "T-TC3", "Not checked in this scenario",
             "https://example.com/demo/trademark-tc3"),
            ("Social", "Unchecked", "S-TC3", "Not checked in this scenario",
             "https://example.com/demo/social-tc3"),
        ],
    },
    "TC4": {
        "title": "Trademark site down",
        "name": "NovaField",
        "expected": "Trademark marked unchecked",
        "evidence": [
            ("Domain", "Available", "D-TC4", "Synthetic registrar response",
             "https://example.com/demo/domain-tc4"),
            ("Trademark", "Unchecked", "T-TC4",
             "Simulated source outage; availability cannot be concluded",
             "https://example.com/demo/trademark-tc4"),
            ("Social", "Unchecked", "S-TC4", "Not checked in this scenario",
             "https://example.com/demo/social-tc4"),
        ],
    },
}


def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def setup_database():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id TEXT NOT NULL,
                input_name TEXT NOT NULL,
                expected TEXT NOT NULL,
                actual TEXT NOT NULL,
                outcome TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                record_id TEXT NOT NULL,
                risk_note TEXT NOT NULL,
                source_url TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(id)
            )
        """)


def assess(test_id, records):
    by_source = {r[0]: r[1] for r in records}

    if test_id == "TC1":
        passed = all(
            by_source.get(source) in
            ("Available", "Clear in test data", "Available in test data")
            for source in ("Domain", "Trademark", "Social")
        )
        return "Green across the matrix", passed

    if test_id == "TC2":
        passed = by_source.get("Trademark") == "Risk found"
        return "Trademark risk flagged" if passed else "Trademark risk not flagged", passed

    if test_id == "TC3":
        domain_note = next((r[3] for r in records if r[0] == "Domain"), "")
        passed = (
            by_source.get("Domain") == "Premium"
            and "INR" in domain_note
        )
        return "Premium domain price shown" if passed else "Premium price missing", passed

    if test_id == "TC4":
        passed = by_source.get("Trademark") == "Unchecked"
        return "Trademark marked unchecked" if passed else "Trademark status incorrect", passed

    return "Unknown scenario", False


def save_run(test_id):
    scenario = SCENARIOS[test_id]
    records = scenario["evidence"]
    actual, passed = assess(test_id, records)

    # Keep expected and actual results separate.
    with connect() as con:
        cursor = con.execute("""
            INSERT INTO runs
            (test_id, input_name, expected, actual, outcome, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            test_id,
            scenario["name"],
            scenario["expected"],
            actual,
            "PASS" if passed else "FAIL",
            datetime.now(timezone.utc).isoformat()
        ))
        run_id = cursor.lastrowid

        for source, status, record_id, note, source_url in records:
            con.execute("""
                INSERT INTO evidence
                (run_id, source, status, record_id, risk_note, source_url)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (run_id, source, status, record_id, note, source_url))

    return run_id


PAGE = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NameCheck AI</title>
<style>
body { font-family: Arial; background: #eef3f9; margin: 0; padding: 22px; }
main { max-width: 950px; margin: auto; }
.card { background: white; padding: 20px; border-radius: 12px; margin: 14px 0; }
h1, h2 { color: #173c67; }
button { padding: 10px 14px; border: 0; border-radius: 7px;
         background: #176bce; color: white; cursor: pointer; margin: 4px; }
table { width: 100%; border-collapse: collapse; background: white; }
th, td { text-align: left; padding: 10px; border-bottom: 1px solid #ddd; }
a { overflow-wrap: anywhere; }
.note { color: #76501b; background: #fff3d9; padding: 12px; border-radius: 8px; }
.small { color: #555; font-size: 13px; }
</style>
</head>
<body>
<main>
<h1>🔎 NameCheck AI</h1>
<p>Business Name Availability Checker — hackathon prototype</p>
<p class="note"><b>Demo mode:</b> All scenario evidence is synthetic.
It does not represent live registrar, trademark or social-profile results.
Example.com URLs are placeholders, not official evidence.</p>

<section class="card">
<h2>Run official test scenarios</h2>
<form method="post" action="/check-name">
    <label for="business_name">Enter your business name:</label>
    <input
        type="text"
        id="business_name"
        name="business_name"
        placeholder="e.g. MyStartup Innovations"
        required
    >
    <button type="submit">Check Name</button>
</form>
<section class="card">
    <h2>Official Verification Sources</h2>

    <p>
        <a href="https://www.mca.gov.in/" target="_blank">
            Ministry of Corporate Affairs (MCA)
        </a>
        — Check company names.
    </p>

    <p>
        <a href="https://tmrsearch.ipindia.gov.in/tmrpublicsearch"
           target="_blank">
            IP India Trademark Search
        </a>
        — Check similar trademarks.
    </p>

    <p>
        <a href="https://www.cloudflare.com/products/registrar/"
           target="_blank">
            Cloudflare Registrar
        </a>
        — Domain registration information.
    </p>

    <p class="note">
        These links open external websites.
        Results have not been checked automatically.
    </p>
</section>
{% for tid, scenario in scenarios.items() %}
<form method="post" action="/run/{{ tid }}" style="display:inline">
<button type="submit">{{ tid }} — {{ scenario.title }}</button>
</form>
{% endfor %}
</section>
<section class="card">
    <h2>Official Verification Sources</h2>

    <p>
        <a href="https://www.mca.gov.in/" target="_blank">
            Ministry of Corporate Affairs (MCA)
        </a>
        — Check company information.
    </p>

    <p>
        <a href="https://tmrsearch.ipindia.gov.in/tmrpublicsearch"
           target="_blank">
            IP India Trademark Search
        </a>
        — Search for similar trademarks.
    </p>

    <p>
        <a href="https://www.cloudflare.com/products/registrar/"
           target="_blank">
            Cloudflare Registrar
        </a>
        — Check domain registration information.
    </p>

    <p class="note">
        These links open external websites.
        Results are not checked automatically by this prototype.
    </p>
</section>
{% if run %}
<section class="card">
<h2>Run #{{ run.id }} — {{ run.test_id }}</h2>
<p><b>Input record:</b> IN-{{ run.id }}</p>
<p><b>Business name:</b> {{ run.input_name }}</p>
<p><b>Expected result:</b> {{ run.expected }}</p>
<p><b>Actual result:</b> {{ run.actual }}</p>
<p><b>Test outcome:</b> {{ run.outcome }}</p>
<p><b>Run time:</b> {{ run.created_at }}</p>
{% if run.outcome == 'FAIL' %}
<p class="note">Mismatch: the actual result did not satisfy the scenario's
acceptance check. Investigate before presenting it as a successful run.</p>
{% endif %}
<h3>Availability matrix and evidence</h3>
<p class="note">
    Demo Mode: These results use simulated test data.
    Live domain, trademark, and social media checks have
    not been performed. Verify results using official sources.
</p>
<table>
<tr><th>Source</th><th>Status</th><th>Evidence ID</th><th>Risk note</th><th>Source URL</th></tr>
{% for e in evidence %}
<tr>
<td>{{ e.source }}</td>
<td>{{ e.status }}</td>
<td>{{ e.record_id }} / EV-{{ e.id }}</td>
<td>{{ e.risk_note }}</td>
<td><a href="{{ e.source_url }}" target="_blank">{{ e.source_url }}</a></td>
</tr>
{% endfor %}
</table>
<p class="small">Evidence is linked to run #{{ run.id }} and input IN-{{ run.id }}.</p>
</section>
{% endif %}

<section class="card">
<h2>Previous saved runs</h2>
{% if runs %}
<table>
<tr><th>Run</th><th>Test</th><th>Input</th><th>Expected</th><th>Actual</th><th>Outcome</th></tr>
{% for r in runs %}
<tr>
<td><a href="/run/{{ r.id }}">#{{ r.id }}</a></td>
<td>{{ r.test_id }}</td><td>{{ r.input_name }}</td>
<td>{{ r.expected }}</td><td>{{ r.actual }}</td><td>{{ r.outcome }}</td>
</tr>
{% endfor %}
</table>
{% else %}
<p>No runs yet. Choose a test case above.</p>
{% endif %}
</section>
</main>
</body>
</html>
"""


@app.route("/")
def home():
    with connect() as con:
        runs = con.execute("SELECT * FROM runs ORDER BY id DESC").fetchall()
    return render_template_string(PAGE, scenarios=SCENARIOS, runs=runs,
                                  run=None, evidence=[])

@app.route("/check-name", methods=["POST"])
def check_name():
    business_name = request.form.get("business_name", "").strip()

    if not business_name:
        return "Please enter a business name.", 400

    return (
        f"<h2>Business Name Check</h2>"
        f"<p>Entered name: {business_name}</p>"
        f"<p>Demo Mode: Live domain, trademark, and social checks "
        f"have not been performed.</p>"
        f'<p><a href="/">Back to Home</a></p>'
    )
@app.route("/run/<test_id>", methods=["POST"])
def run_scenario(test_id):
    if test_id not in SCENARIOS:
        return "Unknown test case", 404

    run_id = save_run(test_id)
    return redirect(url_for("show_run", run_id=run_id))


@app.route("/run/<int:run_id>")
def show_run(run_id):
    with connect() as con:
        run = con.execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        if run is None:
            return "Run not found", 404
        evidence = con.execute(
            "SELECT * FROM evidence WHERE run_id = ? ORDER BY id",
            (run_id,)
        ).fetchall()
        runs = con.execute("SELECT * FROM runs ORDER BY id DESC").fetchall()

    return render_template_string(PAGE, scenarios=SCENARIOS, runs=runs,
                                  run=run, evidence=evidence)


setup_database()

if __name__ == "__main__":
    app.run(debug=True)