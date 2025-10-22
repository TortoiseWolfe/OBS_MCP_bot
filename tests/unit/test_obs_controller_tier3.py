"""Unit tests for Tier 3 OBS controller methods.

Tests attribution overlay control methods:
- set_source_visibility()
- update_text_content()
- set_source_transform()
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from obswebsocket import requests as obs_requests

from src.config.settings import OBSSettings
from src.services.obs_controller import OBSConnectionError, OBSController


@pytest.fixture
def obs_settings():
    """Create test OBS settings."""
    return OBSSettings(
        websocket_url="ws://localhost:4455",
        password="test_password",
        connection_timeout_sec=10,
        reconnect_interval_sec=2,
        max_reconnect_attempts=3,
    )


@pytest.fixture
def mock_ws():
    """Create mock WebSocket connection."""
    ws = MagicMock()
    ws.call = MagicMock()
    return ws


@pytest.fixture
def connected_controller(obs_settings, mock_ws):
    """Create OBS controller with mocked connection."""
    controller = OBSController(obs_settings)
    controller._ws = mock_ws
    controller._connected = True
    return controller


class TestSetSourceVisibility:
    """Tests for set_source_visibility method."""

    @pytest.mark.asyncio
    async def test_show_source(self, connected_controller, mock_ws):
        """Test showing a source."""
        # Mock GetSceneItemList response
        mock_scene_items = Mock()
        mock_scene_items.getSceneItems.return_value = [
            {"sourceName": "Attribution Text", "sceneItemId": 123}
        ]
        mock_ws.call.return_value = mock_scene_items

        await connected_controller.set_source_visibility(
            scene_name="Automated Content",
            source_name="Attribution Text",
            visible=True
        )

        # Verify both GetSceneItemList and SetSceneItemEnabled were called
        assert mock_ws.call.call_count == 2

        # Verify the second call was SetSceneItemEnabled with correct type
        second_call_args = mock_ws.call.call_args_list[1][0]
        assert len(second_call_args) > 0
        request_obj = second_call_args[0]
        assert isinstance(request_obj, obs_requests.SetSceneItemEnabled)

    @pytest.mark.asyncio
    async def test_hide_source(self, connected_controller, mock_ws):
        """Test hiding a source."""
        mock_scene_items = Mock()
        mock_scene_items.getSceneItems.return_value = [
            {"sourceName": "Attribution Text", "sceneItemId": 456}
        ]
        mock_ws.call.return_value = mock_scene_items

        await connected_controller.set_source_visibility(
            scene_name="Automated Content",
            source_name="Attribution Text",
            visible=False
        )

        # Verify SetSceneItemEnabled was called
        assert mock_ws.call.call_count == 2
        request_obj = mock_ws.call.call_args_list[1][0][0]
        assert isinstance(request_obj, obs_requests.SetSceneItemEnabled)

    @pytest.mark.asyncio
    async def test_source_not_found(self, connected_controller, mock_ws):
        """Test handling when source doesn't exist in scene."""
        mock_scene_items = Mock()
        mock_scene_items.getSceneItems.return_value = [
            {"sourceName": "Other Source", "sceneItemId": 999}
        ]
        mock_ws.call.return_value = mock_scene_items

        # Should not raise, just log warning
        await connected_controller.set_source_visibility(
            scene_name="Automated Content",
            source_name="NonExistent",
            visible=True
        )

        # Should only call GetSceneItemList, not SetSceneItemEnabled
        assert mock_ws.call.call_count == 1

    @pytest.mark.asyncio
    async def test_not_connected(self, obs_settings):
        """Test error when not connected."""
        controller = OBSController(obs_settings)
        controller._connected = False

        with pytest.raises(OBSConnectionError, match="Not connected to OBS"):
            await controller.set_source_visibility("Scene", "Source", True)


class TestUpdateTextContent:
    """Tests for update_text_content method."""

    @pytest.mark.asyncio
    async def test_update_text(self, connected_controller, mock_ws):
        """Test updating text content."""
        await connected_controller.update_text_content(
            source_name="Attribution Text",
            text="MIT OCW 6.0001: Lecture 1 - CC BY-NC-SA 4.0"
        )

        # Verify SetInputSettings was called with correct type
        assert mock_ws.call.call_count == 1
        request_obj = mock_ws.call.call_args[0][0]
        assert isinstance(request_obj, obs_requests.SetInputSettings)

    @pytest.mark.asyncio
    async def test_update_with_unicode(self, connected_controller, mock_ws):
        """Test updating text with unicode characters."""
        text = "Khan Academy: Álgebra básica - CC BY-NC-SA"

        await connected_controller.update_text_content(
            source_name="Attribution",
            text=text
        )

        # Verify SetInputSettings was called with correct type
        assert mock_ws.call.call_count == 1
        request_obj = mock_ws.call.call_args[0][0]
        assert isinstance(request_obj, obs_requests.SetInputSettings)

    @pytest.mark.asyncio
    async def test_update_empty_text(self, connected_controller, mock_ws):
        """Test updating to empty text (hiding attribution)."""
        await connected_controller.update_text_content(
            source_name="Attribution",
            text=""
        )

        # Verify SetInputSettings was called with correct type
        assert mock_ws.call.call_count == 1
        request_obj = mock_ws.call.call_args[0][0]
        assert isinstance(request_obj, obs_requests.SetInputSettings)

    @pytest.mark.asyncio
    async def test_websocket_error(self, connected_controller, mock_ws):
        """Test handling WebSocket errors."""
        mock_ws.call.side_effect = Exception("WebSocket timeout")

        with pytest.raises(OBSConnectionError, match="Failed to update text content"):
            await connected_controller.update_text_content(
                source_name="Attribution",
                text="Test"
            )


class TestSetSourceTransform:
    """Tests for set_source_transform method."""

    @pytest.mark.asyncio
    async def test_set_position(self, connected_controller, mock_ws):
        """Test setting source position."""
        mock_scene_items = Mock()
        mock_scene_items.getSceneItems.return_value = [
            {"sourceName": "Attribution Text", "sceneItemId": 789}
        ]
        mock_ws.call.return_value = mock_scene_items

        await connected_controller.set_source_transform(
            scene_name="Automated Content",
            source_name="Attribution Text",
            x=100,
            y=50
        )

        # Verify SetSceneItemTransform was called
        assert mock_ws.call.call_count == 2  # GetSceneItemList + SetSceneItemTransform
        request_obj = mock_ws.call.call_args_list[1][0][0]
        assert isinstance(request_obj, obs_requests.SetSceneItemTransform)
        # Note: Full parameter validation requires accessing internal request data structure

    @pytest.mark.asyncio
    async def test_set_position_and_scale(self, connected_controller, mock_ws):
        """Test setting both position and scale."""
        mock_scene_items = Mock()
        mock_scene_items.getSceneItems.return_value = [
            {"sourceName": "Attribution", "sceneItemId": 100}
        ]
        mock_ws.call.return_value = mock_scene_items

        await connected_controller.set_source_transform(
            scene_name="Scene",
            source_name="Attribution",
            x=200,
            y=100,
            scale_x=1.5,
            scale_y=1.5
        )

        # Verify SetSceneItemTransform was called
        assert mock_ws.call.call_count == 2
        request_obj = mock_ws.call.call_args_list[1][0][0]
        assert isinstance(request_obj, obs_requests.SetSceneItemTransform)

    @pytest.mark.asyncio
    async def test_bottom_right_positioning(self, connected_controller, mock_ws):
        """Test positioning text in bottom-right corner."""
        mock_scene_items = Mock()
        mock_scene_items.getSceneItems.return_value = [
            {"sourceName": "Attribution", "sceneItemId": 200}
        ]
        mock_ws.call.return_value = mock_scene_items

        # Bottom-right of 1920x1080 display, with 10px padding
        await connected_controller.set_source_transform(
            scene_name="Scene",
            source_name="Attribution",
            x=1920 - 500 - 10,  # 500px wide text, 10px padding
            y=1080 - 50 - 10,   # 50px tall text, 10px padding
            scale_x=0.8,
            scale_y=0.8
        )

        # Verify SetSceneItemTransform was called
        assert mock_ws.call.call_count == 2
        request_obj = mock_ws.call.call_args_list[1][0][0]
        assert isinstance(request_obj, obs_requests.SetSceneItemTransform)

    @pytest.mark.asyncio
    async def test_source_not_in_scene(self, connected_controller, mock_ws):
        """Test handling when source doesn't exist in scene."""
        mock_scene_items = Mock()
        mock_scene_items.getSceneItems.return_value = []
        mock_ws.call.return_value = mock_scene_items

        # Should not raise, just log warning
        await connected_controller.set_source_transform(
            scene_name="Scene",
            source_name="Missing",
            x=0,
            y=0
        )

        # Should only call GetSceneItemList
        assert mock_ws.call.call_count == 1


class TestIntegration:
    """Integration tests for Tier 3 OBS controller methods."""

    @pytest.mark.asyncio
    async def test_show_attribution_workflow(self, connected_controller, mock_ws):
        """Test complete workflow: create text, position, and show attribution."""
        mock_scene_items = Mock()
        mock_scene_items.getSceneItems.return_value = [
            {"sourceName": "Attribution", "sceneItemId": 1}
        ]
        mock_ws.call.return_value = mock_scene_items

        # Step 1: Update text content
        await connected_controller.update_text_content(
            source_name="Attribution",
            text="MIT OCW 6.0001: Lecture 1 - CC BY-NC-SA 4.0"
        )

        # Step 2: Position in bottom-right
        await connected_controller.set_source_transform(
            scene_name="Automated Content",
            source_name="Attribution",
            x=1410,
            y=1020
        )

        # Step 3: Show the attribution
        await connected_controller.set_source_visibility(
            scene_name="Automated Content",
            source_name="Attribution",
            visible=True
        )

        # Verify all 4 calls were made (1 text update + 2 for transform + 2 for visibility)
        assert mock_ws.call.call_count == 5

    @pytest.mark.asyncio
    async def test_hide_attribution_workflow(self, connected_controller, mock_ws):
        """Test hiding attribution overlay."""
        mock_scene_items = Mock()
        mock_scene_items.getSceneItems.return_value = [
            {"sourceName": "Attribution", "sceneItemId": 1}
        ]
        mock_ws.call.return_value = mock_scene_items

        # Hide the attribution
        await connected_controller.set_source_visibility(
            scene_name="Automated Content",
            source_name="Attribution",
            visible=False
        )

        # Verify calls
        assert mock_ws.call.call_count == 2  # GetSceneItemList + SetSceneItemEnabled
