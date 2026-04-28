import streamlit as st


def icon_references():
    st.title("Bildnachweise")
    st.markdown(
        """<a href="https://www.flaticon.com/de/kostenlose-icons/lkw" title="lkw Icons">LKW Icon erstellt von mavadee - Flaticon</a>""",
        unsafe_allow_html=True)
    st.markdown(
        """<a href="https://www.flaticon.com/de/kostenlose-icons/sportwagen" title="sportwagen Icons">Sportwagen Icon erstellt von Hilmaaaan - Flaticon</a>""",
        unsafe_allow_html=True)
    st.markdown(
        """<a href="https://www.flaticon.com/de/kostenlose-icons/auto" title="autos Icons">Auto Icon erstellt von sonnycandra - Flaticon</a>""",
        unsafe_allow_html=True)
    st.markdown(
        """<a href="https://www.flaticon.com/de/kostenlose-icons/kleinbus" title="kleinbus Icons">Kleinbus Icon erstellt von Vitaly Gorbachev - Flaticon</a>""",
        unsafe_allow_html=True)
    st.markdown(
        """<a href="https://www.flaticon.com/de/kostenlose-icons/pickup" title="auto Icons">Pickup Icon erstellt von Mehwish - Flaticon</a>""",
        unsafe_allow_html=True)


pg = st.navigation(
    pages=[
        st.Page("demonstrator.py", title="Demonstrator"),
        st.Page("leaderboard.py", title="Leaderboard"),
        st.Page(icon_references, title="Bildnachweise"),
    ],
    position="sidebar",
    expanded=False,
)
pg.run()
