"""Render dark_mode.svg / light_mode.svg with live GitHub stats."""
import json
import os
import time
from datetime import date, datetime
from xml.sax.saxutils import escape

import requests

TOKEN = os.environ.get("PROFILE_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
HEAD = {"Authorization": f"bearer {TOKEN}"}
WIDTH = 56  # characters per info line
LH = 20  # line height of the info column
cfg = json.load(open("config.json", encoding="utf-8"))
USER = cfg["username"]


def gql(query, **variables):
    r = requests.post("https://api.github.com/graphql", headers=HEAD,
                      json={"query": query, "variables": variables}, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def fetch_stats():
    d = gql("""query($u:String!){user(login:$u){createdAt followers{totalCount}
      repositories(ownerAffiliations:OWNER,first:100){totalCount nodes{name stargazerCount}}
      repositoriesContributedTo(first:1,contributionTypes:[COMMIT,PULL_REQUEST,REPOSITORY]){totalCount}}}""",
            u=USER)["user"]
    commits = 0
    for year in range(int(d["createdAt"][:4]), date.today().year + 1):
        c = gql("""query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){
          contributionsCollection(from:$f,to:$t){totalCommitContributions restrictedContributionsCount}}}""",
                u=USER, f=f"{year}-01-01T00:00:00Z", t=f"{year}-12-31T23:59:59Z")
        cc = c["user"]["contributionsCollection"]
        commits += cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
    add = dele = 0
    for repo in d["repositories"]["nodes"]:
        for _ in range(6):  # stats endpoint answers 202 while it computes
            r = requests.get(f"https://api.github.com/repos/{USER}/{repo['name']}/stats/contributors",
                             headers=HEAD, timeout=60)
            if r.status_code != 202:
                break
            time.sleep(3)
        if r.status_code == 200:
            for c in r.json():
                if c["author"] and c["author"]["login"].lower() == USER.lower():
                    add += sum(w["a"] for w in c["weeks"])
                    dele += sum(w["d"] for w in c["weeks"])
    return {
        "repos": d["repositories"]["totalCount"],
        "contrib": d["repositoriesContributedTo"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in d["repositories"]["nodes"]),
        "followers": d["followers"]["totalCount"],
        "commits": commits, "add": add, "del": dele,
    }


def uptime():
    b = datetime.strptime(cfg["birthday"], "%Y-%m-%d").date()
    t = date.today()
    months = (t.year - b.year) * 12 + t.month - b.month - (t.day < b.day)
    m = b.month - 1 + months
    anchor = date(b.year + m // 12, m % 12 + 1, min(b.day, 28))
    return f"{months // 12} years, {months % 12} months, {(t - anchor).days} days"


def render(stats, dark):
    bg, fg, key, dim, ok, bad = (
        ("#161b22", "#c9d1d9", "#58a6ff", "#616e7c", "#3fb950", "#f85149") if dark
        else ("#f6f8fa", "#24292f", "#0969da", "#8c959f", "#1a7f37", "#cf222e"))

    def span(color, text):
        return f'<tspan fill="{color}">{escape(text)}</tspan>'

    def entry(k, v, width=WIDTH):
        return span(key, k) + span(dim, " " + "." * max(width - len(k) - len(v) - 2, 2) + " ") + span(fg, v)

    def header(title):
        return span(key, title) + span(dim, " " + "—" * (WIDTH - len(title) - 1))

    rows = [header(cfg["display"])]
    for item in cfg["info"]:
        rows.append(entry(item[0] + ":", uptime() if item[1] == "@uptime" else item[1]) if item else "")
    rows += ["", header("— Contact")]
    rows += [entry(k + ":", v) for k, v in cfg["contact"]]
    rows += ["", header("— GitHub Stats")]

    s = stats
    left = [("Repos:", f"{s['repos']} {{Contributed: {s['contrib']}}}"), ("Commits:", f"{s['commits']:,}")]
    right = [("Stars:", f"{s['stars']:,}"), ("Followers:", f"{s['followers']:,}")]
    lw = max(len(k) + len(v) + 4 for k, v in left)  # shared widths keep the | aligned
    rw = max(WIDTH - 3 - lw, max(len(k) + len(v) + 4 for k, v in right))
    for (lk, lv), (rk, rv) in zip(left, right):
        rows.append(entry(lk, lv, lw) + span(dim, " | ") + entry(rk, rv, rw))
    loc, add, dele = s["add"] - s["del"], f"{s['add']:,}++", f"{s['del']:,}--"
    tail = f"{loc:,} ( {add}, {dele} )"
    rows.append(span(key, "Lines of Code:")
                + span(dim, " " + "." * max(WIDTH - len("Lines of Code:") - len(tail) - 2, 2) + " ")
                + span(fg, f"{loc:,} ( ") + span(ok, add) + span(fg, ", ") + span(bad, dele) + span(fg, " )"))

    art = open("ascii_art.txt", encoding="utf-8").read().splitlines() if os.path.exists("ascii_art.txt") else []
    h = max(len(rows) * LH, len(art) * 12) + 60
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="985" height="{h}" '
           f'font-family="Consolas, \'Courier New\', monospace">',
           f'<rect width="985" height="{h}" rx="15" fill="{bg}"/>',
           f'<text fill="{fg}" font-size="10px" xml:space="preserve">']
    out += [f'<tspan x="25" y="{35 + i * 12}">{escape(l)}</tspan>' for i, l in enumerate(art)]
    out.append(f'</text><text fill="{fg}" font-size="16px" xml:space="preserve">')
    out += [f'<tspan x="390" y="{40 + i * LH}">{r}</tspan>' for i, r in enumerate(rows)]
    out.append("</text></svg>")
    return "\n".join(out)


if __name__ == "__main__":
    stats = fetch_stats()
    for name, dark in (("dark_mode.svg", True), ("light_mode.svg", False)):
        open(name, "w", encoding="utf-8").write(render(stats, dark))
    print("ok", stats)
