# wan2gp-wildcards

Wildcard prompt expansion plugin for [Wan2GP](https://github.com/deepbeepmeep/Wan2GP).  
**149,000+ terms** across **3,044 files** in **67 subdirectory categories** + **729 flat wildcards** (merged from all major wildcard collections).

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

| Mode | Behavior |
|---|---|
| **Sequential** (default) | Each variable picks line-by-line through its file. Index 0 → line 1, index 1 → line 2, etc. Cycles when exhausted. No repeats until all lines used. |
| **Random** | Each variation uses fresh randomness — true random, no seed lock. |

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

## Changelog

### v1.3.0
- **UI reorder**: Prompt Builder (test + batch generate + send) moved to top. Character Profiles second. File Browser and Cross-File Search moved below.
- **Collapsed Quick Start guide** into compact header line.
- **Searchable file browser**: category filter + search box + favorites-only mode.
- **Cross-file content search**: search all 3,044 files for any term.
- **Favorites system**: star files for quick access, persisted across restarts.
- **Version bumped** to 1.3.0.

### v1.2.0
- **Merged all remaining wildcard collections**: 939 files from billions of wildcards, 318 from YetAnotherWildcardCollection, 969 from first billions pass, 528 from sd-dynamic-prompts, 110 from sd-wildcards.
- **3,044 total files** across 67 categories.
- **Bugs fixed**: sequential mode cycling, weight detection, dropdown refresh, create auto-selects.

### v1.1.0
- Character profile manager with wildcard sync.
- Inline autocomplete JS.

## Library

## Wildcard Index

### Core categories (17 dirs, 89 files)

| Directory | Files | What's inside |
|---|---|---|
| `action/` | 4 | combat, dance, interaction, movement |
| `aesthetic/` | 5 | art-movement, cultural, vibe, punk, trippy |
| `camera/` | 12 | angle, lens, shot, movement, technique, focal-length, photoshoot |
| `character/` | 8 | age, archetype, body, gender, identity, profession, species |
| `clothing/` | 7 | accessory, bottom, fabric, footwear, garment, style, top |
| `color/` | 3 | named, palette, skin |
| `composition/` | 2 | framing, layout |
| `effect/` | 3 | distortion, postprocess, vfx |
| `emotion/` | 5 | atmosphere, expression, horror, mood |
| `environment/` | 10 | fantasy, interior, nature, scifi, urban, water, cosmic, background, setting |
| `lighting/` | 6 | direction, quality, source, style, temp |
| `material/` | 4 | gem, organic, substance, surface |
| `motion/` | 4 | character, pose, quality, speed |
| `quality/` | 4 | film, render, resolution, technique |
| `time/` | 5 | day, decade, era, season, time |
| `transition/` | 3 | cut, dissolve, wipe |
| `weather/` | 4 | extreme, fog, precipitation, sky |

### Character & Creature (10 dirs, 503 files)

| Directory | Files | What's inside |
|---|---|---|
| `characters/` | 245 | beings (cthulu, cyberpunk, dr who, halo, star wars), professions (historical, magical, scifi), classes, weapons, items, magical-beings |
| `creatures/` | 43 | appendages, body-shapes, descriptors, dragons, ears, horns, skin-fur, tails, wings, species (birds, mammals, mythical, aquatic) |
| `Species/` | 63 | alien, aquatic, avian, bear, cat, dog, dragon, eevee, fox, furry, humanoid, insect, lion, monkey, monster, pokemon (1,204), rabbit, robot, scalie, wolf + 33 composite hybrids |
| `person/` | 34 | ages, beard, body-feature, bodyshapes, ethnicity, face-shape, poses, skin, waist, lips, nose, eyes, ears, hair |
| `Body/` | 37 | body-type (fit/heavy/light/shape/tall/short), ears, eyes (shape, pupil, sclera), face-shape, genitalia (breasts, penis, pussy, nipple), hair (color, texture, length, facial, female, male), horns, nose-shape |
| `Body/Eyes/` | — | eye-shape, pupil-color, pupil-shape, sclera-color |
| `Body/Hair/` | — | color, eyebrows, facial, female, length, male, misc-styles, texture |
| `Body/Genitalia/` | — | basic-type, breasts-prefix/size/type, nipple-type, penis-prefix/state/type, pussy-prefix/type |
| `States/` | 14 | age, clothing-removal, emoji, emotions (anger, happy, lust, sadness, surprise), gender, looking, nationality-race, size |
| `Concepts/` | 3 | gestures, occupations, postures-and-poses |

### Clothing & Fashion (6 dirs, 252 files)

| Directory | Files | What's inside |
|---|---|---|
| `clothings/` | 121 | baroque (female/male dress), edo period, victorian, medieval, rococo, tudor, regency, napoleonic, qing dynasty + cyberpunk/magical/nsfw/regular/scifi per body part |
| `Clothing/` | 37 | armor, bags, belt, bottomwear, corsets, costumes, dress, eyewear, footwear, headwear, jewelry-accessories, legwear, robes, suits, tattoos, topwear, underwear (bra, panty, swimwear, lingerie, piercings) |
| `Props/` | 11 | appliances, artifacts, desserts, drinks, flowers, food, instruments, sports, utensils, vehicles, weapons |
| `jewelry/` | 18 | age, brilliance, carat, clarities, cut, durability, facets, fire, hardness, luster, origin, rarity, setting, style, symbolism, treatments |
| `materials/` | 20 | bone, ceramic, cloth, crystal, fantasy, fictional, fossil, fur, glass, leather, metal, mineral, nano, plastic, resin, rock, sci-fi, synthetic, wood |
| `properties/` | 84 | colors, fabrics, patterns, materials, textures, shapes (2D/3D), size, structure, paint, visual/appearance, animal-print |

### Style & Art (6 dirs, 225 files)

| Directory | Files | What's inside |
|---|---|---|
| `styles/` | 163 | 101 art movements + 72 artist-name files by movement, camera settings (aperture, shutter-speed, iso, white-balance, focus, metering), rendering techniques, depiction styles, quality prompts, resolutions, punk-styles, creative-concepts |
| `Artists/` | 29 | themed (anime, digital, fineart, manga, painting, surreal, vectors) + e621 tag-based (blurry, chibi, chubby, dragon-feral, fluffy, hardlight, humanoid, etc.) |
| `styles-drawing/` | 16 | background, body-depiction, color, composition, expression, face-head-depiction, form, line-stroke, narrative, perspective, shading, style, texture, tools |
| `styles-architectural/` | 8 | african, asian, european, indigenous, islamic, pre-columbian, south-american |
| `Styling/` | 6 | aesthetics, composition, lighting, medium, quality-modifiers, viewpoint |
| `Vocab-and-Lists/` | 9 | adjective, anime, cartoons, game-consoles, games, movies, noun, preposition, verb |

### Magic, Fantasy & RPG (3 dirs, 561 files)

| Directory | Files | What's inside |
|---|---|---|
| `magical/` | 407 | academy (50+ room types: library, potions cellar, dueling chamber, divination parlor, etc. × 6 aspects each), magic types (air, blood, crystal, dark, dragon, fire, holy, ice, nature, necrotic, shadow, time, void, etc.), spell-types, profession-magic-use |
| `rpg/` | 127 | tiles (urban, dungeon, natural, terrain, structures), paths/crossings/roads, species, equipment (weapons melee/ranged/magic, armor, accessories), abilities (combat, spells), traps, secrets |
| `heraldry/` | 15 | badges, blazon, colors, ordinaries, subordinaries, charges (animals, objects, plants, celestial bodies, mythical beasts), supporters, mantling, helmets, crests |

### Nature & Environment (10 dirs, 297 files)

| Directory | Files | What's inside |
|---|---|---|
| `atmosphere/` | 74 | abstract, artistic, caves, celestial, cozy, cultural, dark, desert, dreamy, fantasy, magical, mystical, nature, oceanic, sci-fi, space, surreal + 57 more mood/atmosphere categories |
| `scenes/` | 39 | settings (landscapes, urban), cyberpunk scenes (AI uprising, noir detective, virtual reality), fantasy scenes, scifi scenes |
| `Background/` | 13 | ambience, buildings-and-rooms, country-city, disaster, environment, events, fantasy, heritage-sites, parks, planets-and-space, seasons, simple, weather |
| `constructions/` | 126 | types (cyberpunk/fictional/magical/regular/scifi), rooms, interior-design, materials, light-sources (indoor/outdoor) |
| `habitats/` | 41 | biomes, cave, civil, crater, fantasy, housing, magical, places, types, wonderland |
| `castle_exteriors/` | 14 | types, walls, towers, entrances, grounds, decorative-elements, defensive-features, fortifications, lighting |
| `plants/` | 13 | flower, fruit, growth-habit, inflorescence, leaf, root, seed, sepal, stem, foliage-arrangement |
| `mushrooms/` | 18 | annulus, bioluminescence, bruising, gill, growth-form, habitat, hymenium, latex, mycorrhizal-association, pileus, poisonous/medicinal properties, stipe, veil, volva |
| `weather/` | 4 | extreme, fog, precipitation, sky |
| `environment/` | 10 | fantasy, interior, nature, scifi, urban, water, cosmic, background, setting |

### Technology & Science (10 dirs, 197 files)

| Directory | Files | What's inside |
|---|---|---|
| `machines/` | 31 | types — agricultural, communication, complex, construction, energy, household, industrial, medical, military, mining, musical, navigation, optical, printing, robotics, scientific, textile, transportation, weapons |
| `components/` | 17 | bearings-bushings, control-automation, electrical-connectors, electronic, fasteners, hydraulic, pneumatic, springs, structural |
| `vehicles/` | 20 | types (airborne, cars, spacecraft, water, bicycles), accessories, customization, exterior-features, lights, windows, size |
| `audio/` | 34 | albumcover (background, design-elements, main-image, style, title-text), genre, melody, music, notation, notes, sound |
| `lighting/` | 27 | ambient, artificial, atmospheric, cinematic, colored, dramatic, fantasy, mood, natural, neon, period, practical, sci-fi, stage, studio, volumetric + 12 more |
| `subjects-school/` | 12 | art, biology, chemistry, economy, history, literature, math, music, physics, technology |
| `astronomy/` | 4 | celestial-bodies, spacecrafts, relations, celestial-anything |
| `chemistry/` | 3 | elements, gems, minerals |
| `phenomena/` | 9 | abstract, astronomy, cyberpunk, magical, math, natural, physics, psychology, sci-fi |
| `scifi/` | 18 | atmosphere, biopunk, computer, cyberpunk, nanotech, space, spacecrafts (antennae, engine, hull, markings, sensor, shape, size, type, window) |

### Words & Vocabulary (4 dirs, 70 files)

| Directory | Files | What's inside |
|---|---|---|
| `words/` | 26 | adjectives, verbs, substantives (magical/scifi/cyberpunk/regular), brain-psychology, constructors, vogonic-guide |
| `books/` | 12 | genres, fictional-types, book-sizes, bookbinding-styles, book-covers, typography, printing-techniques, illustration, places-book, book-accessories |
| `brain-psychology/` | 4 | terms, practices-fields, concepts-phenomena, neural-circuit-patterns |
| `matter/` | 3 | state, movement1, movement2 |

### Events & Holidays (8 dirs, 82 files)

| Directory | Files | What's inside |
|---|---|---|
| `christmas/` | 11 | artstyles, atmosphere, characters, christmas-carol, decorations, food, lightings, scapes, scenes, traditions |
| `halloween/` | 15 | artstyles, atmosphere, costumes, decorations, food-treats, grimaces, lighting, places-sceneries, pumpkin-carving (techniques, styles, expressions), symbols-icons, traditions |
| `easter/` | 10 | artstyles, atmosphere, characters, costumes, decorations, food, lightings, places, symbols, traditions |
| `valentine/` | 10 | artstyles, atmosphere, characters, decorations, food, lightings, scapes, scenes, symbols, traditions |
| `lunar-newyear/` | 10 | artstyles, atmosphere, characters, decorations, food, lightings, scapes, scenes, symbols, traditions |
| `st-patrick/` | 10 | artstyles, atmosphere, characters, costumes, decorations, food, lightings, places, symbols, traditions |
| `superheroes/` | 4 | dc, marvel, female, male |
| `supervillains/` | 4 | dc, marvel, female, male |

### Other (2 dirs, 10 files)

| Directory | Files | What's inside |
|---|---|---|
| `fruits/` | 6 | climate, flesh, seed-kinds, surface, surface-kind, aroma |
| `subtypes/` | 2 | cyberpunk, scifi |

### NSFW (3 dirs, 54 files)

| Directory | Files | What's inside |
|---|---|---|
| `NSFW/` | 26 | bondage-positions, fetish-gear, fetishes/ (13 subcats: age-play, animal-play, body-type, bondage, breasts, cum-play, exhibitionism, gender-play, group-sex, misc, mutilation, penetration, same-sex, smother, stimulation, watersports), nudity/ (exposed arms/breasts/chest/lower-torso/misc), POV, sex-positions, sex-toys |
| `NSFW/Fetishes/` | — | age-play, animal-play, body-type, bondage, breasts, cum-play, exhibitionism, gender-play, group-sex, misc, mutilation, penetration, same-sex, smother, stimulation, watersports |
| `NSFW/Nudity/` | — | exposed-arms, exposed-breasts, exposed-chest, exposed-lower-torso, misc |

### Flat wildcards (729 files)

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
    ├── 729 flat .txt files
    ├── action/               (4)
    ├── aesthetic/            (5)
    ├── Artists/              (29)  — themed + e621 artist names
    ├── astronomy/            (4)
    ├── atmosphere/           (74)  — mood/atmosphere words
    ├── audio/                (34)  — albumcover, genre, melody, music, notation
    ├── Background/           (13)  — environment, fantasy, seasons, space
    ├── Body/                 (37)  — type, hair, eyes, genitalia, face, ears
    ├── books/                (12)  — genres, bookbinding, typography
    ├── brain-psychology/     (4)
    ├── camera/               (12)
    ├── castle_exteriors/     (14)  — types, walls, towers, defenses
    ├── character/            (8)
    ├── characters/           (245) — beings, professions, classes, weapons
    ├── chemistry/            (3)
    ├── christmas/            (11)
    ├── clothings/            (121) — historical + genre per body part
    ├── Clothing/             (37)  — armor, dress, suits, underwear, swimwear
    ├── color/                (3)
    ├── Colors/               (17)  — per-color files + skin + palettes
    ├── components/           (17)  — bearings, fasteners, connectors
    ├── composition/          (2)
    ├── Concepts/             (3)   — gestures, occupations, poses
    ├── constructions/        (126) — buildings, rooms, interior design
    ├── creatures/            (43)  — descriptors, appendages, species
    ├── easter/               (10)
    ├── effect/               (3)
    ├── emotion/              (5)
    ├── environment/          (10)
    ├── fruits/               (6)
    ├── habitats/             (41)  — biomes, places, types
    ├── halloween/            (15)
    ├── heraldry/             (15)  — blazon, ordinaries, charges, crests
    ├── jewelry/              (18)  — cut, clarity, carat, gemstones, setting
    ├── lighting/             (27)
    ├── lunar-newyear/        (10)
    ├── machines/             (31)  — 20+ machine type categories
    ├── magical/              (407) — academy rooms, magic types, spells
    ├── material/             (4)
    ├── Materials/            (20)  — metal, cloth, crystal, nano, scifi
    ├── matter/               (3)
    ├── motion/               (4)
    ├── mushrooms/            (18)  — gills, veil, stipe, bioluminescence
    ├── NSFW/                 (26)  — bondage, fetishes, nudity, sex toys
    ├── person/               (34)  — poses, ages, body features, ethnicity
    ├── phenomena/            (9)
    ├── plants/               (13)  — flower, leaf, fruit, root, stem
    ├── Prompts/              (28)  — pre-made templates (boudoir, rpg, scifi)
    ├── properties/           (84)  — colors, fabrics, patterns, textures, shapes
    ├── Props/                (11)  — appliances, food, vehicles, weapons
    ├── quality/              (4)
    ├── rpg/                  (127) — tiles, equipment, abilities, spells
    ├── scenes/               (39)  — landscapes, cyberpunk, fantasy, scifi
    ├── scifi/                (18)
    ├── Species/              (63)  — pokemon, dragons, furries, composites
    ├── st-patrick/           (10)
    ├── States/               (14)  — emotions, age, gender, nationality
    ├── styles/               (163) — art movements, artists, camera, rendering
    ├── styles-architectural/ (8)
    ├── styles-drawing/       (16)  — line stroke, shading, perspective
    ├── Styling/              (6)   — composition, lighting, medium, viewpoint
    ├── subjects-school/      (12)
    ├── subtypes/             (2)
    ├── superheroes/          (4)
    ├── supervillains/        (4)
    ├── time/                 (5)
    ├── transition/           (3)
    ├── valentine/            (10)
    ├── vehicles/             (20)  — cars, spacecraft, airborne, water
    ├── Vocab-and-Lists/      (9)   — adjective, noun, verb, anime, games
    ├── weather/              (4)
    ├── words/                (26)  — adjectives, verbs, substantives by domain
    └── 2,315 subdirectory .txt files across 67 total categories
```

## Credits

Author: GKartist75 (with PI Agent)  
Built in collaboration with [PI Agent](https://github.com/earendil-works/pi-coding-agent).

## Requirements

Wan2GP only. No external dependencies.
