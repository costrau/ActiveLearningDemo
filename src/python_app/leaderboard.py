import streamlit as st
import pandas as pd
import os

# file stuff
LEADERBOARD_FILE = "leaderboard.csv"
if not os.path.exists(LEADERBOARD_FILE):
    df = pd.DataFrame(columns=["Name", "Score"])
    df.to_csv(LEADERBOARD_FILE, index=False)


# utility functions
def load_leaderboard():
    df = pd.read_csv(LEADERBOARD_FILE)
    if df.empty:
        return df
    return df.sort_values("Score", ascending=True).reset_index(drop=True)


def save_entry(name, score):
    df = load_leaderboard()
    # Falls Name schon existiert → alten Eintrag entfernen
    df = df[df["Name"] != name]
    # neuen Eintrag hinzufügen
    df = pd.concat([df, pd.DataFrame([{"Name": name, "Score": score}])], ignore_index=True)
    df = df.sort_values("Score", ascending=True).reset_index(drop=True)
    df.to_csv(LEADERBOARD_FILE, index=False)
    return df


def render_leaderboard(df, player_name=None, top_n=10):
    # highlight current user
    def mark_player(row):
        if row["Name"] == player_name:
            return f"👉 {row['Name']}"
        return row["Name"]

    # highlight player name if it exists
    if player_name is not None:
        df["Name"] = df.apply(mark_player, axis=1)

    # render table
    st.table(df)



# session state stuff
if "name_entered" not in st.session_state:
    st.session_state.name_entered = False

# Streamlit UI
base = st.container()
with base:
    st.header("🏆 Leaderboard (Top 10)")

    # the leaderboard is just shown and no user did compete
    if "user_rmse" not in st.session_state:
        # get top 10 entries
        df = load_leaderboard()
        top10 = df.head(10).reset_index(drop=True)
        # increase index by one
        top10.index += 1
        # limit to two decimal digits
        top10["Score"] = top10["Score"].apply(lambda x: f"{x:.2f}")
        # render top 10
        render_leaderboard(top10)
    else:
        user_rmse = float(st.session_state["user_rmse"])
        # create a form to enter the users name
        if not st.session_state.name_entered:
            st.markdown(f"#### Modell-Fehler: **{user_rmse:.2f}**")
            st.markdown(f"##### Bitte gib deinen Namen ein:")
            name = st.text_input("Dein Name eingeben:", label_visibility="collapsed")

            if st.button("In Leaderboard eintragen"):
                # save the name
                st.session_state.name = name
                # save that the name was entered to remove the buttons and the text
                st.session_state.name_entered = True

                if name.strip():
                    df = save_entry(name, user_rmse)
                st.rerun()
        else:
            # get the player name and score from the session state
            name = st.session_state.name
            user_rmse = float(st.session_state["user_rmse"])

            # determine rank of player
            df = load_leaderboard()
            df_reset = df.reset_index()
            player_row = df_reset[df_reset["Name"] == name].iloc[0]
            player_rank = int(player_row["index"] + 1)

            # get top 10
            top10 = df.head(10).reset_index(drop=True)
            # create df with rank column
            top10 = top10.copy()
            top10.index += 1

            # if the player is worse than rank 10 show it below the top 1ß
            if player_rank > 10:
                top10.loc[11] = [name, user_rmse]
                top10.index = list(range(1, 11)) + [player_rank]
            # limit to two decimal digits
            top10["Score"] = top10["Score"].apply(lambda x: f"{x:.2f}")

            # render dataframe
            render_leaderboard(top10, player_name=name)
