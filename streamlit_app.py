import streamlit as st
import pandas as pd
from datetime import datetime
from snowflake.snowpark.functions import col

conn = st.connection("snowflake")
session = conn.session()

st.set_page_config(page_title="Support Ticket Allocator", layout="wide")

st.title("Support Ticket Allocation System")

st.markdown("""
This application intelligently allocates multilingual support tickets
to the best available engineer based on the **AUTO_ALLOCATE_TICKETS** procedure logic:

* Language match
* Engineer is on shift (BST timezone)
* Under max ticket capacity
* Lowest current workload
""")

engineers_df = session.sql("SELECT * FROM SUPPORT_AI.TICKETING.SUPPORT_ENGINEERS").to_pandas()
tickets_df = session.sql("SELECT * FROM SUPPORT_AI.TICKETING.TICKETS LIMIT 100").to_pandas()

tab1, tab2, tab3, tab4 = st.tabs(["Auto-Allocate Test", "Existing Tickets", "Engineer Workload", "Email Translator"])

with tab1:
    st.subheader("Test Dynamic Ticket Assignment")
    st.markdown("Simulate submitting a new ticket and see which engineer gets assigned using the same logic as `AUTO_ALLOCATE_TICKETS`.")

    col1, col2 = st.columns(2)
    with col1:
        test_subject = st.text_input("Ticket Subject", value="Server crashing on AWS deployment")
        test_language = st.selectbox("Language", options=engineers_df["LANGUAGE"].unique().tolist())
    with col2:
        test_priority = st.selectbox("Priority", options=["urgent", "high", "medium", "low"])
        test_queue = st.selectbox("Queue / Skill", options=engineers_df["SKILL"].unique().tolist())

    test_body = st.text_area("Ticket Body", value="Our production server keeps crashing after the latest deployment. Need urgent help.", height=100)

    if st.button("Find Best Engineer", type="primary"):
        bst_now = session.sql(
            "SELECT TIME(CONVERT_TIMEZONE('UTC', 'Europe/London', CURRENT_TIMESTAMP())) AS BST_TIME"
        ).to_pandas()["BST_TIME"][0]

        allocation_query = f"""
        SELECT
            ENGINEER_ID,
            NAME,
            SKILL,
            LANGUAGE,
            TIMEZONE,
            CURRENT_LOAD,
            MAX_TICKETS,
            SHIFT_START,
            SHIFT_END,
            ROUND((CURRENT_LOAD / MAX_TICKETS) * 100, 1) AS UTILIZATION_PCT
        FROM SUPPORT_AI.TICKETING.SUPPORT_ENGINEERS
        WHERE LANGUAGE = '{test_language}'
          AND CURRENT_LOAD < MAX_TICKETS
          AND TIME('{bst_now}') >= TIME(CONVERT_TIMEZONE(TIMEZONE, 'Europe/London',
                TIMESTAMP_NTZ_FROM_PARTS(CURRENT_DATE(), SHIFT_START)))
          AND TIME('{bst_now}') <= TIME(CONVERT_TIMEZONE(TIMEZONE, 'Europe/London',
                TIMESTAMP_NTZ_FROM_PARTS(CURRENT_DATE(), SHIFT_END)))
        ORDER BY CURRENT_LOAD ASC
        """

        result_df = session.sql(allocation_query).to_pandas()

        st.divider()
        st.subheader("Allocation Result")

        if len(result_df) > 0:
            best = result_df.iloc[0]
            st.success(f"Ticket assigned to: **{best['NAME']}**")

            rcol1, rcol2, rcol3, rcol4 = st.columns(4)
            rcol1.metric("Engineer", best["NAME"])
            rcol2.metric("Current Load", f"{best['CURRENT_LOAD']}/{best['MAX_TICKETS']}")
            rcol3.metric("Utilization", f"{best['UTILIZATION_PCT']}%")
            rcol4.metric("Timezone", best["TIMEZONE"])

            st.markdown(f"""
            **Allocation Reasoning (AUTO_ALLOCATE_TICKETS logic):**
            - Language match: `{best['LANGUAGE']}` = `{test_language}`
            - Currently on shift (BST time: `{bst_now}`)
            - Under capacity: `{best['CURRENT_LOAD']}` < `{best['MAX_TICKETS']}`
            - Lowest workload among eligible engineers
            """)

            if len(result_df) > 1:
                st.markdown("**Other eligible engineers (fallback order):**")
                st.dataframe(result_df[["NAME", "SKILL", "CURRENT_LOAD", "MAX_TICKETS", "UTILIZATION_PCT", "TIMEZONE"]], use_container_width=True)
        else:
            st.error("No suitable engineer found! Possible reasons:")
            st.markdown("""
            - No engineer speaks this language
            - All matching engineers are at max capacity
            - No matching engineer is currently on shift (BST)
            """)

            st.markdown("**All engineers for this language (regardless of shift):**")
            fallback_df = engineers_df[engineers_df["LANGUAGE"].str.lower() == test_language.lower()]
            if len(fallback_df) > 0:
                st.dataframe(fallback_df[["NAME", "SKILL", "CURRENT_LOAD", "MAX_TICKETS", "TIMEZONE", "SHIFT_START", "SHIFT_END"]], use_container_width=True)

with tab2:
    st.subheader("Existing Ticket Assignments")

    assigned = tickets_df[tickets_df["ASSIGNED_ENGINEER_ID"].notna()]
    unassigned = tickets_df[tickets_df["ASSIGNED_ENGINEER_ID"].isna()]

    mcol1, mcol2 = st.columns(2)
    mcol1.metric("Assigned Tickets", len(assigned))
    mcol2.metric("Unassigned Tickets", len(unassigned))

    if st.button("Run AUTO_ALLOCATE_TICKETS Procedure"):
        result = session.sql("CALL SUPPORT_AI.TICKETING.AUTO_ALLOCATE_TICKETS()").collect()
        st.success(f"Procedure result: {result[0][0]}")
        st.rerun()

    st.markdown("### Unassigned Tickets")
    if len(unassigned) > 0:
        st.dataframe(unassigned[["SUBJECT", "LANGUAGE", "QUEUE", "PRIORITY"]].head(20), use_container_width=True)
    else:
        st.info("All tickets are assigned!")

    st.markdown("### Recently Assigned")
    if len(assigned) > 0:
        assigned_with_eng = assigned.merge(
            engineers_df[["ENGINEER_ID", "NAME"]],
            left_on="ASSIGNED_ENGINEER_ID",
            right_on="ENGINEER_ID",
            how="left"
        )
        st.dataframe(assigned_with_eng[["SUBJECT", "LANGUAGE", "QUEUE", "PRIORITY", "NAME"]].head(20), use_container_width=True)

with tab3:
    st.subheader("Engineer Workload Dashboard")

    st.bar_chart(
        data=engineers_df[["NAME", "CURRENT_LOAD", "MAX_TICKETS"]].set_index("NAME"),
        use_container_width=True
    )

    engineers_df["UTILIZATION_PCT"] = (engineers_df["CURRENT_LOAD"] / engineers_df["MAX_TICKETS"] * 100).round(1)
    engineers_df["AVAILABLE_CAPACITY"] = engineers_df["MAX_TICKETS"] - engineers_df["CURRENT_LOAD"]
    engineers_df["STATUS"] = engineers_df["UTILIZATION_PCT"].apply(
        lambda x: "Overloaded" if x >= 80 else ("Moderate" if x >= 50 else "Available")
    )

    st.dataframe(
        engineers_df[["NAME", "SKILL", "LANGUAGE", "TIMEZONE", "CURRENT_LOAD", "MAX_TICKETS", "UTILIZATION_PCT", "AVAILABLE_CAPACITY", "STATUS"]],
        use_container_width=True
    )

with tab4:
    st.subheader("Multilingual Email Translator")
    st.markdown("Paste a support email in any language. It will be automatically translated to English and routed to the best available engineer via `AUTO_ALLOCATE_TICKETS` logic.")

    email_input = st.text_area(
        "Paste multilingual email here",
        value="Bonjour, notre serveur de production est en panne depuis ce matin. Nous avons besoin d'aide urgente pour résoudre ce problème critique.",
        height=150
    )

    source_lang = st.selectbox(
        "Source Language (or auto-detect)",
        options=["auto", "fr", "es", "de", "pt", "ja", "ko", "zh", "it", "nl", "ru", "ar", "hi"],
        index=0,
        key="source_lang"
    )

    if st.button("Translate & Allocate", type="primary"):
        if source_lang == "auto":
            translate_query = f"""
            SELECT SNOWFLAKE.CORTEX.TRANSLATE(
                $${email_input}$$,
                '',
                'en'
            ) AS TRANSLATED_TEXT
            """
        else:
            translate_query = f"""
            SELECT SNOWFLAKE.CORTEX.TRANSLATE(
                $${email_input}$$,
                '{source_lang}',
                'en'
            ) AS TRANSLATED_TEXT
            """

        translated_df = session.sql(translate_query).to_pandas()
        translated_text = translated_df["TRANSLATED_TEXT"][0]

        st.divider()
        st.subheader("Translation Result")

        tcol1, tcol2 = st.columns(2)
        with tcol1:
            st.markdown("**Original Email:**")
            st.info(email_input)
        with tcol2:
            st.markdown("**Translated to English:**")
            st.success(translated_text)

        st.divider()
        st.subheader("Auto-Allocation Based on Translated Email")

        bst_now = session.sql(
            "SELECT TIME(CONVERT_TIMEZONE('UTC', 'Europe/London', CURRENT_TIMESTAMP())) AS BST_TIME"
        ).to_pandas()["BST_TIME"][0]

        allocation_query = f"""
        SELECT
            ENGINEER_ID,
            NAME,
            SKILL,
            LANGUAGE,
            TIMEZONE,
            CURRENT_LOAD,
            MAX_TICKETS,
            ROUND((CURRENT_LOAD / MAX_TICKETS) * 100, 1) AS UTILIZATION_PCT
        FROM SUPPORT_AI.TICKETING.SUPPORT_ENGINEERS
        WHERE LANGUAGE = 'en'
          AND CURRENT_LOAD < MAX_TICKETS
          AND TIME('{bst_now}') >= TIME(CONVERT_TIMEZONE(TIMEZONE, 'Europe/London',
                TIMESTAMP_NTZ_FROM_PARTS(CURRENT_DATE(), SHIFT_START)))
          AND TIME('{bst_now}') <= TIME(CONVERT_TIMEZONE(TIMEZONE, 'Europe/London',
                TIMESTAMP_NTZ_FROM_PARTS(CURRENT_DATE(), SHIFT_END)))
        ORDER BY CURRENT_LOAD ASC
        """

        result_df = session.sql(allocation_query).to_pandas()

        if len(result_df) > 0:
            best = result_df.iloc[0]
            st.success(f"Translated ticket assigned to: **{best['NAME']}**")

            rcol1, rcol2, rcol3, rcol4 = st.columns(4)
            rcol1.metric("Engineer", best["NAME"])
            rcol2.metric("Current Load", f"{best['CURRENT_LOAD']}/{best['MAX_TICKETS']}")
            rcol3.metric("Utilization", f"{best['UTILIZATION_PCT']}%")
            rcol4.metric("Timezone", best["TIMEZONE"])

            st.markdown(f"""
            **Workflow:**
            1. Email received in foreign language
            2. Translated to English using `SNOWFLAKE.CORTEX.TRANSLATE`
            3. Routed to English-speaking engineer on shift (BST: `{bst_now}`)
            4. Assigned to **{best['NAME']}** (lowest load: `{best['CURRENT_LOAD']}/{best['MAX_TICKETS']}`)
            """)
        else:
            st.error("No English-speaking engineer currently on shift.")
