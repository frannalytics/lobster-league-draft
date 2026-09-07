import streamlit as st
import pandas as pd
from pathlib import Path
import requests

from draft_logic import get_current_pick_info, draft_order

# =========================================================
# HELPERS
# =========================================================


def normalize_yahoo_id(value):
    if pd.isna(value):
        return ""

    value = str(value).strip()

    if value.lower() in {"", "nan", "none"}:
        return ""

    try:
        numeric = float(value)

        if numeric.is_integer():
            return str(int(numeric))

    except ValueError:
        pass

    return value


def load_draft_log(api_url):
    draft_columns = [
        "Pick",
        "Round",
        "Round Pick",
        "Team",
        "Player",
        "Position",
        "NFL Team",
        "Yahoo Player ID",
        "Dropped Player",
        "Dropped Yahoo Player ID",
        "Timestamp",
    ]

    try:
        response = requests.get(
            api_url,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if not data:
            return pd.DataFrame(columns=draft_columns)

        df = pd.DataFrame(data)

        for col in draft_columns:
            if col not in df.columns:
                df[col] = None

        df = df[draft_columns]

        df["Yahoo Player ID"] = df["Yahoo Player ID"].apply(normalize_yahoo_id)

        df["Dropped Yahoo Player ID"] = df["Dropped Yahoo Player ID"].apply(
            normalize_yahoo_id
        )

        return df

    except Exception as e:
        st.error(f"Could not load live draft data: {e}")

        return pd.DataFrame(columns=draft_columns)


# =========================================================
# PAGE SETUP
# =========================================================

st.set_page_config(
    page_title="Lobster League Draft",
    layout="wide",
)

st.title("🏈 Lobster League Draft")


# =========================================================
# TEAM OWNERS
# =========================================================

TEAM_OWNERS = {
    "Hawk-Tua Tuesdays": "Adam",
    "Thorpeedos": "Kevin",
    "Jimbo’s Smokin’ Hot": "Jimmy",
    "Frankie_pix": "Frank",
    "NJGiants30": "Doug",
    "My Ball Zach Ertz": "Phil",
    "Lame Clowns": "Meaghan",
    "TJ Hockentuahs": "Jake",
    "Taylormade Mafia": "AJ",
    "God619": "Cheng",
}


# =========================================================
# FILES / API
# =========================================================

BASE_DIR = Path(__file__).parent
FILES_DIR = BASE_DIR / "files"

ROSTERS_FILE = FILES_DIR / "Lobster_League_Rosters_2026.csv"

AVAILABLE_FILE = FILES_DIR / "Lobster_League_Available_Players_2026.csv"

DRAFT_API_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbxJlUdCAAf69oYNwHZ2IomJKmQPikOvx0xL6IX_gujB8khV38gvDYtLfSDw5agsksIE/exec"
)


# =========================================================
# LOAD BASE DATA
# =========================================================

base_rosters = pd.read_csv(ROSTERS_FILE)

base_available = pd.read_csv(AVAILABLE_FILE)

base_rosters["Yahoo Player ID"] = base_rosters["Yahoo Player ID"].apply(
    normalize_yahoo_id
)

base_available["Yahoo Player ID"] = base_available["Yahoo Player ID"].apply(
    normalize_yahoo_id
)


# -----------------------------
# Stable fallback IDs
# -----------------------------

missing_ids = base_rosters["Yahoo Player ID"] == ""

base_rosters.loc[missing_ids, "Yahoo Player ID"] = (
    "NOID-"
    + base_rosters.loc[missing_ids, "Player"].astype(str)
    + "-"
    + base_rosters.loc[missing_ids, "NFL Team"].astype(str)
)


# =========================================================
# REFRESH BUTTON
# =========================================================

if st.button(
    "🔄 Refresh Draft",
    use_container_width=False,
):
    st.rerun()


# =========================================================
# LOAD LIVE DRAFT LOG
# =========================================================

draft_log = load_draft_log(DRAFT_API_URL)


# =========================================================
# BUILD LIVE ROSTERS
# =========================================================

rosters = base_rosters.copy()

if not draft_log.empty:

    dropped_ids = draft_log["Dropped Yahoo Player ID"].dropna().astype(str).tolist()

    rosters = rosters[~rosters["Yahoo Player ID"].astype(str).isin(dropped_ids)].copy()

    drafted_players = draft_log[
        [
            "Team",
            "Player",
            "Position",
            "NFL Team",
            "Yahoo Player ID",
        ]
    ].copy()

    drafted_players = drafted_players.rename(columns={"Team": "Fantasy Team"})

    rosters = pd.concat(
        [
            rosters,
            drafted_players,
        ],
        ignore_index=True,
    )


# =========================================================
# BUILD LIVE AVAILABLE POOL
# =========================================================

available = base_available.copy()

if not draft_log.empty:

    drafted_ids = draft_log["Yahoo Player ID"].dropna().astype(str).tolist()

    available = available[
        ~available["Yahoo Player ID"].astype(str).isin(drafted_ids)
    ].copy()

    dropped_ids = draft_log["Dropped Yahoo Player ID"].dropna().astype(str).tolist()

    for drop_id in dropped_ids:

        original_player = base_rosters[
            base_rosters["Yahoo Player ID"].astype(str) == str(drop_id)
        ]

        if original_player.empty:
            original_player = base_available[
                base_available["Yahoo Player ID"].astype(str) == str(drop_id)
            ]

        if not original_player.empty:

            player = original_player.iloc[0]

            already_available = (
                available["Yahoo Player ID"].astype(str) == str(drop_id)
            ).any()

            if not already_available:

                new_row = {
                    "Player": player["Player"],
                    "Position": player["Position"],
                    "NFL Team": player["NFL Team"],
                    "Yahoo Player ID": player["Yahoo Player ID"],
                    "Pre-Season Rank": (
                        player["Pre-Season Rank"]
                        if "Pre-Season Rank" in player.index
                        else None
                    ),
                    "Actual Rank": (
                        player["Actual Rank"] if "Actual Rank" in player.index else None
                    ),
                    "Rostered %": (
                        player["Rostered %"] if "Rostered %" in player.index else None
                    ),
                }

                available = pd.concat(
                    [
                        available,
                        pd.DataFrame([new_row]),
                    ],
                    ignore_index=True,
                )


# =========================================================
# CURRENT PICK / NEXT UP
# =========================================================

current_pick = get_current_pick_info(draft_log)

current_index = draft_order.index(current_pick["Team"])

on_deck_team = draft_order[(current_index + 1) % len(draft_order)]

in_the_hole_team = draft_order[(current_index + 2) % len(draft_order)]

current_owner = TEAM_OWNERS.get(current_pick["Team"], "")

on_deck_owner = TEAM_OWNERS.get(on_deck_team, "")

in_the_hole_owner = TEAM_OWNERS.get(in_the_hole_team, "")


# =========================================================
# ON THE CLOCK BANNER
# =========================================================

st.markdown(
    f"""
<div style="
    padding:22px;
    border-radius:14px;
    border:2px solid #888;
    text-align:center;
    margin-bottom:12px;
">
<h2 style="margin:0;">
🟢 PICK {current_pick['Pick']} — {current_pick['Team']} IS ON THE CLOCK
</h2>

<p style="margin:8px 0 0 0;font-size:17px;">
Owner: {current_owner}
&nbsp;&nbsp;•&nbsp;&nbsp;
Round {current_pick['Round']}
&nbsp;&nbsp;•&nbsp;&nbsp;
Pick {current_pick['Round Pick']}
</p>
</div>
""",
    unsafe_allow_html=True,
)


# =========================================================
# ON DECK / IN THE HOLE
# =========================================================

next1, next2 = st.columns(2)

with next1:
    st.info(f"🟡 **ON DECK:** " f"{on_deck_team} ({on_deck_owner})")

with next2:
    st.info(f"⚪ **IN THE HOLE:** " f"{in_the_hole_team} ({in_the_hole_owner})")


# =========================================================
# LAST PICK
# =========================================================

if not draft_log.empty:

    last_pick = draft_log.iloc[-1]

    st.success(
        f"✅ **LAST PICK:** "
        f"{last_pick['Team']} selected "
        f"**{last_pick['Player']}** "
        f"and dropped "
        f"**{last_pick['Dropped Player']}**"
    )


# =========================================================
# DRAFT CONTROL
# =========================================================

st.subheader("🦞 Draft Control")


# -----------------------------
# Player to draft
# -----------------------------

player_options = available.copy()

player_options["label"] = (
    player_options["Player"].astype(str)
    + " — "
    + player_options["Position"].astype(str)
    + " — "
    + player_options["NFL Team"].astype(str)
)

selected_label = st.selectbox(
    f"{current_pick['Team']} is on the clock — select a player",
    player_options["label"].tolist(),
    index=None,
    placeholder="Search/select a player...",
)


# -----------------------------
# Player to drop
# -----------------------------

current_team_roster = rosters[rosters["Fantasy Team"] == current_pick["Team"]].copy()

current_team_roster["label"] = (
    current_team_roster["Player"].astype(str)
    + " — "
    + current_team_roster["Position"].astype(str)
    + " — "
    + current_team_roster["NFL Team"].astype(str)
)

dropped_label = st.selectbox(
    f"Select player for {current_pick['Team']} to drop",
    current_team_roster["label"].tolist(),
    index=None,
    placeholder="Select player to drop...",
)


# -----------------------------
# Submit pick
# -----------------------------

if selected_label and dropped_label:

    selected_player = player_options[player_options["label"] == selected_label].iloc[0]

    dropped_player = current_team_roster[
        current_team_roster["label"] == dropped_label
    ].iloc[0]

    confirm_left, confirm_right = st.columns(2)

    with confirm_left:
        st.info(
            f"**Draft:** "
            f"{selected_player['Player']} "
            f"({selected_player['Position']} - "
            f"{selected_player['NFL Team']})"
        )

    with confirm_right:
        st.warning(
            f"**Drop:** "
            f"{dropped_player['Player']} "
            f"({dropped_player['Position']} - "
            f"{dropped_player['NFL Team']})"
        )

    if st.button(
        f"MAKE PICK — {current_pick['Team']}",
        type="primary",
        use_container_width=True,
    ):

        payload = {
            "player": selected_player["Player"],
            "position": selected_player["Position"],
            "nfl_team": selected_player["NFL Team"],
            "yahoo_player_id": normalize_yahoo_id(selected_player["Yahoo Player ID"]),
            "dropped_player": dropped_player["Player"],
            "dropped_yahoo_player_id": normalize_yahoo_id(
                dropped_player["Yahoo Player ID"]
            ),
        }

        try:
            response = requests.post(
                DRAFT_API_URL,
                json=payload,
                timeout=10,
            )

            response.raise_for_status()

            result = response.json()

            if result.get("success"):

                st.success(
                    f"Pick {result['pick']}: "
                    f"{result['team']} selects "
                    f"{result['player']} and drops "
                    f"{result['dropped_player']}"
                )

                st.rerun()

            else:
                st.error(
                    result.get(
                        "error",
                        "Something went wrong.",
                    )
                )

        except Exception as e:
            st.error(f"Could not submit pick: {e}")


st.divider()


# =========================================================
# TEAM TABS
# =========================================================

team_names = draft_order.copy()

tabs = st.tabs(["🏈 Draft Board"] + team_names)


# =========================================================
# DRAFT BOARD TAB
# =========================================================

with tabs[0]:

    st.subheader("2026 Draft Order")

    draft_order_rows = []

    for number, team in enumerate(draft_order, start=1):

        if team == current_pick["Team"]:
            status = "🟢 ON THE CLOCK"

        elif team == on_deck_team:
            status = "🟡 ON DECK"

        elif team == in_the_hole_team:
            status = "⚪ IN THE HOLE"

        else:
            status = ""

        draft_order_rows.append(
            {
                "Pick": number,
                "Owner": TEAM_OWNERS.get(team, ""),
                "Team": team,
                "Status": status,
            }
        )

    draft_order_df = pd.DataFrame(draft_order_rows)

    st.dataframe(
        draft_order_df,
        hide_index=True,
        use_container_width=True,
    )

    st.divider()

    left, right = st.columns([2.2, 1.4])

    # -----------------------------
    # Available players
    # -----------------------------
    with left:

        st.subheader("Available Players")

        search = st.text_input(
            "Search player",
            placeholder="Type a player name...",
            key="available_search",
        )

        positions = sorted(available["Position"].dropna().astype(str).unique())

        position_filter = st.multiselect(
            "Position",
            positions,
            key="available_position",
        )

        filtered = available.copy()

        if search:
            filtered = filtered[
                filtered["Player"]
                .astype(str)
                .str.contains(
                    search,
                    case=False,
                    na=False,
                )
            ]

        if position_filter:
            filtered = filtered[filtered["Position"].isin(position_filter)]

        display_columns = [
            "Player",
            "Position",
            "NFL Team",
            "Pre-Season Rank",
            "Actual Rank",
            "Rostered %",
        ]

        display_columns = [col for col in display_columns if col in filtered.columns]

        st.caption(f"{len(filtered)} available players")

        st.dataframe(
            filtered[display_columns],
            hide_index=True,
            use_container_width=True,
            height=600,
        )

    # -----------------------------
    # Draft results
    # -----------------------------
    with right:

        st.subheader("Draft Results")

        if draft_log.empty:

            st.info("No picks yet.")

        else:

            results = draft_log[
                [
                    "Pick",
                    "Team",
                    "Player",
                    "Dropped Player",
                ]
            ].copy()

            results = results.iloc[::-1]

            st.dataframe(
                results,
                hide_index=True,
                use_container_width=True,
                height=600,
            )


# =========================================================
# INDIVIDUAL TEAM TABS
# =========================================================

for i, team in enumerate(
    team_names,
    start=1,
):

    with tabs[i]:

        team_roster = rosters[rosters["Fantasy Team"] == team].copy()

        st.header(team)

        owner = TEAM_OWNERS.get(team, "")

        st.caption(f"Owner: {owner}")

        # -----------------------------
        # Roster counts
        # -----------------------------
        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            st.metric(
                "Roster Size",
                len(team_roster),
            )

        with c2:
            st.metric(
                "QB",
                team_roster["Position"].astype(str).str.contains("QB").sum(),
            )

        with c3:
            st.metric(
                "RB",
                team_roster["Position"].astype(str).str.contains("RB").sum(),
            )

        with c4:
            st.metric(
                "WR",
                team_roster["Position"].astype(str).str.contains("WR").sum(),
            )

        with c5:
            st.metric(
                "TE",
                team_roster["Position"].astype(str).str.contains("TE").sum(),
            )

        # -----------------------------
        # Current roster
        # -----------------------------
        st.subheader("Current Roster")

        position_order = {
            "QB": 1,
            "RB": 2,
            "WR": 3,
            "TE": 4,
            "K": 5,
            "DEF": 6,
        }

        team_roster["Position Sort"] = (
            team_roster["Position"].map(position_order).fillna(99)
        )

        team_roster = team_roster.sort_values(
            [
                "Position Sort",
                "Player",
            ]
        )

        st.dataframe(
            team_roster[
                [
                    "Player",
                    "Position",
                    "NFL Team",
                ]
            ],
            hide_index=True,
            use_container_width=True,
            height=650,
        )

        # -----------------------------
        # Draft activity
        # -----------------------------
        st.subheader("Draft Activity")

        if draft_log.empty:

            st.caption("No draft moves yet.")

        else:

            team_moves = draft_log[draft_log["Team"] == team].copy()

            if team_moves.empty:

                st.caption("No draft moves yet.")

            else:

                team_moves = team_moves[
                    [
                        "Pick",
                        "Round",
                        "Player",
                        "Dropped Player",
                    ]
                ]

                st.dataframe(
                    team_moves,
                    hide_index=True,
                    use_container_width=True,
                )
