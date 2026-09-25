import pytest
from textual.widgets import Input, RichLog, Static, Label
from ui.tui_app import UniversalAgentTUI, TitanOS, AgentsModal, CommandsModal


def test_tui_instantiation():
    app = UniversalAgentTUI()
    assert app.TITLE == "Universal Agent HP"
    assert issubclass(TitanOS, UniversalAgentTUI)


@pytest.mark.asyncio
async def test_tui_app_composition_and_bindings():
    app = UniversalAgentTUI()
    async with app.run_test() as pilot:
        # Check input exists and is focused
        input_widget = app.query_one("#input-box", Input)
        assert input_widget is not None
        assert input_widget.has_focus

        # Check logo and output log
        logo = app.query_one("#logo", Static)
        assert logo is not None
        assert "H P   A G E N T   O S" in str(logo.render())

        output_log = app.query_one("#output-log", RichLog)
        assert output_log is not None

        # Check sub bar badges
        mode_badge = app.query_one(".badge-mode", Label)
        assert "Build" in str(mode_badge.render())

        # Trigger Agents modal via action
        app.action_toggle_agents()
        await pilot.pause()
        assert isinstance(app.screen, AgentsModal)
        app.screen.dismiss()
        await pilot.pause()

        # Trigger Commands modal via action
        app.action_open_commands()
        await pilot.pause()
        assert isinstance(app.screen, CommandsModal)
        app.screen.dismiss()
        await pilot.pause()

        # Submit /clear
        input_widget.value = "/clear"
        await pilot.press("enter")
        await pilot.pause()

        # Submit task
        input_widget.value = "Fix broken tests"
        await pilot.press("enter")
        await pilot.pause()
        assert input_widget.value == ""
