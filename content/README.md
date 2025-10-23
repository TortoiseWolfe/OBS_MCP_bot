# Educational Content Library

This directory contains open-source educational programming content for 24/7 streaming.

## Directory Structure

```
content/
├── failover/               # Emergency failover content
│   └── default_failover.mp4 (Big Buck Bunny)
├── kids-after-school/      # 3-6 PM time block (Creative, beginner-friendly)
│   └── khan-academy/
├── professional-hours/     # 9 AM-3 PM time block (Advanced, professional)
│   └── (TBD - advanced tutorials, tools, workflows)
├── evening-mixed/          # 7-10 PM time block (Algorithms, problem-solving)
│   └── (TBD - mixed difficulty content)
└── general/                # All-audience content (CS fundamentals)
    ├── mit-ocw-6.0001/
    ├── harvard-cs50/
    └── khan-academy/
```

## Content Sources & Licenses

### 1. Big Buck Bunny (Failover Content)
- **License**: Creative Commons Attribution 3.0
- **Source**: Blender Foundation
- **URL**: https://peach.blender.org/
- **Attribution**: © 2008, Blender Foundation / www.bigbuckbunny.org
- **Usage**: Emergency failover content, always available
- **File**: `failover/default_failover.mp4` (151 MB, 9:56 duration)

### 2. MIT OpenCourseWare - Introduction to CS and Programming in Python (6.0001)
- **License**: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 (CC BY-NC-SA 4.0)
- **Source**: MIT OpenCourseWare
- **URL**: https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/
- **Attribution**: MIT OpenCourseWare, 6.0001 Introduction to Computer Science and Programming in Python, Fall 2016
- **Instructor**: Prof. Eric Grimson, Prof. John Guttag, Dr. Ana Bell
- **Content**: 12 lectures covering Python fundamentals, algorithms, data structures
- **Audience**: General (beginners with no prior experience)
- **Download Script**: `../scripts/download_mit_ocw.sh`

**License Terms**:
- ✓ Attribution required
- ✓ Non-commercial use (educational streaming complies)
- ✓ ShareAlike (derivatives must use same license)
- ✗ No commercial use

### 3. Harvard CS50 - Introduction to Computer Science
- **License**: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 (CC BY-NC-SA 4.0)
- **Source**: Harvard University CS50
- **URL**: https://cs50.harvard.edu/
- **Attribution**: Harvard University CS50, Instructor: David J. Malan
- **Content**: Introduction to computer science, algorithms, data structures, C, Python, web development
- **Audience**: General (beginners)
- **Download Script**: `../scripts/download_cs50.sh`

**License Terms**:
- ✓ Attribution required
- ✓ Non-commercial use (educational streaming complies)
- ✓ ShareAlike (derivatives must use same license)
- ✗ No commercial use

### 4. Khan Academy - Computer Programming
- **License**: Creative Commons Attribution-NonCommercial-ShareAlike (CC BY-NC-SA)
- **Source**: Khan Academy
- **URL**: https://www.khanacademy.org/computing/computer-programming
- **Attribution**: Khan Academy
- **Content**: JavaScript basics, drawing & animation, interactive programs
- **Audience**: Kids-after-school, General (very beginner-friendly)
- **Download Script**: `../scripts/download_khan_academy.sh`

**License Terms**:
- ✓ Attribution required
- ✓ Non-commercial use (educational streaming complies)
- ✓ ShareAlike (derivatives must use same license)
- ✗ No commercial use

## Constitutional Compliance

All content in this library complies with **OBS_24_7 Constitution v2.0.0**:

### Principle II: Educational Quality
- ✓ Technically accurate content from verified sources (MIT, Harvard, Khan Academy)
- ✓ Clear explanations accessible to target audience
- ✓ Age-appropriate content enforcement via time blocks

### Principle III: Content Appropriateness
- ✓ Time-based content filtering implemented
- ✓ Kids content (Khan Academy) during 3-6 PM
- ✓ Professional content during business hours
- ✓ General CS fundamentals for evening hours
- ✓ Twitch TOS and DMCA compliant (all CC-licensed)

### Principle VII: Transparent Sustainability
- ✓ All sources openly attributed
- ✓ Non-commercial educational use clearly defined
- ✓ No hidden promotion or undisclosed sponsorship

## Download Instructions

### Prerequisites

Install `yt-dlp` (YouTube downloader):
```bash
pip install yt-dlp
# Or on Debian/Ubuntu:
sudo apt install yt-dlp
```

### Download All Content (Recommended)

```bash
cd scripts/
./download_all_content.sh
```

**Estimated**: 5-10 GB, 1-3 hours depending on connection speed

### Download Individual Sources

```bash
cd scripts/

# MIT OpenCourseWare Python course (~3-5 GB)
./download_mit_ocw.sh

# Harvard CS50 first 5 lectures (~2-3 GB)
./download_cs50.sh

# Khan Academy programming basics (~1-2 GB)
./download_khan_academy.sh
```

## Attribution Requirements

When streaming this content, display attribution in OBS:
- **Text overlay**: "Content: [Source Name] - CC BY-NC-SA 4.0"
- **Scene name**: Include source in scene name (e.g., "MIT OCW - Python Lecture 1")
- **Chat command**: `!attribution` displays current content source and license

## Twitch TOS Compliance (T064)

**Platform**: Twitch.tv
**Channel Purpose**: Educational content streaming (24/7)
**Monetization**: **DISABLED** (no ads, subscriptions, bits, or sponsorships)

### Compliance Statement

This stream operates in full compliance with:
1. **Twitch Terms of Service**: https://www.twitch.tv/p/legal/terms-of-service/
2. **Twitch Community Guidelines**: https://safety.twitch.tv/s/article/Community-Guidelines
3. **Creative Commons Licenses**: All content properly attributed

### Why This Stream is TOS-Compliant

- ✅ **Educational Purpose**: All content is educational (CS/programming)
- ✅ **Licensed Content**: CC BY-NC-SA permits educational streaming
- ✅ **Attribution**: Live on-screen text overlays credit creators
- ✅ **Non-Commercial**: Zero monetization features enabled
- ✅ **No Copyright Violations**: All content legally licensed

### Verification Date

- **Last Checked**: 2025-10-22
- **Next Review**: 2026-10-22

---

## Commercial Use Prohibition (T065)

**CRITICAL**: This content is licensed for **NON-COMMERCIAL EDUCATIONAL USE ONLY**.

### ❌ PROHIBITED Activities

1. **Monetization (ANY FORM)**:
   - NO Twitch Partner/Affiliate programs
   - NO ad revenue (pre-roll, mid-roll, display ads)
   - NO subscription tiers or Twitch Turbo
   - NO bits/cheers from viewers
   - NO sponsorships or brand deals
   - NO affiliate marketing or referral links

2. **Commercial Streaming**:
   - NO corporate training for profit
   - NO paid courses using this content
   - NO conference presentations with paid admission
   - NO selling stream archives or VODs

3. **Redistribution for Profit**:
   - NO selling access to this content library
   - NO bundling with paid services
   - NO licensing to third parties

### ✅ PERMITTED Activities

1. **Educational Streaming**:
   - Free 24/7 educational broadcasts
   - Community study sessions
   - Teaching programming concepts
   - Answering viewer questions about content

2. **Attribution & Sharing**:
   - Linking to original content sources
   - Crediting creators via text overlays
   - Discussing course topics with viewers

3. **Non-Commercial Community**:
   - Building learning communities
   - Sharing knowledge freely
   - Helping viewers learn programming

### Consequences of Violating NC Clause

- **License Violation**: Immediately loses CC BY-NC-SA permissions
- **Copyright Infringement**: Content becomes unauthorized
- **Twitch DMCA**: Subject to takedown notices from MIT, Harvard, Khan Academy
- **Channel Penalties**: Potential Twitch account suspension

---

## License Verification Checklist (T063)

Perform this review **ANNUALLY** or when adding new content:

### Step 1: Verify Source Licenses

- [ ] **MIT OCW**: Check https://ocw.mit.edu/terms/ - Confirm CC BY-NC-SA 4.0 still applies
- [ ] **Harvard CS50**: Check https://cs50.harvard.edu/x/2024/license/ - Verify CC BY-NC-SA 4.0
- [ ] **Khan Academy**: Review https://www.khanacademy.org/about/tos - Section 5 (Licenses)
- [ ] **Big Buck Bunny**: Verify https://peach.blender.org/about/ - CC BY 3.0

### Step 2: Verify Platform Compliance

- [ ] **Twitch TOS**: Review https://www.twitch.tv/p/legal/terms-of-service/ for policy changes
- [ ] **DMCA Policy**: Check https://www.twitch.tv/p/legal/dmca-guidelines/ for updates

### Step 3: Verify Attribution System

- [ ] **OBS Text Overlay**: Test "Content Attribution" text source displays correctly
- [ ] **All Videos**: Verify attribution shows for each video in database
- [ ] **Format**: Confirm "{Source} {Course}: {Title} - {License}" format
- [ ] **Visibility**: Check overlay is readable (font size, color, position)

### Step 4: Verify Monetization Disabled

- [ ] **Twitch Dashboard**: Confirm NO Partner/Affiliate status
- [ ] **Ad Settings**: Verify ads are disabled
- [ ] **Subscription**: Confirm subscription button is OFF
- [ ] **Bits**: Verify bits/cheers are disabled
- [ ] **Third-Party**: Check NO sponsorship integrations

### Step 5: Document Review

- [ ] **Last Verification Date**: 2025-10-22
- [ ] **Next Review Due**: 2026-10-22
- [ ] **Verified By**: System operator
- [ ] **Changes**: Document any license or TOS updates

---

## DMCA & Copyright Compliance

✓ **Safe for Twitch streaming**:
- All content is Creative Commons licensed
- All licenses permit educational, non-commercial use
- Attribution provided per license requirements
- No copyrighted music or unlicensed material

✗ **Not safe for commercial use**:
- Do NOT monetize streams with ads
- Do NOT sell access to this content
- Do NOT use for sponsored streams (violates NC clause)

## Content Metadata

Track content in SQLite database using `ContentSource` entity:

```python
ContentSource(
    source_id=uuid4(),
    source_type="video",
    file_path="/app/content/general/mit-ocw-6.0001/01-What_is_Computation.mp4",
    duration_sec=2847,  # 47:27
    title="What is Computation?",
    instructor="Prof. Eric Grimson",
    source_attribution="MIT OpenCourseWare 6.0001",
    license_type="CC BY-NC-SA 4.0",
    age_rating="all",
    time_blocks=["general", "evening-mixed"],
    priority=5,
    tags=["python", "fundamentals", "computation"]
)
```

## Future Content Sources

Additional CC-licensed content to consider:

1. **The Coding Train (Daniel Shiffman)**
   - Creative coding with Processing and p5.js
   - Code is MIT licensed (verify video licensing)
   - Great for kids-after-school time block

2. **freeCodeCamp**
   - YouTube tutorials on web development
   - Verify licensing for individual videos

3. **Code.org**
   - CS and AI educational videos
   - Free for educational use

4. **CppCon / PyCon / Conference Talks**
   - Many conference talks are CC-licensed
   - Professional-hours content

## Maintenance

### Adding New Content

1. Download content to appropriate time block folder
2. Verify license compliance (must be CC or public domain)
3. Update this README with attribution
4. Add metadata to database using `scripts/add_content_metadata.py`
5. Update OBS scenes to include new content

### Removing Content

1. Delete video files
2. Remove entries from database
3. Update this README
4. Verify failover content still exists

### Monthly Review

- Verify all download links still work
- Check for updated course versions
- Ensure license compliance
- Audit stream logs for content gaps

## Support & Questions

For questions about content licensing or attribution:
- MIT OCW: ocw@mit.edu
- Harvard CS50: help@cs50.harvard.edu
- Khan Academy: https://www.khanacademy.org/about/contact

---

**Last Updated**: 2025-10-22
**Maintainer**: OBS_bot Project
**Constitution Compliance**: v2.0.0 ✓
