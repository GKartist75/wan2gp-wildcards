# wan2gp-wildcards

Wildcard prompt expansion plugin for [Wan2GP](https://github.com/deepbeepmeep/Wan2GP). Randomize prompts with `__wildcard__` and `{opt1|opt2}` syntax.  
35,000+ terms across 280 files in 17+ categories.

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

## Library

### Subdirectory categories (17)

`action` `aesthetic` `camera` `character` `clothing` `color` `composition` `effect` `emotion` `environment` `lighting` `material` `motion` `quality` `time` `transition` `weather`

### Flat wildcards (211 files, sourced from [sd-wildcards](https://github.com/mattjaybe/sd-wildcards))

| Group | Files |
|---|---|
| **Adjective** | adj-architecture, adj-beauty, adj-general, adj-horror |
| **Animal** | animal, bird, cat, dog, fish, dinosaur |
| **Artist** | artist (general), artist-anime, artist-cartoon, artist-concept, artist-csv, artist-dig1/2/3, artist-fantasy, artist-fareast, artist-fineart, artist-horror, artist-nudity, artist-scifi, artist-scribbles, artist-surreal, artist-ukioe, artist-weird, artist-black-white, artist-botanical, artist-c, artist-director, artist-n, artist-photographer, artist-special |
| **Body** | body-fit, body-shape, body-shape2, body-tall, body-short, body-heavy, body-light, body-poor, body-framing |
| **Camera** | camera, camera-manu, angle, focal-length, f-stop, iso-stop |
| **Character** | class, gender, gender-ext, race, nationality, occupation, identity, age (female-adult, female-young, male-adult, male-young) |
| **Clothing/Accessory** | clothing, clothing-female, clothing-male, costume-female, costume-male, suit-female, suit-male, dress, swimwear, high-heels, belt, choker, earrings, eyeliner, hair-accessory, headwear-f/m, legwear, neckwear, purse, bangs, braid, makeup, lipstick, lipstick-shade |
| **Color** | color, background-color, eye-color, hair-color, skin-color |
| **Cosmic** | cosmic-galaxy, cosmic-nebula, cosmic-star, cosmic-term, planet |
| **Emotion/Expression** | expression |
| **Environment** | landscape, biome, forest-type, national-park, interior, location, water, underwater, wave, background, setting |
| **Fantasy/Horror/Scifi** | fantasy, fantasy-creature, fantasy-setting, horror, monster, alien, robot, scifi, deity, angel, demon |
| **Food/Plant** | food, fruit, flower, tree |
| **Hair** | hair-female, hair-female-short, hair-male, hair-length, hair-color |
| **Media/Style** | style, genre, film-genre, technique, pose, portrait-type, photoshoot-type, still-life, oil-painting, watercolor, sculpture, photo-term, 3d-term |
| **Name** | name-female, name-male |
| **Nature** | biome, landscape, forest-type, national-park, tree, flower, fruit, water, wave, underwater |
| **Noun** | noun-general, noun-beauty, noun-fantasy, noun-horror, noun-landscape, noun-romance, noun-scifi |
| **NSFW** | nsfw-bdsm, nsfw-bdsm-type, nsfw-bra, nsfw-breastsize, nsfw-clothing-state, nsfw-corset, nsfw-cumplay, nsfw-expression, nsfw-fetish, nsfw-gag, nsfw-lingerie, nsfw-lingerie-state, nsfw-panties, nsfw-position, nsfw-publicity, nsfw-sex-act, nsfw-sex-position, nsfw-sex-toy, nsfw-subreddit |
| **Pop Culture** | pop-culture, pop-location, game, rpg-Item, superhero, punk, trippy |
| **Quality** | render, render-engine, hd, detail, neg-weight |
| **Scenario** | scenario, scenario2, scenario-fantasy, scenario-romance, scenario-scifi |
| **Subject** | subject, subject-fantasy, subject-horror, subject-romance, subject-scifi |
| **Time** | time, decade |
| **Other** | actor, actress, celeb, supermodel, civilization, tribe, ship, train, furniture, gem, nationality, race, quantity, site, public, background, detail, setting, aspect-ratio, gen-modifier, emoji, emoji-combo |

## Files

```
wan2gp-wildcards/
├── __init__.py
├── plugin.py          # WAN2GPPlugin + monkey-patch + autocomplete
├── expander.py        # expansion engine
├── plugin_info.json   # metadata
├── README.md
└── wildcards/
    ├── __index__.txt
    ├── action/        # 3 files (combat, dance, ...)
    ├── aesthetic/     # 3 files (art-movement, cultural, vibe)
    ├── camera/        # 5 files (angle, lens, shot, ...)
    ├── character/     # 5 files (age, archetype, body, ...)
    ├── clothing/      # 6 files (accessory, bottom, ...)
    ├── color/         # 3 files (named, palette, skin)
    ├── composition/   # 2 files (framing, layout)
    ├── effect/        # 3 files (distortion, postprocess, vfx)
    ├── emotion/       # 3 files (atmosphere, expression, mood)
    ├── environment/   # 6 files (fantasy, interior, nature, ...)
    ├── lighting/      # 5 files (direction, quality, source, ...)
    ├── material/      # 3 files (organic, substance, surface)
    ├── motion/        # 3 files (character, quality, speed)
    ├── quality/       # 3 files (film, render, resolution)
    ├── time/          # 3 files (day, era, season)
    ├── transition/    # 3 files (cut, dissolve, wipe)
    ├── weather/       # 4 files (extreme, fog, ...)
    └── 211 flat .txt files (see Library section)
```

## Credits

Author: GKartist75 (with PI Agent)  
Built in collaboration with [PI Agent](https://github.com/earendil-works/pi-coding-agent).  
Flat wildcard library sourced from [sd-wildcards](https://github.com/mattjaybe/sd-wildcards).

## Requirements

Wan2GP only. No external dependencies.
