# Gloucestershire Badminton League — Codebase Guide

> **How to view diagrams:** Open this file in VS Code, press `Ctrl+Shift+V` to open Markdown Preview.
> Install the **"Markdown Preview Mermaid Support"** extension (search in Extensions panel) to render the diagrams.

---

## 1. The Big Picture

There are two Django "apps" in the project:

```
glos_badminton_league_website/
│
├── leagueWebsite/          ← Project config (settings, main URLs, base template, CSS)
│   ├── settings.py
│   ├── urls.py             ← Includes league/urls.py
│   └── templates/base.html ← Every page extends this
│
└── league/                 ← The actual website (almost everything lives here)
    ├── models.py           ← Database tables
    ├── views.py            ← Page logic
    ├── urls.py             ← URL routing
    ├── forms.py            ← Input forms
    ├── admin.py            ← Django admin config
    ├── templates/league/   ← HTML pages
    └── utilities/          ← Helper functions (email, table calc, etc.)
```

---

## 2. Database Model (what data is stored and how it links together)

```mermaid
erDiagram
    Season {
        string year "e.g. 2025-2026"
        bool current "only one is True"
    }
    LeagueSettings {
        string league_status "entry / fixtures / live"
    }
    Club {
        string name
        bool teams_confirmed
    }
    Division {
        int number
        string type "Mixed / Womens / Mens"
        bool active
    }
    Team {
        int number
        string type
        time start_time
        time end_time
    }
    Player {
        string name
        string level "Womens / Mens"
    }
    Venue {
        string name
        string address
    }
    Fixture {
        datetime date_time "null until club sets it"
        int home_points
        int away_points
        string status "Unplayed / Played / Postponed etc"
    }
    TeamNomination {
        int position
        date date_from
        date date_to "null = currently active"
        bool approved
    }
    Penalty {
        string penalty_type
        int penalty_value
    }
    Administrator {
        string username
    }
    Member {
        string username
    }

    Club ||--o{ Team : owns
    Club ||--o{ Player : has
    Club ||--o{ Administrator : "admin account"
    Club ||--o{ Member : "member account"
    Division ||--o{ Team : "teams play in"
    Team }o--|| Venue : "plays home at"
    Team ||--o{ TeamNomination : "nominated players"
    Player ||--o{ TeamNomination : "nominated to"
    Season ||--o{ Fixture : "fixtures in"
    Division ||--o{ Fixture : "fixtures for"
    Team ||--o{ Fixture : "home team"
    Team ||--o{ Fixture : "away team"
    Venue ||--o{ Fixture : "hosted at"
    Season ||--o{ Penalty : "penalties in"
    Team ||--o{ Penalty : "penalised"
    Fixture }o--o| Penalty : "from"
```

---

## 3. Who Can Do What (User Roles)

There are five types of user. They share a Django `User` login but have different access:

```mermaid
flowchart TD
    Public("🌐 Public<br/>(not logged in)")
    Member("👤 Club Member<br/>linked to a Club")
    Admin("👥 Club Administrator<br/>linked to a Club")
    League("⭐ leagueAdmin<br/>username")
    Website("🔧 websiteAdmin<br/>username")

    Public -->|can view| PubPages("Fixtures · Division tables<br/>Club/Team info · Venues")

    Member -->|everything above, plus| MemPages("Submit match results<br/>View team roster")

    Admin -->|everything above, plus| AdminPages("Club admin page<br/>Set fixture dates<br/>Manage players & contacts<br/>Submit nominations<br/>Request nomination changes")

    League -->|separate login| LeaguePages("Approve/reject nomination changes<br/>Set league_status<br/>View all club contact emails<br/>Delete penalties<br/>Generate season fixtures")

    Website -->|separate login| WebPages("Upload fixture spreadsheet<br/>Access Django database admin")
```

> **Key rule:** `GenericViewMixin` (top of `views.py`) runs on every page load.
> It checks who is logged in and adds `admin`, `member`, `user`, `current_season` and `settings`
> to every template automatically — that's why `{{ admin.club }}` works on any page.

---

## 4. The Season Lifecycle (league_status)

The `LeagueSettings.league_status` field controls what features are visible to clubs.
The League Admin changes it on the League Admin page.

```mermaid
flowchart TD
    Start([New season begins]) --> entry

    subgraph entry ["🏸  TEAM ENTRY  —  league_status = 'entry'"]
        direction TB
        e1["Clubs submit team entries"]
        e2["Clubs set home venues & timings"]
        e3["League admin generates fixtures"]
        e1 --> e2 --> e3
    end

    entry -->|Teams confirmed| fixtures

    subgraph fixtures ["📋  FIXTURES & NOMINATIONS  —  league_status = 'fixtures'"]
        direction TB
        f1["Clubs set fixture dates"]
        f2["Clubs submit player nominations"]
        f3["League admin approves nominations"]
        f1 --> f2 --> f3
    end

    fixtures -->|Season starts| live

    subgraph live ["⚡  SEASON LIVE  —  league_status = 'live'"]
        direction TB
        l1["Clubs submit match results"]
        l2["Division tables update automatically"]
        l3["Clubs can request nomination changes"]
        l1 --> l2 --> l3
    end

    live --> End([Season ends])
```

---

## 5. How a Web Request Flows Through the Code

Every page visit follows the same path:

```mermaid
flowchart TD
    Browser("🌐 Browser visits a URL\ne.g. /fixtures/home")

    subgraph urls ["league/urls.py"]
        URL("Matches URL pattern\npath('fixtures/<str:pagename>', FixturesView)")
    end

    subgraph view ["league/views.py"]
        Mixin("GenericViewMixin.get_context_data\nAlways runs first ↓\nAdds: user · admin · member\ncurrent_season · settings")
        ViewLogic("View's own get_context_data\nBranches on 'pagename'\nBuilds the data for the page")
    end

    subgraph template ["league/templates/league/"]
        Template("fixtures.html\nUses context data\n{% if %} blocks show/hide sections")
    end

    Browser --> URL --> Mixin --> ViewLogic --> Template --> Response("📄 HTML sent to browser")

    POST("📮 Form submitted (POST)")
    POST --> URL2("Same URL → same View")
    URL2 --> PostMethod("view.post() method\nSaves data to database")
    PostMethod --> Redirect("redirect() back to page")
```

---

## 6. URL Structure at a Glance

Most views use a `pagename` in the URL as a **page switcher** — the same view class handles multiple sub-pages by branching on its value.

```mermaid
flowchart LR
    subgraph Public Pages
        A("/divisions/home") --> A1("List all divisions")
        B("/divisions/X1") --> B1("Mixed Div 1 table & fixtures")
        C("/fixtures/home") --> C1("All fixtures list")
        D("/fixtures/42/fix") --> D1("View fixture #42")
        E("/clubs/home") --> E1("Club list")
        F("/teams/home") --> F1("Team list")
    end

    subgraph Club Admin
        G("/clubadmin/club") --> G1("Club admin page")
        H("/fixtures/dates") --> H1("Schedule fixture dates")
        I("/nominations/teamupdate") --> I1("Submit nominations")
        J("/nominations/indiupdate/<id>") --> J1("Request player change")
    end

    subgraph League Admin
        K("/clubadmin/league") --> K1("League admin dashboard")
        L("/nominations/admin/<id>") --> L1("Approve/reject nomination")
    end

    subgraph Fixture Updates
        M("/fixtures/update/<id>/submit/fix") --> M1("Submit result")
        N("/fixtures/update/<id>/reschedule/fix") --> N1("Propose new date")
        O("/fixtures/update/<id>/options/fix") --> O1("Choose action")
    end
```

---

## 7. The Utilities Folder (helper functions)

These files contain logic that is too complex to live inside a view:

| File | What it does |
|------|-------------|
| `table.py` | Calculates division standings (W/D/L/points), handles concessions |
| `email.py` | Sends all automated emails (results, reschedules, nominations) |
| `roster.py` | Builds the player appearance stats table on the club admin page |
| `player.py` | Fuzzy-matches away player names; checks eligibility |
| `fixture.py` | Parses uploaded fixture spreadsheets; creates season fixtures |
| `download.py` | Exports fixtures to Excel for download |
| `season.py` | Finds adjacent seasons for prev/next navigation |

---

## 8. Key Things to Know

**The `pagename` pattern** — instead of dozens of separate URLs, most views have one URL
with a `pagename` variable. Inside `get_context_data`, an `if/elif` chain branches on it.
Think of it like a tab switcher baked into the URL.

**`LeagueSettings.get()`** — there is always exactly one row in the LeagueSettings table (pk=1).
Call `.get()` to retrieve it. It holds `league_status` and controls what the whole site shows.

**`TeamNomination`** — an active nomination has `date_to=None` and `approved=True`.
A pending change request has `approved=False`. A retired nomination has a `date_to` date set.

**Adding a new page** — the typical pattern is:
1. Add `path(...)` to `league/urls.py`
2. Create a `class MyView(GenericViewMixin, TemplateView)` in `views.py`
3. Create `league/templates/league/mypage.html`
