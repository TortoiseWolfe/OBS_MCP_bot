# ScriptHammer 24/7: the tutorial backlog on air

## What Jonathan asked for (Sun 1 Nov 2026, about 7:25 AM, to the tower hub)

> try to keep something on 24/7, coordinate with Hatch as the Producer, don't forget we should have a whole backlog of eductional tutorials. Most of which have their own updates needed, try to review them for production mistakes, bad UI/UX decisions, badly formatted text leaving white space on screen or clipping on word on it's own line etc.

His standing rule from the night before (Sat 31 Oct, about 9:05 PM):

> streams are always recorded ahead of time ... it needs to be done right from the start, encode before scheduling

## What that means here

- Only finished, checked files go on air, sent with `-c copy` (no live encoding). Nothing is scheduled until it passes its checks.
- The backlog is the rendered tutorials in `~/clawd-twitch/renders` (registry `~/clawd-twitch/episodes.json`). Their source is `~/repos/openclaw/remotion` and `~/repos/openclaw/toolkit/video`.
- Hatch (Jonathan's producer agent) owns the programming: order, blocks, and the posts about it. A title, category or schedule change still needs Jonathan's word.
- Each tutorial is reviewed for production mistakes, poor layout choices, text that leaves empty screen space, clipped text, and single words left alone on a line. What fails is listed for an update. It doesn't air until it's fixed.
