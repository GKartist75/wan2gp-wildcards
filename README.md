# wan2gp-wildcards

Wildcard prompt expansion plugin for [Wan2GP](https://github.com/deepbeepmeep/Wan2GP).  
**34,000+ terms** across **190 files** in **17 subdirectory categories** + **101 flat wildcards**.

## Install

1. **Plugins** tab → **Install New Plugin**
2. Paste: `https://github.com/GKartist75/wan2gp-wildcards`
3. Click **Download and Install**
4. Enable it → **Save Settings** → **Restart**

## Usage

| Syntax | Effect | Example |
|---|---|---|
| `__name__` | Random line from `wildcards/name.txt` | `__camera_shot__` → `close-up shot` |
| `__dir__` | Random line from ALL files in `wildcards/dir/` | `__color__` → pooled from all color files |
| `__dir/file__` | Specific file in subdirectory | `__color/named__` |
| `{a\|b\|c}` | Random inline choice | `{cinematic\|vintage\|raw}` |
| `N::value` | Weighted option (weight N) | `3::sunset` = 3× more likely |

### Inline Autocomplete

Type `__` in the **Test Expansion** or **Batch Generate** textbox → dropdown shows matching wildcards at cursor.  
Arrow keys / Enter / Tab / Click to insert. Escape to dismiss.

### Batch Mode

**Batch Generate N Variations** — enter a template with wildcards, set count, generate N expanded prompts, send straight to the prompt box.

### Seed

- **Seed = -1** → random each time
- **Fixed seed** → deterministic expansion (same seed = same picks)

## Character Profiles

Define named characters with appearance descriptions. Each character becomes
a wildcard file — use `__character/Name__` in your prompt to inject their
appearance. Voice, clothing, and tags are metadata stored for other plugins
(LTX Director, SeedVC, etc.) to consume.

### Managing Characters

Open the **Wildcards** tab → **Character Profiles** section.

1. Pick a character from the dropdown to edit, or click **New**
2. Fill in:
   - **Name** — identifier used in wildcard syntax
   - **Appearance** — main description (what `__character/Name__` expands to)
   - **Voice sample** — path/filename for TTS plugins (e.g. `voice_sarah.wav`)
   - **Clothing**, **Tags**, **Notes** — metadata
3. Click **Save** — creates/updates `wildcards/character/{Name}.txt`
4. Use `__character/Sarah__` in any prompt → expands to appearance text

You can list multiple appearance variants (one per line) for randomized
variety while keeping the character identity consistent.

### Example

```
Prompt:  "__character/Sarah__ walks through market, cinematic lighting"
Expands: "blonde hair, blue eyes, red dress, fair skin woman walks through market, cinematic lighting"
```

For multi-shot video projects (LTX Director, Scail 2): every window uses
`__character/Sarah__` → same appearance every time. Voice path in the
profile lets audio plugins pick the right voice sample per character.

## Library

### Subdirectory categories (17 dirs, 89 files)

| Directory | Files | What's inside |
|---|---|---|
| `action/` | combat, dance, interaction, movement | actions, gestures, combat moves |
| `aesthetic/` | art-movement, cultural, vibe, punk, trippy | art movements, cultural themes, vibes |
| `camera/` | angle, lens, shot, movement, technique, phrase, focal-length, f-stop, iso-stop, manufacturer, photoshoot, portrait | camera angles, lens types, shot types, camera specs |
| `character/` | age, archetype, body, gender, identity, profession, species, phrase | character traits, body types, jobs, species, classes |
| `clothing/` | accessory, bottom, fabric, footwear, garment, style, top | clothing items, accessories, fabrics, styles |
| `color/` | named, palette, skin | named colors, palettes, skin tones |
| `composition/` | framing, layout | shot composition, framing techniques |
| `effect/` | distortion, postprocess, vfx | visual effects, post-processing |
| `emotion/` | atmosphere, expression, horror, mood, phrase | emotions, facial expressions, moods |
| `environment/` | fantasy, interior, nature, scifi, urban, water, cosmic, background, setting, phrase | environments, landscapes, locations, biomes |
| `lighting/` | direction, quality, source, style, temp, phrase | lighting setups, qualities, sources |
| `material/` | gem, organic, substance, surface | materials, surfaces, substances |
| `motion/` | character, pose, quality, speed | motion types, poses, motion qualities |
| `quality/` | film, render, resolution, technique | render/film quality, art techniques |
| `time/` | day, decade, era, season, time | times of day, seasons, eras |
| `transition/` | cut, dissolve, wipe | video transitions |
| `weather/` | extreme, fog, precipitation, sky | weather conditions, sky types |

### Flat wildcards (101 files)

| Group | Files | Lines |
|---|---|---|
| **Adjective** | adj-architecture, adj-beauty, adj-general, adj-horror | 1,637 |
| **Animal** | animal, bird, cat, dog, fish, dinosaur | 4,109 |
| **Artist** | artist + 25 artist-* files (anime, fineart, cartoon, csv, scribbles, etc.) | 9,543 |
| **Hair** | hair-color, hair-female, hair-female-short, hair-length, hair-male | 160 |
| **Name** | name-female, name-male | 415 |
| **Noun** | noun-general, noun-beauty, noun-fantasy, noun-horror, noun-landscape, noun-romance, noun-scifi | 2,069 |
| **NSFW** | 19 nsfw-* files (bdsm, bra, lingerie, sex-act, position, toy, etc.) | 697 |
| **Scenario** | scenario, scenario2, scenario-fantasy, scenario-romance, scenario-scifi | 398 |
| **Subject** | subject, subject-fantasy, subject-horror, subject-romance, subject-scifi | 405 |
| **Pop Culture** | pop-culture, pop-location, game, rpg-Item, superhero | 1,281 |
| **Actor/Celeb** | actor, actress, celeb, supermodel | 1,107 |
| **Emoji** | emoji, emoji-combo | 1,101 |
| **Other** | style, genre, civilization, tribe, ship, train, aspect-ratio, gen-modifier, neg-weight, public, site, quantity, hair-color | — |

## File Tree

```
wan2gp-wildcards/
├── __init__.py
├── plugin.py              # plugin + monkey-patch + autocomplete JS
├── expander.py            # expansion engine
├── character_manager.py   # character profile CRUD + wildcard sync
├── plugin_info.json
├── README.md
├── characters/
│   └── profiles.json      # character profile storage
└── wildcards/
    ├── __index__.txt
    ├── action/        (4 files)
    ├── aesthetic/     (5 files)
    ├── camera/        (12 files)
    ├── character/     (8 files)
    ├── clothing/      (7 files)
    ├── color/         (3 files)
    ├── composition/   (2 files)
    ├── effect/        (3 files)
    ├── emotion/       (5 files)
    ├── environment/   (10 files)
    ├── lighting/      (6 files)
    ├── material/      (4 files)
    ├── motion/        (4 files)
    ├── quality/       (4 files)
    ├── time/          (5 files)
    ├── transition/    (3 files)
    ├── weather/       (4 files)
    └── 101 flat .txt files
```

## Credits

Author: GKartist75 (with PI Agent)  
Built in collaboration with [PI Agent](https://github.com/earendil-works/pi-coding-agent).

## Requirements

Wan2GP only. No external dependencies.
