import streamlit as st
from i18n import initialize_language, option_label
from workspace import PAGES, ROOT, db, nav_sidebar, page_header

st.set_page_config(page_title="Cyberdesk AI", page_icon=str(ROOT / "assets" / "brand.png"), layout="wide",
                   initial_sidebar_state="expanded")
initialize_language(db())
routes = [st.Page(f"app_pages/{slug}.py", title=option_label(name),
                  default=slug == "dashboard") for name, (slug, icon) in PAGES.items()]
current = st.navigation(routes, position="hidden")
st.html(ROOT / "assets" / "workspace.css")
nav_sidebar(current.title)
page_header(current.title)
current.run()
