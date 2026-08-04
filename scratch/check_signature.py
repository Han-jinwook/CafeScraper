import inspect
import app.utils.streamlit_top_nav as nav

print("File path:", nav.__file__)
print("render_settings_card_title signature:", inspect.signature(nav.render_settings_card_title))
try:
    nav.render_settings_card_title("Test Title", icon="ia-info")
    print("Call with icon='ia-info' succeeded!")
except Exception as e:
    print("Call with icon='ia-info' failed:", type(e), e)
