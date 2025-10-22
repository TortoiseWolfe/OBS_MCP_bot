# OBS Attribution Text Source Setup

## Overview

The content library management system (Tier 3) requires a text source in OBS called **"Content Attribution"** to display proper Creative Commons license attribution during streaming. This ensures legal compliance with CC BY-NC-SA licenses for all educational content.

## Why This Is Required

All content from MIT OCW, Harvard CS50, and Khan Academy is licensed under **Creative Commons Attribution-NonCommercial-ShareAlike (CC BY-NC-SA)**. This license **requires** visible attribution during use.

**Without proper attribution, streaming this content violates the license terms.**

## Quick Setup (5 minutes)

### Step 1: Create the Text Source

1. Open **OBS Studio**
2. Select any scene (recommendation: "Automated Content" scene)
3. Right-click in the **Sources** panel
4. Select **Add → Text (FreeType 2)**
5. Name it exactly: `Content Attribution`
6. Click **OK**

### Step 2: Configure the Text Source

In the text source properties dialog:

**Text Content:**
```
[This will be automatically updated by the system]
```
(Leave the initial text as anything - it will be replaced automatically)

**Font Settings:**
- **Font Family:** Arial, Liberation Sans, or any clear sans-serif font
- **Font Size:** **28-32 pixels** (readable but not intrusive)
- **Font Style:** Regular (not bold, not italic)

**Color Settings:**
- **Text Color:** White (`#FFFFFF`) or Light Gray (`#EEEEEE`)
- **Opacity:** 100%

**Outline (CRITICAL for readability):**
- **Enable Outline:** ✓ Checked
- **Outline Size:** **2-3 pixels**
- **Outline Color:** Black (`#000000`)
- **Outline Opacity:** 100%

**Background (Optional but Recommended):**
- **Enable Background:** ✓ Checked
- **Background Color:** Semi-transparent black (`#000000` at 50-70% opacity)
- **Padding:** 8-12 pixels

### Step 3: Position the Text

**Recommended Positions:**

**Option A: Bottom-Left Corner (Recommended)**
- X: 20-40 pixels from left edge
- Y: Screen height - 60 pixels (e.g., 1020 for 1080p)
- Anchor: Bottom-Left

**Option B: Bottom-Right Corner**
- X: Screen width - text width - 40 pixels
- Y: Screen height - 60 pixels
- Anchor: Bottom-Right

**Option C: Top-Right Corner (if bottom is crowded)**
- X: Screen width - text width - 40 pixels
- Y: 20 pixels from top
- Anchor: Top-Right

**Visibility:**
- Ensure the text does NOT overlap with:
  - Webcam overlay
  - Channel name/logo
  - Donation alerts
  - Chat overlay

### Step 4: Verify Setup

1. In OBS, ensure the text source is **visible** (eye icon enabled)
2. The text should be readable against all background content
3. Start the orchestrator system
4. Check logs for: `preflight_check_passed check=attribution_text_source`

## Automatic Updates

Once configured, the system will **automatically update the text** when content changes:

**Format:**
```
[Source] [Course]: [Title] - [License]
```

**Examples:**
- `MIT OCW 6.0001: What is Computation? - CC BY-NC-SA 4.0`
- `Harvard CS50: Introduction to Computer Science - CC BY-NC-SA 4.0`
- `Khan Academy: Intro to JavaScript - CC BY-NC-SA`
- `Big Buck Bunny © Blender Foundation - CC BY 3.0` (failover)

## Advanced Configuration

### Custom Text Source Name

If you need to use a different name (not recommended):

1. Edit `src/services/obs_attribution_updater.py`
2. Change `DEFAULT_TEXT_SOURCE_NAME = "Content Attribution"` to your preferred name
3. Rebuild Docker container: `docker compose -f docker-compose.prod.yml build`

### Custom Styling

To match your stream's branding:

**Font Customization:**
- Use any font installed on your system
- Monospace fonts (e.g., Courier) work well for technical content
- Serif fonts (e.g., Georgia) can enhance educational feel

**Color Schemes:**

**Dark Theme (Recommended):**
- Text: `#EEEEEE` (light gray)
- Outline: `#000000` (black, 2-3px)
- Background: `#000000` at 60% opacity

**Light Theme (for dark backgrounds):**
- Text: `#222222` (dark gray)
- Outline: `#FFFFFF` (white, 2-3px)
- Background: `#FFFFFF` at 70% opacity

**High Contrast (Maximum Readability):**
- Text: `#FFFFFF` (white)
- Outline: `#000000` (black, 3px)
- Background: `#000000` at 80% opacity

### Multi-Scene Setup

If you want attribution visible across multiple scenes:

**Option 1: Copy Source to All Scenes**
1. Right-click the source → **Copy**
2. Switch to another scene
3. Right-click Sources panel → **Paste (Reference)**
   - This shares the same source (text updates everywhere automatically)

**Option 2: Scene Collection Setup**
1. Create attribution in a dedicated scene called "Attribution Overlay"
2. Add "Attribution Overlay" as a nested scene source in all content scenes
3. Updates propagate to all scenes automatically

## Troubleshooting

### "Text source not found" error during startup

**Cause:** Text source doesn't exist or has wrong name

**Fix:**
1. Verify source exists: OBS → Sources panel → Look for "Content Attribution"
2. Check exact name (case-sensitive, no extra spaces)
3. Restart orchestrator after creating source

### Text not updating automatically

**Cause:** Source might be locked or OBS WebSocket permission issue

**Fix:**
1. Unlock source: Right-click source → Uncheck "Lock"
2. Verify WebSocket enabled: OBS → Tools → WebSocket Server Settings
3. Check logs: `docker compose -f docker-compose.prod.yml logs obs_bot_orchestrator`

### Text is too small/large

**Fix:**
- Small text: Increase font size to 32-36px
- Large text: Decrease font size to 24-28px
- Always test at streaming resolution (1080p or 720p)

### Text not readable against content

**Fix:**
1. Increase outline size to 3-4px
2. Enable background with 70-80% opacity
3. Move to corner with consistent background color

### Text cuts off at screen edge

**Fix:**
1. Add more padding/margin (move away from edge)
2. Enable text wrapping in source properties
3. Use a smaller font size

## OBS Scene Recommendations

### Automated Content Scene

This scene plays educational content 24/7:

**Required Sources:**
1. **Content Player** - Media source pointing to current video file
2. **Content Attribution** - Text source (this guide)
3. **Content Credits** - Optional supplementary attribution
4. **Channel Info Overlay** - Optional branding

### Failover Scene

Displayed during technical difficulties:

**Required Sources:**
1. **Failover Video** - Big Buck Bunny looping
2. **Content Attribution** - Auto-updates to "Big Buck Bunny © Blender Foundation - CC BY 3.0"
3. **Technical Difficulties Message** - Warning text
4. **Channel Info** - GitHub link and project info

## Legal Compliance Notes

### What the License Requires

**Creative Commons BY-NC-SA mandates:**
- ✓ **Attribution:** Display source, author, and license (this text source handles it)
- ✓ **Non-Commercial:** No monetization, no ads, no sponsored content
- ✓ **ShareAlike:** Any derivatives must use same license

### What You MUST NOT Do

- ✗ **Remove or hide attribution** - Always keep text source visible
- ✗ **Run ads during educational content** - Violates "Non-Commercial" clause
- ✗ **Claim content as your own** - Always display proper attribution
- ✗ **Use for commercial training courses** - Educational streaming only

### Audit Checklist

Before going live:
- [ ] Attribution text source exists and is named "Content Attribution"
- [ ] Text is readable at streaming resolution (720p/1080p)
- [ ] Text doesn't overlap other UI elements
- [ ] Orchestrator startup validation passes
- [ ] Text updates automatically when content changes
- [ ] No ads or monetization enabled on stream
- [ ] Stream is categorized as "Educational" on Twitch

## Support

**Pre-flight validation error?**
```
❌ ATTRIBUTION TEXT SOURCE EXISTS
   Error: Text source 'Content Attribution' not found in OBS
```

**Solution:** Follow Step 1-3 above to create the text source.

**For more help:**
- See `docs/CONTENT_ARCHITECTURE.md` for system overview
- See `content/README.md` for license details
- Check logs: `docker compose -f docker-compose.prod.yml logs`
- GitHub Issues: https://github.com/TortoiseWolfe/OBS_bot/issues

---

**Last Updated:** 2025-10-22
**Tier:** 3 (Content Library Management)
**Task:** T031 (User Story 5: OBS Integration)
