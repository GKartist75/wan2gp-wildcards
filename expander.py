"""Wildcard expansion engine for Wan2GP prompts.

Syntax:
- __name__       -> random line from wildcards/name.txt
- {opt1|opt2}    -> random inline choice
- 2::value       -> weighted option in .txt files (weight 2)
- __$var:file__  -> pick from file, store result as var
- __$var=value__ -> assign a literal value to var (no random pick)
- __$var__       -> reuse previously stored var value
- Nesting: files can reference other __wildcards__ and {options}
- Seed-deterministic via random.Random(seed)
"""

import os
import re
import random
import glob as globmod

WILDCARDS_DIR: str = ""  # set by plugin.py on init
DEPTH_LIMIT = 10

WILDCARD_RE = re.compile(r"__([a-zA-Z0-9_/.\-]+)__")
VARIANT_RE = re.compile(r"\{([^{}]*)\}")
CAPTURE_ANY_RE = re.compile(
    r"__\$([a-zA-Z0-9_]+):([a-zA-Z0-9_/.\\-]+)__"   # __$var:file__
    r"|__\$([a-zA-Z0-9_]+)\s*=\s*(.+?)__"           # __$var=value__
)
CAPTURE_GET_RE = re.compile(r"__\$([a-zA-Z0-9_]+)__")


# Wildcard name aliases (old flat names → new organized paths)
# Added by migration to preserve backward compatibility.
WILDCARD_ALIASES = {
    "3d-term": "misc/3d-terms",
    "3d-terms": "misc/3d-terms-alt",
    "actor": "people/actors",
    "actress": "people/actresses",
    "adj-architecture": "descriptive/adj-architecture",
    "adj-beauty": "descriptive/adj-beauty",
    "adj-general": "descriptive/adj-general",
    "adj-horror": "descriptive/adj-horror",
    "adjectives": "descriptive/adjectives",
    "adnd": "fantasy/adnd",
    "alien": "scifi/aliens",
    "angel": "fantasy/angels",
    "animal": "animals/general",
    "animals": "animals/list",
    "animals_categories": "animals/categories",
    "animals_types_aquatic_cambrian": "animals/aquatic/cambrian",
    "animals_types_aquatic_crustacean": "animals/aquatic/crustaceans",
    "animals_types_aquatic_fish": "animals/aquatic/fish",
    "animals_types_aquatic_invertebrate": "animals/aquatic/invertebrates",
    "animals_types_aquatic_whale": "animals/aquatic/whales",
    "animals_types_cat": "animals/cats/types",
    "animals_types_dog": "animals/dogs/types",
    "animals_types_insects": "animals/insects",
    "animals_types_large": "animals/large",
    "animals_types_medium": "animals/medium",
    "animals_types_reptile_and_amphibian": "animals/reptiles-amphibians",
    "animals_types_rodent": "animals/rodents",
    "appearance": "body/appearance",
    "artist": "art/artists",
    "artist-anime": "art/artists-anime",
    "artist-black-white": "art/artists-bw",
    "artist-botanical": "art/artists-botanical",
    "artist-c": "art/artists-c",
    "artist-cartoon": "art/artists-cartoon",
    "artist-concept": "art/artists-concept",
    "artist-csv": "art/artists-csv",
    "artist-dig1": "art/artists-digital-1",
    "artist-dig2": "art/artists-digital-2",
    "artist-dig3": "art/artists-digital-3",
    "artist-director": "art/artists-directors",
    "artist-fantasy": "art/artists-fantasy",
    "artist-fareast": "art/artists-far-east",
    "artist-fineart": "art/artists-fineart",
    "artist-horror": "art/artists-horror",
    "artist-n": "art/artists-n",
    "artist-nudity": "art/artists-nudity",
    "artist-photographer": "art/artists-photographers",
    "artist-scifi": "art/artists-scifi",
    "artist-scribbles": "art/artists-scribbles",
    "artist-special": "art/artists-special",
    "artist-surreal": "art/artists-surreal",
    "artist-ukioe": "art/artists-ukiyoe",
    "artist-weird": "art/artists-weird",
    "artmovement": "art/movements",
    "aspect-ratio": "camera/aspect-ratio",
    "ass_anatomy": "nsfw/ass/anatomy",
    "ass_and_hands": "nsfw/ass/with-hands",
    "ass_and_heads": "nsfw/ass/with-heads",
    "ass_anus_anatomy": "nsfw/ass/anus",
    "ass_misc": "nsfw/ass/misc",
    "ass_with_cum": "nsfw/ass/with-cum",
    "attire_headwear": "clothing/headwear",
    "attire_jewelry_and_accessories_head_and_face": "clothing/jewelry-head-face",
    "attire_jewelry_and_accessories_limbs": "clothing/jewelry-limbs",
    "attire_jewelry_and_accessories_neck_and_shoulders": "clothing/jewelry-neck",
    "attire_jewelry_and_accessories_torso_and_misc": "clothing/jewelry-torso",
    "attire_legs_and_feet": "clothing/legs-feet",
    "attire_other": "clothing/attire-other",
    "attire_pants_and_bottomwear": "clothing/pants-bottomwear",
    "attire_shirts_and_topwear": "clothing/shirts-topwear",
    "attire_shoes_and_footwear": "clothing/shoes-footwear",
    "attire_styles_and_patterns_patterns": "clothing/patterns",
    "attire_styles_and_patterns_prints": "clothing/prints",
    "attire_swimsuits_and_bodysuits": "clothing/swimsuits",
    "attire_traditional_clothing": "clothing/traditional",
    "attire_uniforms_and_costumes": "clothing/uniforms-costumes",
    "audio_genre": "misc/audio-genres",
    "audio_instruments_brass": "misc/instruments-brass",
    "audio_instruments_keyboard": "misc/instruments-keyboard",
    "audio_instruments_other": "misc/instruments-other",
    "audio_instruments_percussion": "misc/instruments-percussion",
    "audio_instruments_strings": "misc/instruments-strings",
    "audio_instruments_woodwinds": "misc/instruments-woodwinds",
    "audio_misc": "misc/audio-misc",
    "audio_places": "misc/audio-places",
    "audio_playback_media": "misc/audio-media",
    "audio_playback_other": "misc/audio-playback-other",
    "audio_playback_players": "misc/audio-players",
    "audio_playback_speakers_and_headphones": "misc/audio-speakers",
    "audio_professions": "misc/audio-professions",
    "background": "color/background",
    "background-color": "color/background",
    "backgrounds_colors": "color/background-colors",
    "backgrounds_multiple_colors": "color/background-multi",
    "backgrounds_other": "color/background-other",
    "backgrounds_patterns": "color/background-patterns",
    "bangs": "body/hair/bangs",
    "beards": "body/hair/beards",
    "belt": "clothing/belt",
    "biome": "environment/biomes",
    "bird": "animals/birds/general",
    "birds_main": "animals/birds/main",
    "birds_mythological": "animals/birds/mythological",
    "birds_real": "animals/birds/real",
    "blonde": "body/hair/blonde",
    "board_games_main": "misc/board-games",
    "board_games_pieces": "misc/board-game-pieces",
    "body-fit": "body/fit",
    "body-framing": "body/framing",
    "body-heavy": "body/heavy",
    "body-light": "body/light",
    "body-poor": "body/poor",
    "body-shape": "body/shape",
    "body-shape2": "body/shape-alt",
    "body-short": "body/short",
    "body-tall": "body/tall",
    "body_parts_appendages": "body/appendages",
    "body_parts_head": "body/head-parts",
    "body_parts_torso_lower": "body/torso-lower",
    "body_parts_torso_upper": "body/torso-upper",
    "bodyshape": "body/shape-generic",
    "braid": "body/hair/braids",
    "breasts_and_other_body_parts_docking": "nsfw/breasts/docking",
    "breasts_and_other_body_parts_hands": "nsfw/breasts/with-hands",
    "breasts_and_other_body_parts_head": "nsfw/breasts/with-head",
    "breasts_and_other_body_parts_mouth": "nsfw/breasts/with-mouth",
    "breasts_and_other_body_parts_penis": "nsfw/breasts/with-penis",
    "breasts_and_other_body_parts_toys": "nsfw/breasts/with-toys",
    "breasts_clothes_for": "nsfw/breasts/clothes",
    "breasts_descriptions": "nsfw/breasts/descriptions",
    "breasts_main": "nsfw/breasts/main",
    "breasts_misc": "nsfw/breasts/misc",
    "breasts_sizes_ranges": "nsfw/breasts/sizes",
    "breasts_sizes_scenes_revolving_around": "nsfw/breasts/size-scenes",
    "breasts_visibilty_parts": "nsfw/breasts/visibility-parts",
    "breasts_visibilty_whole": "nsfw/breasts/visibility-whole",
    "camera": "camera/models",
    "camera-manu": "camera/manufacturers",
    "cat": "animals/cats/general",
    "cats_behavior": "animals/cats/behavior",
    "cats_breeds": "animals/cats/breeds",
    "cats_coat": "animals/cats/coats",
    "cats_felines": "animals/cats/felines",
    "cats_main": "animals/cats/main",
    "cats_misc": "animals/cats/misc",
    "cats_places": "animals/cats/places",
    "cats_related": "animals/cats/related",
    "celeb": "people/celebrities",
    "choker": "clothing/choker",
    "civilization": "people/civilizations",
    "class": "people/classes",
    "clothing": "clothing/general",
    "clothing-female": "clothing/female",
    "clothing-male": "clothing/male",
    "color": "color/named",
    "color-palette": "color/palette-named",
    "colors_collections": "color/collections",
    "colors_dominant_palettes": "color/dominant-palettes",
    "colors_dominant_specific": "color/dominant-specific",
    "colors_misc": "color/misc",
    "colours": "color/colours",
    "cosmic-galaxy": "environment/space-galaxies",
    "cosmic-nebula": "environment/space-nebulae",
    "cosmic-star": "environment/space-stars",
    "cosmic-term": "environment/space-terms",
    "cosmic-terms": "environment/space-terms-alt",
    "cthulhu": "fantasy/cthulhu",
    "decade": "time/decades",
    "deity": "fantasy/deities",
    "detail": "descriptive/detail",
    "details": "descriptive/details",
    "digitalart": "art/digital",
    "dinosaur": "animals/dinosaurs",
    "dog": "animals/dogs/general",
    "dog_breeds": "animals/dogs/breeds",
    "dog_canines": "animals/dogs/canines",
    "dog_misc": "animals/dogs/misc",
    "dog_related": "animals/dogs/related",
    "dogs_main": "animals/dogs/main",
    "drawing": "art/drawing",
    "dress": "clothing/dress",
    "dress_appearance_colors": "clothing/dress-colors",
    "dress_appearance_models": "clothing/dress-models",
    "dress_appearance_multiple_colors": "clothing/dress-multi-colors",
    "dress_appearance_other": "clothing/dress-other",
    "dress_appearance_patterns_and_prints": "clothing/dress-patterns",
    "dress_misc": "clothing/dress-misc",
    "earrings": "clothing/earrings",
    "ears_animal": "body/ears/animal",
    "ears_misc": "body/ears/misc",
    "ears_number": "body/ears/number",
    "ears_objects": "body/ears/objects",
    "ears_other": "body/ears/other",
    "emoji": "misc/emoji",
    "emoji-combo": "misc/emoji-combos",
    "expression": "body/face/expression",
    "eye-color": "body/eyes/colors",
    "eyecolor": "body/eyes/colors-alt",
    "eyeliner": "body/eyes/eyeliner",
    "eyes_accessories": "body/eyes/accessories",
    "eyes_around": "body/eyes/around",
    "eyes_closed": "body/eyes/closed",
    "eyes_emotions_and_expressions": "body/eyes/emotions",
    "eyes_gazes": "body/eyes/gazes",
    "eyes_iris_colors": "body/eyes/iris-colors",
    "eyes_iris_form": "body/eyes/iris-form",
    "eyes_iris_multiple_colors": "body/eyes/iris-multi",
    "eyes_misc": "body/eyes/misc",
    "eyes_more_appearance_animal": "body/eyes/animal",
    "eyes_more_appearance_other": "body/eyes/appearance-other",
    "eyes_more_appearance_series_specific": "body/eyes/series-specific",
    "eyes_more_appearance_stylistic": "body/eyes/stylistic",
    "eyes_number": "body/eyes/number",
    "eyes_pupils": "body/eyes/pupils",
    "eyes_sclera": "body/eyes/sclera",
    "eyewear_eyewear_frame_colors": "clothing/eyewear-frame-colors",
    "eyewear_eyewear_lens_colors": "clothing/eyewear-lens-colors",
    "eyewear_eyewear_misc": "clothing/eyewear-misc",
    "eyewear_eyewear_types": "clothing/eyewear-types",
    "eyewear_glasses_misc": "clothing/glasses-misc",
    "eyewear_glasses_types": "clothing/glasses-types",
    "eyewear_main": "clothing/eyewear",
    "eyewear_sunglasses": "clothing/sunglasses",
    "f-stop": "camera/f-stop",
    "face_drawing_styles": "body/face/drawing-styles",
    "face_emotes": "body/face/emotes",
    "face_emotions": "body/face/emotions",
    "face_looking_at": "body/face/looking-at",
    "face_main": "body/face/main",
    "face_misc": "body/face/misc",
    "face_sexual": "body/face/sexual",
    "face_smile": "body/face/smile",
    "face_smile_main": "body/face/smile-main",
    "face_smug": "body/face/smug",
    "face_smug_main": "body/face/smug-main",
    "face_surprised_scared_sad": "body/face/surprised-scared-sad",
    "face_surprised_scared_sad_main": "body/face/surprised-scared-sad-main",
    "fantasy": "fantasy/general",
    "fantasy-creature": "creatures/fantasy",
    "fantasy-setting": "fantasy/settings",
    "female-adult": "people/female-adult",
    "female-young": "people/female-young",
    "film-genre": "misc/film-genres",
    "fish": "animals/aquatic/fish-list",
    "flower": "plants/flower",
    "flowers_main": "plants/flowers-main",
    "flowers_misc": "plants/flowers-misc",
    "flowers_species": "plants/flowers-species",
    "focal-length": "camera/focal-length",
    "food": "food/general",
    "food_actions": "food/actions",
    "food_breads": "food/breads",
    "food_condiments": "food/condiments",
    "food_dairy": "food/dairy",
    "food_drink_containers": "food/drink-containers",
    "food_drink_main": "food/drinks",
    "food_fruit": "food/fruits",
    "food_main": "food/main",
    "food_meal": "food/meals",
    "food_meat": "food/meat",
    "food_misc": "food/misc",
    "food_professions_and_establishments": "food/professions",
    "food_sexual": "food/sexual",
    "food_snacks": "food/snacks",
    "food_sweets": "food/sweets",
    "food_sweets_main": "food/sweets-main",
    "food_utensils": "food/utensils",
    "food_vegetable": "food/vegetables",
    "foods": "food/foods",
    "forest-type": "environment/forest-types",
    "fruit": "food/fruit",
    "furniture": "misc/furniture",
    "game": "misc/games",
    "game_activities_board": "misc/game-board",
    "game_activities_card": "misc/game-card",
    "game_activities_group": "misc/game-group",
    "game_activities_hand": "misc/game-hand",
    "game_activities_mechanical": "misc/game-mechanical",
    "game_activities_places": "misc/game-places",
    "game_activities_puzzle": "misc/game-puzzle",
    "games": "misc/games-alt",
    "gender": "people/gender",
    "gender-ext": "people/gender-extended",
    "generalstyle": "art/styles-general",
    "genre": "misc/genres",
    "gestures_one_hand_one_open_finger": "body/gestures/one-finger",
    "gestures_one_hand_three_open_fingers": "body/gestures/three-fingers",
    "gestures_one_hand_two_open_fingers": "body/gestures/two-fingers",
    "gestures_one_hand_variable_number_of_open_fingers": "body/gestures/variable-fingers",
    "gestures_one_hand_whole_closed_hand": "body/gestures/closed-hand",
    "gestures_one_hand_whole_open_hand": "body/gestures/open-hand",
    "gestures_other": "body/gestures/other",
    "gestures_two_hands": "body/gestures/two-hands",
    "hair": "body/hair/main",
    "hair-color": "body/hair/colors",
    "hair-female": "body/hair/female",
    "hair-female-short": "body/hair/female-short",
    "hair-length": "body/hair/length",
    "hair-male": "body/hair/male",
    "hair_actions": "body/hair/actions",
    "hair_color": "body/hair/colors-alt",
    "hair_color_misc": "body/hair/colors-misc",
    "hair_color_multiple": "body/hair/colors-multi",
    "hair_facial": "body/hair/facial",
    "hair_fantasy": "body/hair/fantasy",
    "hair_misc": "body/hair/misc",
    "hair_objects_accessories": "body/hair/accessories",
    "hair_objects_care": "body/hair/care",
    "hair_styles_back": "body/hair/styles-back",
    "hair_styles_front": "body/hair/styles-front",
    "hair_styles_length": "body/hair/styles-length",
    "hair_styles_long": "body/hair/styles-long",
    "hair_styles_medium": "body/hair/styles-medium",
    "hair_styles_misc": "body/hair/styles-misc",
    "hair_styles_over_the_body": "body/hair/styles-over-body",
    "hair_styles_short": "body/hair/styles-short",
    "hair_styles_tall": "body/hair/styles-tall",
    "hair_styles_texture": "body/hair/styles-texture",
    "hair_styles_tied": "body/hair/styles-tied",
    "hair_styles_top": "body/hair/styles-top",
    "hands_strange": "body/hands/strange",
    "hands_where_above_neck": "body/hands/above-neck",
    "hands_where_breasts": "body/hands/on-breasts",
    "hands_where_lower_body": "body/hands/lower-body",
    "hands_where_members": "body/hands/on-members",
    "hands_where_somewhere_else": "body/hands/somewhere-else",
    "hands_where_upper_body": "body/hands/upper-body",
    "hd": "misc/hd",
    "headwear-female": "clothing/headwear-female",
    "headwear-male": "clothing/headwear-male",
    "headwear_accessories": "clothing/headwear-accessories",
    "headwear_actions": "clothing/headwear-actions",
    "headwear_colors": "clothing/headwear-colors",
    "headwear_crowns": "clothing/crowns",
    "headwear_hats_brimless": "clothing/hats-brimless",
    "headwear_hats_misc": "clothing/hats-misc",
    "headwear_hats_with_brim": "clothing/hats-with-brim",
    "headwear_hats_with_ear_flaps": "clothing/hats-earflaps",
    "headwear_hats_with_visor": "clothing/hats-visor",
    "headwear_helmets": "clothing/helmets",
    "headwear_non_specific_styles": "clothing/headwear-styles",
    "headwear_not_headwear": "clothing/headwear-not",
    "headwear_other": "clothing/headwear-other",
    "headwear_types": "clothing/headwear-types",
    "high-heels": "clothing/high-heels",
    "home": "environment/home",
    "identity": "people/identity",
    "identity-adult": "people/identity-adult",
    "identity-young": "people/identity-young",
    "image_composition_angle_perspective_depth": "descriptive/composition-angle",
    "image_composition_composition": "descriptive/composition",
    "image_composition_flaws": "descriptive/composition-flaws",
    "image_composition_focus": "descriptive/composition-focus",
    "image_composition_format": "descriptive/composition-format",
    "image_composition_framing_body": "descriptive/composition-framing",
    "image_composition_other_patterns": "descriptive/composition-other",
    "image_composition_styles": "descriptive/composition-styles",
    "image_composition_subject_matter": "descriptive/composition-subject",
    "image_composition_techniques": "descriptive/composition-techniques",
    "image_composition_traditional_japanese_patterns": "descriptive/japanese-patterns",
    "interior": "environment/interiors",
    "iso-stop": "camera/iso",
    "jobs": "people/jobs",
    "landscape": "environment/landscape",
    "landscape-type": "environment/landscape-types",
    "legwear": "clothing/legwear",
    "legwear_action": "clothing/legwear-actions",
    "legwear_bands": "clothing/legwear-bands",
    "legwear_colors": "clothing/legwear-colors",
    "legwear_main": "clothing/legwear-main",
    "legwear_misc": "clothing/legwear-misc",
    "legwear_multiple_colors": "clothing/legwear-multi-colors",
    "legwear_pattern": "clothing/legwear-patterns",
    "legwear_style": "clothing/legwear-styles",
    "location": "environment/locations",
    "makeup": "body/face/makeup",
    "male-adult": "people/male-adult",
    "male-young": "people/male-young",
    "monster": "creatures/monsters",
    "mood": "descriptive/moods",
    "movement": "poses/movement-general",
    "name-female": "people/names-female",
    "name-male": "people/names-male",
    "national-park": "environment/national-parks",
    "nationality": "people/nationalities",
    "natl-park": "environment/national-parks-alt",
    "neck_and_neckwear_actions": "clothing/neckwear-actions",
    "neck_and_neckwear_anatomy": "clothing/neck-anatomy",
    "neck_and_neckwear_attire_accessories_objects": "clothing/neckwear-accessories",
    "neck_and_neckwear_collar": "clothing/collars",
    "neck_and_neckwear_styles_colors": "clothing/neckwear-colors",
    "neck_and_neckwear_styles_patterns": "clothing/neckwear-patterns",
    "neckwear": "clothing/neckwear-main",
    "neg-weight": "misc/negative-weights",
    "noun-beauty": "descriptive/noun-beauty",
    "noun-emote": "descriptive/noun-emotion",
    "noun-fantasy": "descriptive/noun-fantasy",
    "noun-general": "descriptive/noun-general",
    "noun-horror": "descriptive/noun-horror",
    "noun-landscape": "descriptive/noun-landscape",
    "noun-romance": "descriptive/noun-romance",
    "noun-scifi": "descriptive/noun-scifi",
    "nsfw-bdsm": "nsfw/bdsm",
    "nsfw-bdsm-type": "nsfw/bdsm-types",
    "nsfw-bra": "nsfw/bra",
    "nsfw-breastsize": "nsfw/breast-sizes",
    "nsfw-clothing-state": "nsfw/clothing-state",
    "nsfw-corset": "nsfw/corset",
    "nsfw-cumplay": "nsfw/cum-play",
    "nsfw-expression": "nsfw/expressions",
    "nsfw-fetish": "nsfw/fetish",
    "nsfw-gag": "nsfw/gag",
    "nsfw-lingerie": "nsfw/lingerie",
    "nsfw-lingerie-state": "nsfw/lingerie-state",
    "nsfw-panties": "nsfw/panties",
    "nsfw-position": "nsfw/positions",
    "nsfw-publicity": "nsfw/publicity",
    "nsfw-sex-act": "nsfw/sex-acts",
    "nsfw-sex-position": "nsfw/sex-positions",
    "nsfw-sex-toy": "nsfw/sex-toys",
    "nsfw-subreddit": "nsfw/subreddits",
    "nudity_by_gender": "nsfw/nudity/by-gender",
    "nudity_complete": "nsfw/nudity/complete",
    "nudity_dressing_covering_body_parts": "nsfw/nudity/dressing",
    "nudity_misc": "nsfw/nudity/misc",
    "nudity_naughty_points_of_view": "nsfw/nudity/naughty-pov",
    "nudity_partial_any_clothes": "nsfw/nudity/partial-any",
    "nudity_partial_exposed_breasts": "nsfw/nudity/partial-breasts",
    "nudity_partial_exposed_breasts_parts_of": "nsfw/nudity/partial-breast-parts",
    "nudity_partial_exposed_chest": "nsfw/nudity/partial-chest",
    "nudity_partial_exposed_head_or_neck": "nsfw/nudity/partial-head-neck",
    "nudity_partial_exposed_nipples": "nsfw/nudity/partial-nipples",
    "nudity_partial_exposed_shoulders_and_arms": "nsfw/nudity/partial-shoulders-arms",
    "nudity_partial_exposed_torso": "nsfw/nudity/partial-torso",
    "nudity_partial_focus_on_exposed_ass_or_crotch": "nsfw/nudity/partial-ass-crotch",
    "nudity_partial_focus_on_exposed_legs_or_feet": "nsfw/nudity/partial-legs-feet",
    "nudity_partial_misc": "nsfw/nudity/partial-misc",
    "nudity_partial_specific_clothes_or_ornaments_being_worn_as_exceptions": "nsfw/nudity/partial-exceptions",
    "nudity_touching_clothes": "nsfw/nudity/touching-clothes",
    "occupation": "people/occupations",
    "occupations": "people/occupations-alt",
    "oil-painting": "art/oil-painting",
    "othermedia": "art/other-media",
    "painting": "art/painting",
    "panties_and_body_parts_breasts": "nsfw/panties/with-breasts",
    "panties_and_body_parts_hands": "nsfw/panties/with-hands",
    "panties_and_body_parts_head": "nsfw/panties/with-head",
    "panties_and_body_parts_legs": "nsfw/panties/with-legs",
    "panties_and_body_parts_misc": "nsfw/panties/with-misc",
    "panties_and_body_parts_penis": "nsfw/panties/with-penis",
    "panties_and_fluids": "nsfw/panties/fluids",
    "panties_and_objects": "nsfw/panties/objects",
    "panties_appearance_additional": "nsfw/panties/appearance-additional",
    "panties_appearance_colors": "nsfw/panties/colors",
    "panties_appearance_incomplete": "nsfw/panties/incomplete",
    "panties_appearance_lowleg_highleg": "nsfw/panties/lowleg-highleg",
    "panties_appearance_materials": "nsfw/panties/materials",
    "panties_appearance_multiple_colors": "nsfw/panties/multi-colors",
    "panties_appearance_patterns_and_prints": "nsfw/panties/patterns",
    "panties_appearance_sizes": "nsfw/panties/sizes",
    "panties_main": "nsfw/panties/main",
    "panties_number": "nsfw/panties/number",
    "panties_with_other_clothes": "nsfw/panties/with-clothes",
    "photo-term": "camera/terms",
    "photoshoot-type": "camera/shoot-types",
    "piercings_general_locations_body": "body/piercings/body",
    "piercings_general_locations_head_and_facial": "body/piercings/head",
    "piercings_genital_female": "body/piercings/genital-female",
    "piercings_genital_male": "body/piercings/genital-male",
    "piercings_main": "body/piercings/main",
    "piercings_misc": "body/piercings/misc",
    "planet": "environment/planets",
    "plant_actions": "plants/actions",
    "plant_locations": "plants/locations",
    "plant_misc": "plants/misc",
    "plant_parts": "plants/parts",
    "plant_types": "plants/types",
    "platform": "misc/platforms",
    "pop-culture": "misc/pop-culture",
    "pop-location": "misc/pop-locations",
    "portrait-type": "camera/portrait-types",
    "pose": "poses/general",
    "posture_arms_basic": "poses/arms-basic",
    "posture_arms_specific": "poses/arms-specific",
    "posture_basic": "poses/basic",
    "posture_carrying": "poses/carrying",
    "posture_foot_position": "poses/foot-position",
    "posture_hand_position": "poses/hand-position",
    "posture_hands_touching_each_other": "poses/hands-touching",
    "posture_head": "poses/head",
    "posture_hips": "poses/hips",
    "posture_hugging_main": "poses/hugging",
    "posture_hugging_one_character": "poses/hugging-one",
    "posture_hugging_two_characters": "poses/hugging-two",
    "posture_knee_location": "poses/knee-location",
    "posture_leg_location": "poses/leg-location",
    "posture_movement_of_the_body": "poses/movement",
    "posture_other_whole_body": "poses/whole-body",
    "posture_poses": "poses/poses",
    "posture_rest_points": "poses/rest-points",
    "posture_three_characters": "poses/three-characters",
    "posture_torso": "poses/torso",
    "posture_two_characters": "poses/two-characters",
    "prints_patterns": "clothing/prints-patterns",
    "prints_patterns_specific": "clothing/prints-specific",
    "prints_patterns_things": "clothing/prints-things",
    "prints_print_items": "clothing/prints-items",
    "public": "environment/public-spaces",
    "purse": "clothing/purse",
    "pussy_adornments": "nsfw/pussy/adornments",
    "pussy_anatomy": "nsfw/pussy/anatomy",
    "pussy_attire": "nsfw/pussy/attire",
    "pussy_fluids": "nsfw/pussy/fluids",
    "pussy_hands_on": "nsfw/pussy/hands-on",
    "pussy_sexual_objects_and_acts": "nsfw/pussy/objects-and-acts",
    "pussy_under_clothes": "nsfw/pussy/under-clothes",
    "pussy_visible_parts": "nsfw/pussy/visible-parts",
    "quantity": "descriptive/quantity",
    "race": "people/races",
    "render": "art/render",
    "render-engine": "art/render-engines",
    "robot": "scifi/robots",
    "rpg-item": "fantasy/rpg-items",
    "scenario": "environment/scenarios",
    "scenario-desc": "environment/scenario-descriptions",
    "scenario-fantasy": "environment/scenario-fantasy",
    "scenario-romance": "environment/scenario-romance",
    "scenario-scifi": "environment/scenario-scifi",
    "scenario2": "environment/scenarios-alt",
    "scifi": "scifi/general",
    "sculptural": "art/sculptural",
    "sculpture": "art/sculpture",
    "seasons": "time/seasons",
    "setting": "environment/settings",
    "sex_acts_before": "nsfw/sex-acts/before",
    "sex_acts_fetishes_ageplay": "nsfw/fetishes/age-play",
    "sex_acts_fetishes_animal_play": "nsfw/fetishes/animal-play",
    "sex_acts_fetishes_body_types": "nsfw/fetishes/body-types",
    "sex_acts_fetishes_bondage": "nsfw/fetishes/bondage",
    "sex_acts_fetishes_breasts": "nsfw/fetishes/breasts",
    "sex_acts_fetishes_cum_play": "nsfw/fetishes/cum-play",
    "sex_acts_fetishes_exhibitionism": "nsfw/fetishes/exhibitionism",
    "sex_acts_fetishes_extreme_mutilation": "nsfw/fetishes/mutilation",
    "sex_acts_fetishes_extreme_scat_and_urination": "nsfw/fetishes/scat",
    "sex_acts_fetishes_facial_expressions": "nsfw/fetishes/facial-expressions",
    "sex_acts_fetishes_gender_play": "nsfw/fetishes/gender-play",
    "sex_acts_fetishes_incest": "nsfw/fetishes/incest",
    "sex_acts_fetishes_misc": "nsfw/fetishes/misc",
    "sex_acts_fetishes_rape": "nsfw/fetishes/rape",
    "sex_acts_fetishes_smother": "nsfw/fetishes/smother",
    "sex_acts_fetishes_views": "nsfw/fetishes/views",
    "sex_acts_group_sex": "nsfw/sex-acts/group",
    "sex_acts_penetration_and_insertion": "nsfw/sex-acts/penetration",
    "sex_acts_same_sex": "nsfw/sex-acts/same-sex",
    "sex_acts_stimulation": "nsfw/sex-acts/stimulation",
    "sex_objects_bdsm": "nsfw/objects/bdsm",
    "sex_objects_fluids": "nsfw/objects/fluids",
    "sex_objects_sex_toys": "nsfw/objects/sex-toys",
    "sexual_positions_bondage": "nsfw/positions/bondage",
    "sexual_positions_main": "nsfw/positions/main",
    "shading-techniques": "art/shading",
    "ship": "scifi/ships",
    "shoulders_anatomy": "body/shoulders/anatomy",
    "shoulders_attire_clothing_desgined_to_leave_shoulders_asymmetrical_necklines": "body/shoulders/asymmetrical",
    "shoulders_attire_clothing_desgined_to_leave_shoulders_bare_low_and_wide_cut_necklines": "body/shoulders/low-neckline",
    "shoulders_attire_clothing_desgined_to_leave_shoulders_bare_sleeveless": "body/shoulders/sleeveless",
    "shoulders_attire_clothing_desgined_to_leave_shoulders_bare_strapless": "body/shoulders/strapless",
    "shoulders_attire_exposed": "body/shoulders/exposed",
    "shoulders_attire_for": "body/shoulders/attire",
    "shoulders_attire_other": "body/shoulders/attire-other",
    "shoulders_with_somethinge_else_animals": "body/shoulders/with-animals",
    "shoulders_with_somethinge_else_hands": "body/shoulders/with-hands",
    "shoulders_with_somethinge_else_misc": "body/shoulders/with-misc",
    "shoulders_with_somethinge_else_objects": "body/shoulders/with-objects",
    "shoulders_with_somethinge_else_touching": "body/shoulders/touching",
    "site": "environment/sites",
    "size": "descriptive/sizes",
    "skin-color": "color/skin",
    "skin_color_abnormal": "color/skin-abnormal",
    "skin_color_misc": "color/skin-misc",
    "skin_color_normal": "color/skin-normal",
    "sleeves_actions": "clothing/sleeves-actions",
    "sleeves_colors": "clothing/sleeves-colors",
    "sleeves_lack_thereof": "clothing/sleeveless",
    "sleeves_lenght": "clothing/sleeves-length",
    "sleeves_misc": "clothing/sleeves-misc",
    "sleeves_prints": "clothing/sleeves-prints",
    "sleeves_styled": "clothing/sleeves-styled",
    "sleeves_styles": "clothing/sleeves-styles",
    "sleeves_trims": "clothing/sleeves-trims",
    "still-life": "art/still-life",
    "style": "art/styles",
    "suit-female": "clothing/suits-female",
    "suit-male": "clothing/suits-male",
    "superhero": "fantasy/superheroes",
    "supermodel": "people/supermodels",
    "swimsuit_colors": "clothing/swimwear-colors",
    "swimsuit_male": "clothing/swimwear-male",
    "swimsuit_misc": "clothing/swimwear-misc",
    "swimsuit_styles": "clothing/swimwear-styles",
    "swimsuit_types": "clothing/swimwear-types",
    "swimwear": "clothing/swimwear-main",
    "technique": "art/techniques",
    "technology_armor_futuristic": "scifi/armor-futuristic",
    "technology_armor_modern": "scifi/armor-modern",
    "technology_artificial_life": "scifi/artificial-life",
    "technology_computers": "scifi/computers",
    "technology_costumes": "scifi/costumes",
    "technology_descriptions": "scifi/descriptions",
    "technology_holograms": "scifi/holograms",
    "technology_jobs": "scifi/jobs",
    "technology_mecha": "scifi/mecha",
    "technology_medical": "scifi/medical",
    "technology_parts_electronic": "scifi/parts-electronic",
    "technology_parts_main": "scifi/parts",
    "technology_parts_mechanical": "scifi/parts-mechanical",
    "technology_personal_communication": "scifi/communication",
    "technology_places": "scifi/places",
    "technology_prosthetics": "scifi/prosthetics",
    "technology_radio": "scifi/radio",
    "technology_robots": "scifi/robots-list",
    "technology_scientific": "scifi/scientific",
    "technology_space": "scifi/space",
    "technology_themes": "scifi/themes",
    "technology_tools": "scifi/tools",
    "technology_vehicles_aerospace": "scifi/vehicles-aerospace",
    "technology_vehicles_land": "scifi/vehicles-land",
    "technology_vehicles_naval": "scifi/vehicles-naval",
    "technology_vehicles_power_sources": "scifi/power-sources",
    "textile": "clothing/textiles",
    "time": "time/general",
    "timeofday": "time/time-of-day",
    "tolkien": "fantasy/tolkien",
    "train": "scifi/trains",
    "tree": "plants/trees",
    "tree_action": "plants/tree-actions",
    "tree_habitats": "plants/tree-habitats",
    "tree_misc": "plants/tree-misc",
    "tree_parts": "plants/tree-parts",
    "tree_types": "plants/tree-types",
    "tribe": "people/tribes",
    "underwater": "environment/underwater",
    "water": "environment/water-main",
    "water_clothes": "environment/water-clothes",
    "water_geography_bodies": "environment/water-bodies",
    "water_geography_landforms": "environment/water-landforms",
    "water_ice": "environment/ice",
    "water_main": "environment/water-main",
    "water_meteorology": "environment/weather-water",
    "water_misc": "environment/water-misc",
    "water_steam": "environment/steam",
    "water_vehicles": "environment/water-vehicles",
    "water_wet": "environment/wet",
    "watercolor": "art/watercolor",
    "wh-site": "environment/world-heritage-sites",
    "bra_colors": "clothing/bra-colors",
    "bra_main": "clothing/bra",
    "bra_misc": "clothing/bra-misc",
    "bra_models": "clothing/bra-models",
    "bra_multiple_colors": "clothing/bra-multi-colors",
    "bra_patterns_and_prints": "clothing/bra-patterns",
    "costume-female": "clothing/costumes-female",
    "costume-male": "clothing/costumes-male",
    "fire_actions": "effect/fire-actions",
    "fire_body_parts": "effect/fire-body-parts",
    "fire_colors": "effect/fire-colors",
    "fire_forms": "effect/fire-forms",
    "fire_main": "effect/fire",
    "fire_misc": "effect/fire-misc",
    "fire_objects": "effect/fire-objects",
    "focus_body_parts": "descriptive/focus-body-parts",
    "focus_gender": "descriptive/focus-gender",
    "focus_objects": "descriptive/focus-objects",
    "focus_other": "descriptive/focus-other",
    "gem": "material/gems",
    "gen-modifier": "descriptive/gen-modifiers",
    "general_aesthetics": "descriptive/aesthetics",
    "angle": "camera/angle-shot",
    "groups_animals": "descriptive/groups-animals",
    "groups_by_gender_boys": "descriptive/groups-boys",
    "groups_by_gender_girls": "descriptive/groups-girls",
    "groups_by_gender_other": "descriptive/groups-other",
    "groups_everyone": "descriptive/groups-everyone",
    "groups_main": "descriptive/groups",
    "hair-accessory": "body/hair/hair-accessory",
    "haircolour": "body/hair/haircolour",
    "horror": "descriptive/horror",
    "injury_coverings": "body/injury-coverings",
    "injury_misc": "body/injury-misc",
    "injury_visible": "body/injury-visible",
    "lighting": "lighting/general",
    "lipstick-shade": "body/face/lipstick-shades",
    "lipstick": "body/face/lipstick",
    "punk": "aesthetic/punk",
    "sports_equpment": "misc/sports-equipment",
    "sports_list": "misc/sports-list",
    "sports_main": "misc/sports",
    "subject": "descriptive/subjects",
    "subject-fantasy": "descriptive/subject-fantasy",
    "subject-horror": "descriptive/subject-horror",
    "subject-romance": "descriptive/subject-romance",
    "subject-scifi": "descriptive/subject-scifi",
    "tail_and_objects": "body/tail/objects",
    "tail_and_sex": "body/tail/sexual",
    "tail_main": "body/tail/main",
    "tail_misc": "body/tail/misc",
    "tail_number": "body/tail/number",
    "tail_types_elemental": "body/tail/types-elemental",
    "tail_types_mammals": "body/tail/types-mammals",
    "tail_types_other_animals": "body/tail/types-other",
    "tail_types_supernatural": "body/tail/types-supernatural",
    "trippy": "aesthetic/trippy",
    "verbs_and_gerunds_ambiguous": "descriptive/verbs-ambiguous",
    "verbs_and_gerunds_gerunds": "descriptive/gerunds",
    "verbs_and_gerunds_verbs": "descriptive/verbs",
    "wave": "environment/waves",
    "wings_colors": "body/wings/colors",
    "wings_main": "body/wings/main",
    "wings_misc": "body/wings/misc",
    "wings_number": "body/wings/number",
    "wings_sizes": "body/wings/sizes",
    "wings_types_elemental": "body/wings/types-elemental",
    "wings_types_false": "body/wings/types-false",
    "wings_types_insects": "body/wings/types-insects",
    "wings_types_other": "body/wings/types-other",
    "wings_types_supernatural": "body/wings/types-supernatural",
    "wings_where_attached": "body/wings/attachment",
}




def set_wildcards_dir(path: str) -> None:
    global WILDCARDS_DIR
    WILDCARDS_DIR = path
    os.makedirs(path, exist_ok=True)


def resolve_wildcard_files(name: str) -> list[str]:
    """Find .txt files matching wildcard name in WILDCARDS_DIR.

    Supports three forms:
      __camera_shot__  (underscore -> slash fallback)
      __camera/shot__  (direct path)
      __camera__       (directory pool)
    Also checks WILDCARD_ALIASES for renamed/moved files (backward compat).
    """
    base = name.replace("\\", "/").lstrip("/")
    paths = []

    def _try_resolve(b: str) -> list[str]:
        result: list[str] = []
        # direct match: wildcards/name.txt
        direct = os.path.join(WILDCARDS_DIR, b + ".txt")
        if os.path.isfile(direct):
            result.append(direct)
        # directory match: wildcards/name/*.txt
        dirpath = os.path.join(WILDCARDS_DIR, b)
        if os.path.isdir(dirpath):
            for f in sorted(os.listdir(dirpath)):
                if f.endswith(".txt"):
                    result.append(os.path.join(dirpath, f))
        # glob match: wildcards/name*.txt (partial-name resolution fallback)
        if not result:
            pattern = os.path.join(WILDCARDS_DIR, b) + "*.txt"
            for f in sorted(globmod.glob(pattern)):
                if os.path.isfile(f):
                    result.append(f)
        # alias check (backward compatibility for renamed/moved files)
        if not result and b in WILDCARD_ALIASES:
            aliased = WILDCARD_ALIASES[b]
            result = _try_resolve(aliased)
        return result

    paths = _try_resolve(base)

    # fallback: convert underscores to slashes
    # __camera_shot__ -> try camera/shot as well
    if not paths and "_" in base:
        slash_version = base.replace("_", "/")
        if slash_version != base:
            paths = _try_resolve(slash_version)
            # Also check aliases for the slashed version
            if not paths and slash_version in WILDCARD_ALIASES:
                paths = _try_resolve(WILDCARD_ALIASES[slash_version])

    return paths


def load_wildcard_lines(name: str) -> list[str]:
    """Return all non-empty, non-comment lines from matching wildcard files."""
    lines: list[str] = []
    for fpath in resolve_wildcard_files(name):
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        lines.append(line)
        except OSError:
            continue
    return lines


def pick_random(rng: random.Random, items: list[str], sequential_index: int | None = None) -> str:
    """Pick item uniformly, or weighted if items use N:: prefix.

    When sequential_index is set, picks items[index % len(items)] for
    line-by-line cycling instead of random choice.
    """
    if not items:
        return ""

    # sequential mode: index directly into items, no RNG
    if sequential_index is not None:
        return items[sequential_index % len(items)]

    # check if any item has N:: prefix (weighted) -- was previously only checking items[0]
    has_weights = any("::" in item for item in items)
    if not has_weights:
        return rng.choice(items)

    choices: list[str] = []
    weights: list[float] = []
    for item in items:
        if "::" in item:
            weight_str, _, val = item.partition("::")
            try:
                weight = float(weight_str)
            except ValueError:
                weight = 1.0
            val = val.strip()
        else:
            weight = 1.0
            val = item.strip()
        if val:
            choices.append(val)
            weights.append(max(weight, 0.0))

    if not choices:
        return ""
    return rng.choices(choices, weights=weights, k=1)[0]


def _expand_text(text: str, rng: random.Random, depth: int = 0,
                 sequential_index: int | None = None,
                 _context: dict[str, str] | None = None) -> str:
    """Recursive expansion: captures, wildcards, then variants. Depth-limited."""
    if depth >= DEPTH_LIMIT:
        return text
    if _context is None:
        _context = {}

    # 0. expand __$var:file__ (pick + store) and __$var=value__ (literal assign)
    #    in ONE pass so textual order is respected — the last set in the prompt wins.
    def _replace_capture(m: re.Match) -> str:
        var, file, var2, value = m.group(1), m.group(2), m.group(3), m.group(4)
        if file is not None:
            lines = load_wildcard_lines(file)
            if not lines:
                return m.group(0)
            chosen = pick_random(rng, lines, sequential_index=sequential_index)
            chosen = _expand_text(chosen, rng, depth + 1,
                                  sequential_index=sequential_index, _context=_context)
            _context[var] = chosen
            return chosen
        expanded = _expand_text(value.strip(), rng, depth + 1,
                                sequential_index=sequential_index,
                                _context=_context)
        _context[var2] = expanded
        return expanded

    text = CAPTURE_ANY_RE.sub(_replace_capture, text)

    # 0b. expand __$var__ (reuse captured value)
    def _replace_capture_get(m: re.Match) -> str:
        var = m.group(1)
        if var in _context:
            return _context[var]
        return m.group(0)  # unknown var, leave as-is

    text = CAPTURE_GET_RE.sub(_replace_capture_get, text)

    # 1. expand __wildcard__ references
    def _replace_wildcard(m: re.Match) -> str:
        name = m.group(1)
        lines = load_wildcard_lines(name)
        if not lines:
            return m.group(0)  # leave as-is if not found
        chosen = pick_random(rng, lines, sequential_index=sequential_index)
        return _expand_text(chosen, rng, depth + 1, sequential_index=sequential_index, _context=_context)

    text = WILDCARD_RE.sub(_replace_wildcard, text)

    # 2. expand {opt1|opt2} inline variants
    def _replace_variant(m: re.Match) -> str:
        inner = m.group(1)
        parts = [p.strip() for p in inner.split("|")]
        if len(parts) < 2:
            return m.group(0)
        chosen = pick_random(rng, parts, sequential_index=sequential_index)
        return _expand_text(chosen, rng, depth + 1, sequential_index=sequential_index, _context=_context)

    text = VARIANT_RE.sub(_replace_variant, text)
    return text


def expand_prompt(prompt: str, seed: int | None = None) -> str:
    """Public entry point. Expands wildcards/variants in prompt.

    Args:
        prompt: Input prompt string.
        seed: RNG seed for deterministic output. None = random.

    Returns:
        Expanded prompt string.
    """
    if not prompt or not WILDCARDS_DIR:
        return prompt

    rng = random.Random(seed)
    return _expand_text(prompt, rng, depth=0)


def expand_prompt_sequential(prompt: str, index: int) -> str:
    """Expand prompt using sequential (non-random) selection.

    Each __wildcard__ picks the line at position `index % len(lines)`
    instead of a random choice. This cycles through wildcard files in order.

    Args:
        prompt: Input prompt string.
        index: Zero-based index for line-by-line cycling.

    Returns:
        Expanded prompt string.
    """
    if not prompt or not WILDCARDS_DIR:
        return prompt

    rng = random.Random()  # not used in sequential mode, but needed for signature
    return _expand_text(prompt, rng, depth=0, sequential_index=index)
