# apps/fincrm_dashboard.py
import streamlit as st


def main() -> None:
    st.set_page_config(page_title="FinCRM Dashboard", layout="wide")

    st.title("FinCRM Dashboard")
    st.write("Your finances + CRM app is alive.")

    st.sidebar.header("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Overview", "Transactions", "Contacts", "Deals", "Tasks"],
    )

    if page == "Overview":
        st.header("Overview")
        st.info("Next step: wire real data.")
    elif page == "Transactions":
        st.header("Transactions")
    elif page == "Contacts":
        st.header("Contacts")
    elif page == "Deals":
        st.header("Deals")
    elif page == "Tasks":
        st.header("Tasks")


if __name__ == "__main__":
    main()