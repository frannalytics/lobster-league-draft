import streamlit as st
import pandas as pd
from pathlib import Path

from draft_logic import get_current_pick_info

# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(page_title="Lobster League Draft", layout="wide")

st.title("🏈 Lobster League Draft")


# -----------------------------
# File paths
# -----------------------------
BASE_DIR = Path(__file__).parent
FILES_DIR = BASE_DIR / "files"

ROSTERS_FILE = FILES_DIR / "Lobster_League_Rosters_2026.csv"
AVAILABLE_FILE = FILES_DIR / "Lobster_League_Available_Players_2026.csv"
DRAFT_LOG_FILE = FILES_DIR / "draft_log.csv"


# -----------------------------
# Load data
# -----------------------------
rosters = pd.read_csv(ROSTERS_FILE)
available = pd.read_csv(AVAILABLE_FILE)

if DRAFT_LOG_FILE.exists():
    draft_log = pd.read_csv(DRAFT_LOG_FILE)
else:
    draft_log = pd.DataFrame(
        columns=[
            "Pick",
            "Round",
            "Round Pick",
            "Team",
            "Player",
            "Position",
            "NFL Team",
            "Yahoo Player ID",
        ]
    )


# -----------------------------
# Current pick
# -----------------------------
current_pick = get_current_pick_info(draft_log)

st.subheader(f"⏰ On the Clock: {current_pick['Team']}")

st.caption(
    f"Round {current_pick['Round']} • "
    f"Pick {current_pick['Round Pick']} • "
    f"Overall Pick {current_pick['Pick']}"
)


# -----------------------------
# Layout
# -----------------------------
left, center, right = st.columns([1.2, 2.2, 1.4])


# -----------------------------
# Left: Rosters
# -----------------------------
with left:
    st.subheader("Current Rosters")

    teams = sorted(rosters["Fantasy Team"].dropna().unique())

    selected_team = st.selectbox("View team", teams)

    team_roster = rosters[rosters["Fantasy Team"] == selected_team]

    st.dataframe(
        team_roster[["Player", "Position", "NFL Team"]],
        hide_index=True,
        use_container_width=True,
    )


# -----------------------------
# Center: Available players
# -----------------------------
with center:
    st.subheader("Available Players")

    search = st.text_input("Search player", placeholder="Type a player name...")

    positions = sorted(available["Position"].dropna().astype(str).unique())

    position_filter = st.multiselect("Position", positions)

    filtered = available.copy()

    if search:
        filtered = filtered[
            filtered["Player"].astype(str).str.contains(search, case=False, na=False)
        ]

    if position_filter:
        filtered = filtered[filtered["Position"].isin(position_filter)]

    st.dataframe(
        filtered[
            [
                "Player",
                "Position",
                "NFL Team",
                "Pre-Season Rank",
                "Actual Rank",
                "Rostered %",
            ]
        ],
        hide_index=True,
        use_container_width=True,
        height=600,
    )


# -----------------------------
# Right: Draft results
# -----------------------------
with right:
    st.subheader("Draft Results")

    if draft_log.empty:
        st.info("No picks yet.")
    else:
        st.dataframe(
            draft_log[["Pick", "Team", "Player", "Position"]].iloc[::-1],
            hide_index=True,
            use_container_width=True,
        )
