import pandas as pd

draft_order = [
    "Frankie_pix",
    "Jimbo’s Smokin’ Hot",
    "Thorpeedos",
    "Hawk-Tua Tuesdays",
    "My Ball Zach Ertz",
    "NJGiants30",
    "Lame Clowns",
    "TJ Hockentuahs",
    "Taylormade Mafia",
    "God619",
]


def get_current_pick_info(draft_log):
    pick_no = len(draft_log) + 1

    team_index = (pick_no - 1) % len(draft_order)
    round_no = ((pick_no - 1) // len(draft_order)) + 1
    round_pick = team_index + 1

    return {
        "Pick": pick_no,
        "Round": round_no,
        "Round Pick": round_pick,
        "Team": draft_order[team_index],
    }
