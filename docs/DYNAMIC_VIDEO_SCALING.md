# Dynamic Video Scaling - COMPLETE

**Date**: 2025-10-22
**Feature**: Automatic video scaling to fit OBS canvas
**Status**: Production ready

## Problem Statement

Videos from different sources have different resolutions:
- MIT OCW: 480x360 (4:3 SD)
- Harvard CS50: 1280x720 (16:9 HD)
- Big Buck Bunny: 1280x720 (16:9 HD)

Without dynamic scaling, videos would appear at incorrect sizes or be cropped/stretched.

## Solution

Implemented automatic aspect-ratio-preserving scaling that:
1. Detects each video's resolution from metadata
2. Queries the OBS canvas size (1920x1080)
3. Calculates optimal scale factor to fit while maintaining aspect ratio
4. Centers the video with black bars if needed
5. Applies transform dynamically when switching videos

## Implementation

### 1. Database Schema Enhancement
**File**: `src/persistence/db.py` (lines 121-122)

Added resolution columns to `content_sources` table:
```sql
width INTEGER NOT NULL CHECK(width > 0),
height INTEGER NOT NULL CHECK(height > 0),
```

### 2. Domain Model Update
**File**: `src/models/content_library.py` (lines 99-100)

Added resolution fields to `ContentSource`:
```python
width: int = Field(gt=0, description="Video width in pixels")
height: int = Field(gt=0, description="Video height in pixels")
```

### 3. Metadata Extraction
**File**: `src/services/content_metadata_manager.py`

Enhanced ffprobe extraction (lines 146, 185-217):
- Added `stream=width,height` to ffprobe query
- Parse video stream dimensions from ffprobe JSON output
- Store resolution in ContentSource entity

### 4. OBS Controller Methods
**File**: `src/services/obs_controller.py` (lines 681-751)

Added two new methods:

#### `get_canvas_resolution()` (lines 681-707)
Queries OBS canvas (base) resolution via WebSocket:
```python
async def get_canvas_resolution(self) -> tuple[int, int]:
    """Get OBS canvas (base) resolution."""
    ws = self._ensure_connected()
    video_settings = ws.call(obs_requests.GetVideoSettings())
    width = video_settings.getBaseWidth()
    height = video_settings.getBaseHeight()
    return (width, height)
```

#### `calculate_video_transform()` (lines 709-751)
Calculates optimal scaling and centering:
```python
def calculate_video_transform(
    self,
    video_width: int,
    video_height: int,
    canvas_width: int,
    canvas_height: int
) -> tuple[int, int, float, float]:
    """Calculate optimal transform to fit video in canvas while maintaining aspect ratio."""
    # Calculate scale factor (maintain aspect ratio)
    scale_x_factor = canvas_width / video_width
    scale_y_factor = canvas_height / video_height
    scale_factor = min(scale_x_factor, scale_y_factor)

    # Calculate scaled dimensions
    scaled_width = video_width * scale_factor
    scaled_height = video_height * scale_factor

    # Center the video
    x_position = int((canvas_width - scaled_width) / 2)
    y_position = int((canvas_height - scaled_height) / 2)

    return (x_position, y_position, scale_factor, scale_factor)
```

### 5. Content Scheduler Integration
**File**: `src/services/content_scheduler.py` (lines 203-228)

Added dynamic scaling to playback loop:
```python
# Get canvas resolution and calculate optimal transform
canvas_width, canvas_height = await self.obs.get_canvas_resolution()
x_pos, y_pos, x_scale, y_scale = self.obs.calculate_video_transform(
    video_width=content_source.width,
    video_height=content_source.height,
    canvas_width=canvas_width,
    canvas_height=canvas_height
)

# Apply transform to scale and center video
await self.obs.set_source_transform(
    scene_name="Automated Content",
    source_name="Content Player",
    x=x_pos,
    y=y_pos,
    scale_x=x_scale,
    scale_y=y_scale
)

logger.info(
    "content_player_scaled",
    title=content_source.title,
    resolution=f"{content_source.width}x{content_source.height}",
    canvas=f"{canvas_width}x{canvas_height}",
    scale=round(x_scale, 3)
)
```

## Results

### MIT OCW Videos (480x360)
- **Original**: 480x360
- **Scale Factor**: 3.0x
- **Rendered Size**: 1440x1080
- **Position**: (240, 0) - centered with 240px black bars on each side
- **Aspect Ratio**: Preserved (4:3)

### CS50/Blender Videos (1280x720)
- **Original**: 1280x720
- **Scale Factor**: 1.5x
- **Rendered Size**: 1920x1080
- **Position**: (0, 0) - fills canvas exactly
- **Aspect Ratio**: Preserved (16:9)

## Verification

Logs confirm dynamic scaling is working:
```json
{
  "title": "Branching And Iteration",
  "resolution": "480x360",
  "canvas": "1920x1080",
  "scale": 3.0,
  "event": "content_player_scaled",
  "level": "info",
  "timestamp": "2025-10-22T21:31:41.515840Z"
}
```

OBS WebSocket query confirms proper dimensions:
```
Content Player dimensions:
  Source: 480.0x360.0
  Rendered: 1440.0x1080.0
  Scale: 3.0x, 3.0y
  Position: (240.0, 0.0)
✅ Video has dimensions - should be visible!
```

## Known Issues & Fixes

### Issue 1: Windows Path Mapping
**Problem**: Initial metadata scan used container paths (`/app/content`) which OBS on Windows couldn't access.

**Fix**: Updated database paths to use host paths:
```sql
UPDATE content_sources
SET windows_obs_path = REPLACE(windows_obs_path,
    '\\wsl.localhost\Debian\app\content',
    '\\wsl.localhost\Debian\home\turtle_wolfe\repos\OBS_bot\content')
```

**Prevention**: Future metadata scans should be run from host, not container.

### Issue 2: Environment Variable Loading
**Problem**: Docker container wasn't loading `OBS_WEBSOCKET_PASSWORD` after rebuild.

**Fix**: Recreated container with `docker compose down && docker compose up -d` to reload .env file.

**Note**: Container restarts (`docker compose restart`) don't reload .env - need full recreation.

## Database Population

All 19 videos scanned and populated with resolution data:
```
480x360 (12 videos) - MIT OCW lectures
1280x720 (7 videos) - CS50 + Blender content
```

## Future Enhancements

Potential improvements not currently needed:
1. **Letterboxing color**: Currently black bars, could make configurable
2. **Zoom to fill**: Option to crop video to fill canvas (losing aspect ratio)
3. **Resolution validation**: Warn if video resolution too low for canvas
4. **Performance**: Cache canvas resolution instead of querying each time

## Related Files

- Database migration: `src/persistence/db.py:121-122`
- Domain model: `src/models/content_library.py:99-100`
- Metadata extraction: `src/services/content_metadata_manager.py:146,185-217`
- OBS controller: `src/services/obs_controller.py:681-751`
- Content scheduler: `src/services/content_scheduler.py:203-228`
- Repository: `src/persistence/repositories/content_library.py:196-199,429-430`

## Testing

Manual testing confirmed:
- ✅ 480x360 videos scale 3.0x and center correctly
- ✅ 1280x720 videos scale 1.5x and fill canvas
- ✅ Aspect ratios preserved (no stretching/distortion)
- ✅ Black bars appear correctly for non-16:9 content
- ✅ Transform applied before scene switch (no flicker)
- ✅ Logs show scaling calculations

No automated tests added yet - this is a production-verified feature.
