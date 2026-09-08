import streamlit as st
import pandas as pd
from pathlib import Path
import requests

from draft_logic import get_current_pick_info, draft_order


# =========================================================
# HELPERS
# =========================================================


def send_discord_message(message):
    try:
        webhook_url = st.secrets["DISCORD_WEBHOOK_URL"]

        response = requests.post(
            webhook_url,
            json={"content": message},
            timeout=10,
        )

        response.raise_for_status()

    except Exception as e:
        st.warning(f"Draft updated, but Discord notification failed: {e}")


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
        "Action",
    ]

    try:
        response = requests.get(
            api_url,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if not data:
            return pd.DataFrame(
                columns=draft_columns
            )

        df = pd.DataFrame(data)

        for col in draft_columns:
            if col not in df.columns:
                df[col] = None

        df = df[draft_columns]

        df["Yahoo Player ID"] = (
            df["Yahoo Player ID"]
            .apply(normalize_yahoo_id)
        )

        df["Dropped Yahoo Player ID"] = (
            df["Dropped Yahoo Player ID"]
            .apply(normalize_yahoo_id)
        )

        # Support any older rows created before Action existed
        missing_action = (
            df["Action"].isna()
            |
            (df["Action"].astype(str).str.strip() == "")
        )

        df.loc[
            missing_action
            & df["Player"].notna()
            & (df["Player"].astype(str).str.strip() != ""),
            "Action"
        ] = "PICK"

        df.loc[
            missing_action
            & (
                df["Player"].isna()
                |
                (df["Player"].astype(str).str.strip() == "")
            ),
            "Action"
        ] = "SKIP"

        df["Action"] = (
            df["Action"]
            .astype(str)
            .str.upper()
            .str.strip()
        )

        return df

    except Exception as e:
        st.error(
            f"Could not load live draft data: {e}"
        )

        return pd.DataFrame(
            columns=draft_columns
        )


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

ROSTERS_FILE = (
    FILES_DIR
    / "Lobster_League_Rosters_2026.csv"
)

AVAILABLE_FILE = (
    FILES_DIR
    / "Lobster_League_Available_Players_2026.csv"
)

DRAFT_API_URL = "https://script.google.com/macros/s/AKfycbzniJ3hPhpTENVx7o1-F6AYjYWibon3_zZQxnaJDEr9EpzwBrF-z3Hi1xLJ4uxH1zfQ/exec"


# =========================================================
# LOAD BASE DATA
# =========================================================

base_rosters = pd.read_csv(
    ROSTERS_FILE
)

base_available = pd.read_csv(
    AVAILABLE_FILE
)

base_rosters["Yahoo Player ID"] = (
    base_rosters["Yahoo Player ID"]
    .apply(normalize_yahoo_id)
)

base_available["Yahoo Player ID"] = (
    base_available["Yahoo Player ID"]
    .apply(normalize_yahoo_id)
)


# -----------------------------
# Stable fallback IDs
# -----------------------------

missing_ids = (
    base_rosters["Yahoo Player ID"] == ""
)

base_rosters.loc[
    missing_ids,
    "Yahoo Player ID"
] = (
    "NOID-"
    + base_rosters.loc[
        missing_ids,
        "Player"
    ].astype(str)
    + "-"
    + base_rosters.loc[
        missing_ids,
        "NFL Team"
    ].astype(str)
)


# =========================================================
# REFRESH BUTTON
# =========================================================

if st.button(
    "🔄 Refresh Draft"
):
    st.session_state["available_search"] = ""
    st.session_state["available_position"] = []
    st.rerun()


# =========================================================
# LOAD LIVE LOG
# =========================================================

draft_log = load_draft_log(
    DRAFT_API_URL
)


# =========================================================
# PICK-ONLY LOG
# =========================================================
# SKIPs advance the clock but must NOT affect rosters.

if not draft_log.empty:
    pick_log = draft_log[
        draft_log["Action"] == "PICK"
    ].copy()

else:
    pick_log = draft_log.copy()


# =========================================================
# BUILD LIVE ROSTERS
# =========================================================

rosters = base_rosters.copy()

if not pick_log.empty:

    dropped_ids = (
        pick_log[
            "Dropped Yahoo Player ID"
        ]
        .dropna()
        .astype(str)
        .tolist()
    )

    rosters = rosters[
        ~rosters[
            "Yahoo Player ID"
        ]
        .astype(str)
        .isin(dropped_ids)
    ].copy()


    drafted_players = pick_log[
        [
            "Team",
            "Player",
            "Position",
            "NFL Team",
            "Yahoo Player ID",
        ]
    ].copy()

    drafted_players = (
        drafted_players.rename(
            columns={
                "Team": "Fantasy Team"
            }
        )
    )

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

if not pick_log.empty:

    drafted_ids = (
        pick_log[
            "Yahoo Player ID"
        ]
        .dropna()
        .astype(str)
        .tolist()
    )

    available = available[
        ~available[
            "Yahoo Player ID"
        ]
        .astype(str)
        .isin(drafted_ids)
    ].copy()


    dropped_ids = (
        pick_log[
            "Dropped Yahoo Player ID"
        ]
        .dropna()
        .astype(str)
        .tolist()
    )


    for drop_id in dropped_ids:

        original_player = base_rosters[
            base_rosters[
                "Yahoo Player ID"
            ].astype(str)
            == str(drop_id)
        ]


        if original_player.empty:
            original_player = base_available[
                base_available[
                    "Yahoo Player ID"
                ].astype(str)
                == str(drop_id)
            ]


        if not original_player.empty:

            player = original_player.iloc[0]

            already_available = (
                available[
                    "Yahoo Player ID"
                ]
                .astype(str)
                == str(drop_id)
            ).any()


            if not already_available:

                new_row = {
                    "Player":
                        player["Player"],

                    "Position":
                        player["Position"],

                    "NFL Team":
                        player["NFL Team"],

                    "Yahoo Player ID":
                        player["Yahoo Player ID"],

                    "Pre-Season Rank":
                        (
                            player["Pre-Season Rank"]
                            if "Pre-Season Rank"
                            in player.index
                            else None
                        ),

                    "Actual Rank":
                        (
                            player["Actual Rank"]
                            if "Actual Rank"
                            in player.index
                            else None
                        ),

                    "Rostered %":
                        (
                            player["Rostered %"]
                            if "Rostered %"
                            in player.index
                            else None
                        ),
                }

                available = pd.concat(
                    [
                        available,
                        pd.DataFrame(
                            [new_row]
                        ),
                    ],
                    ignore_index=True,
                )


# =========================================================
# CURRENT PICK / NEXT UP
# =========================================================

current_pick = get_current_pick_info(
    draft_log
)

current_index = draft_order.index(
    current_pick["Team"]
)

on_deck_team = draft_order[
    (current_index + 1)
    % len(draft_order)
]

in_the_hole_team = draft_order[
    (current_index + 2)
    % len(draft_order)
]


current_owner = TEAM_OWNERS.get(
    current_pick["Team"],
    ""
)

on_deck_owner = TEAM_OWNERS.get(
    on_deck_team,
    ""
)

in_the_hole_owner = TEAM_OWNERS.get(
    in_the_hole_team,
    ""
)


# =========================================================
# ON THE CLOCK
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
    st.info(
        f"🟡 **ON DECK:** "
        f"{on_deck_team} "
        f"({on_deck_owner})"
    )

with next2:
    st.info(
        f"⚪ **IN THE HOLE:** "
        f"{in_the_hole_team} "
        f"({in_the_hole_owner})"
    )


# =========================================================
# LAST EVENT
# =========================================================

if not draft_log.empty:

    last_event = draft_log.iloc[-1]

    if last_event["Action"] == "SKIP":

        st.warning(
            f"⏭️ **LAST TURN:** "
            f"{last_event['Team']} skipped."
        )

    else:

        st.success(
            f"✅ **LAST PICK:** "
            f"{last_event['Team']} selected "
            f"**{last_event['Player']}** "
            f"and dropped "
            f"**{last_event['Dropped Player']}**"
        )


# =========================================================
# DRAFT CONTROL
# =========================================================

st.subheader(
    "🦞 Draft Control"
)


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

current_team_roster = rosters[
    rosters["Fantasy Team"]
    == current_pick["Team"]
].copy()

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


# =========================================================
# MAKE PICK
# =========================================================

if selected_label and dropped_label:

    selected_player = player_options[
        player_options["label"]
        == selected_label
    ].iloc[0]

    dropped_player = current_team_roster[
        current_team_roster["label"]
        == dropped_label
    ].iloc[0]


    confirm_left, confirm_right = (
        st.columns(2)
    )

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
            "action": "pick",

            "player":
                selected_player["Player"],

            "position":
                selected_player["Position"],

            "nfl_team":
                selected_player["NFL Team"],

            "yahoo_player_id":
                normalize_yahoo_id(
                    selected_player[
                        "Yahoo Player ID"
                    ]
                ),

            "dropped_player":
                dropped_player["Player"],

            "dropped_yahoo_player_id":
                normalize_yahoo_id(
                    dropped_player[
                        "Yahoo Player ID"
                    ]
                ),
        }


        try:
            response = requests.post(
                DRAFT_API_URL,
                json=payload,
                timeout=30,
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
                
                
                next_pick = get_current_pick_info(
                    pd.concat(
                        [
                            draft_log,
                            pd.DataFrame([{"Action": "PICK"}]),
                        ],
                        ignore_index=True,
                    )
                )

                send_discord_message(
                    f"🦞 **Pick {result['pick']}**\n"
                    f"**{result['team']}** selects "
                    f"**{result['player']}** ({result['position']})\n"
                    f"Dropped: **{result['dropped_player']}**\n\n"
                    f"⏰ **On the clock:** {next_pick['Team']}"
)
                st.rerun()

            else:

                st.error(
                    result.get(
                        "error",
                        "Something went wrong."
                    )
                )


        except Exception as e:

            st.error(
                f"Could not submit pick: {e}"
            )


# =========================================================
# SKIP / GO BACK
# =========================================================

st.divider()

skip_col, back_col = st.columns(2)


with skip_col:

    if st.button(
        f"⏭️ SKIP PICK — {current_pick['Team']}",
        use_container_width=True,
    ):

        try:
            response = requests.post(
                DRAFT_API_URL,
                json={
                    "action": "skip"
                },
                timeout=10,
            )

            response.raise_for_status()

            result = response.json()


            if result.get("success"):

                st.success(
                    f"{result['team']} skipped Pick "
                    f"{result['pick']}."
                )
                
                next_pick = get_current_pick_info(
                    pd.concat(
                        [
                            draft_log,
                            pd.DataFrame([{"Action": "SKIP"}]),
                        ],
                        ignore_index=True,
                    )
                )

                send_discord_message(
                    f"⏭️ **Pick {result['pick']} skipped**\n"
                    f"**{result['team']}** passes for now.\n\n"
                    f"⏰ **On the clock:** {next_pick['Team']}"
                )

                st.rerun()

            else:

                st.error(
                    result.get(
                        "error",
                        "Could not skip pick."
                    )
                )


        except Exception as e:

            st.error(
                f"Could not skip pick: {e}"
            )


with back_col:

    if draft_log.empty:

        st.button(
            "↩️ GO BACK ONE PICK",
            disabled=True,
            use_container_width=True,
        )

    else:

        if st.button(
            "↩️ GO BACK ONE PICK",
            use_container_width=True,
        ):

            try:
                response = requests.post(
                    DRAFT_API_URL,
                    json={
                        "action": "back"
                    },
                    timeout=10,
                )

                response.raise_for_status()

                result = response.json()

                if result.get("success"):

                    st.success(
                        f"Returned to Pick "
                        f"{result['pick']}."
                    )

                    send_discord_message(
                        f"↩️ **Draft correction**\n"
                        f"Pick {result['pick']} was removed.\n\n"
                        f"⏰ **Back on the clock:** {result['team']}"
                    )

                    st.rerun()

                else:

                    st.error(
                        result.get(
                            "error",
                            "Could not go back."
                        )
                    )

            except Exception as e:

                st.error(
                    f"Could not go back: {e}"
                )


st.divider()


# =========================================================
# TEAM TABS
# =========================================================

team_names = draft_order.copy()

tabs = st.tabs(
    ["🏈 Draft Board"]
    + team_names
)


# =========================================================
# DRAFT BOARD
# =========================================================

with tabs[0]:

    st.subheader(
        "2026 Draft Order"
    )

    draft_order_rows = []


    for number, team in enumerate(
        draft_order,
        start=1,
    ):

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
                "Owner":
                    TEAM_OWNERS.get(
                        team,
                        ""
                    ),
                "Team": team,
                "Status": status,
            }
        )


    draft_order_df = pd.DataFrame(
        draft_order_rows
    )


    st.dataframe(
        draft_order_df,
        hide_index=True,
        use_container_width=True,
    )


    st.divider()


    left, right = st.columns(
        [2.2, 1.4]
    )


    # =====================================================
    # AVAILABLE PLAYERS
    # =====================================================

    with left:

        st.subheader(
            "Available Players"
        )


        search = st.text_input(
            "Search player",
            placeholder="Type a player name...",
            key="available_search",
        )


        positions = sorted(
            available[
                "Position"
            ]
            .dropna()
            .astype(str)
            .unique()
        )


        position_filter = st.multiselect(
            "Position",
            positions,
            key="available_position",
        )


        filtered = available.copy()


        if search:

            filtered = filtered[
                filtered[
                    "Player"
                ]
                .astype(str)
                .str.contains(
                    search,
                    case=False,
                    na=False,
                )
            ]


        if position_filter:

            filtered = filtered[
                filtered[
                    "Position"
                ]
                .isin(
                    position_filter
                )
            ]


        display_columns = [
            "Player",
            "Position",
            "NFL Team",
            "Pre-Season Rank",
            "Actual Rank",
            "Rostered %",
        ]


        display_columns = [
            col
            for col
            in display_columns
            if col
            in filtered.columns
        ]


        st.caption(
            f"{len(filtered)} available players"
        )


        st.dataframe(
            filtered[
                display_columns
            ],
            hide_index=True,
            use_container_width=True,
            height=600,
        )


    # =====================================================
    # DRAFT RESULTS
    # =====================================================

    with right:

        st.subheader(
            "Draft Results"
        )


        if draft_log.empty:

            st.info(
                "No picks yet."
            )

        else:

            results = draft_log[
                [
                    "Pick",
                    "Team",
                    "Player",
                    "Dropped Player",
                    "Action",
                ]
            ].copy()


            results.loc[
                results["Action"] == "SKIP",
                "Player"
            ] = "SKIPPED"


            results.loc[
                results["Action"] == "SKIP",
                "Dropped Player"
            ] = ""


            results = (
                results.iloc[::-1]
            )


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

        team_roster = rosters[
            rosters[
                "Fantasy Team"
            ]
            == team
        ].copy()

        st.header(team)

        st.caption(
            f"Owner: "
            f"{TEAM_OWNERS.get(team, '')}"
        )

        # =================================================
        # COUNTS
        # =================================================

        c1, c2, c3, c4, c5 = (
            st.columns(5)
        )

        with c1:
            st.metric(
                "Roster Size",
                len(team_roster),
            )

        with c2:
            st.metric(
                "QB",
                team_roster[
                    "Position"
                ]
                .astype(str)
                .str.contains("QB")
                .sum(),
            )

        with c3:
            st.metric(
                "RB",
                team_roster[
                    "Position"
                ]
                .astype(str)
                .str.contains("RB")
                .sum(),
            )

        with c4:
            st.metric(
                "WR",
                team_roster[
                    "Position"
                ]
                .astype(str)
                .str.contains("WR")
                .sum(),
            )

        with c5:
            st.metric(
                "TE",
                team_roster[
                    "Position"
                ]
                .astype(str)
                .str.contains("TE")
                .sum(),
            )

        # =================================================
        # CURRENT ROSTER
        # =================================================

        st.subheader(
            "Current Roster"
        )

        position_order = {
            "QB": 1,
            "RB": 2,
            "WR": 3,
            "TE": 4,
            "K": 5,
            "DEF": 6,
        }

        team_roster[
            "Position Sort"
        ] = (
            team_roster[
                "Position"
            ]
            .map(
                position_order
            )
            .fillna(99)
        )

        team_roster = (
            team_roster.sort_values(
                [
                    "Position Sort",
                    "Player",
                ]
            )
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

        # =================================================
        # DRAFT ACTIVITY
        # =================================================

        st.subheader(
            "Draft Activity"
        )

        if draft_log.empty:

            st.caption(
                "No draft activity yet."
            )

        else:

            team_moves = draft_log[
                draft_log[
                    "Team"
                ]
                == team
            ].copy()

            if team_moves.empty:

                st.caption(
                    "No draft activity yet."
                )

            else:

                team_moves = team_moves[
                    [
                        "Pick",
                        "Round",
                        "Player",
                        "Dropped Player",
                        "Action",
                    ]
                ]

                team_moves.loc[
                    team_moves["Action"]
                    == "SKIP",
                    "Player"
                ] = "SKIPPED"

                team_moves.loc[
                    team_moves["Action"]
                    == "SKIP",
                    "Dropped Player"
                ] = ""

                st.dataframe(
                    team_moves,
                    hide_index=True,
                    use_container_width=True,
                )


st.divider()

st.subheader("📋 Final Rosters")

if st.button(
    "EXPORT CURRENT ROSTERS TO GOOGLE SHEETS",
    use_container_width=True,
):

    export_rosters = rosters[
        [
            "Fantasy Team",
            "Player",
            "Position",
            "NFL Team",
            "Yahoo Player ID",
        ]
    ].copy()

    export_rosters = export_rosters.sort_values(
        [
            "Fantasy Team",
            "Position",
            "Player",
        ]
    )

    payload = {
        "action": "export_rosters",
        "rosters": export_rosters.to_dict(orient="records"),
    }

    try:
        response = requests.post(
            DRAFT_API_URL,
            json=payload,
            timeout=30,
        )

        response.raise_for_status()

        result = response.json()

        if result.get("success"):
            st.success(
                f"Final Rosters updated — " f"{result['rows_written']} players written."
            )

        else:
            st.error(result.get("error", "Could not export rosters."))

    except Exception as e:
        st.error(f"Could not export rosters: {e}")
