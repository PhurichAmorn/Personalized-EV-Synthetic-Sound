"""Pilot recipe windows for future search policies; existing sessions do not use them."""

import math

from audio import SOUND_RECIPES


RECIPE_NAMES = {
    'Comfort': {'comfort_clean_v1': 'Clean Electric', 'comfort_warm_v1': 'Warm Motor'},
    'Sport': {'sport_electric_v1': 'Electric Sport', 'sport_ice_v1': 'ICE Inspired'},
    'Deep': {'deep_traction_v1': 'Traction Glide', 'deep_orchestral_v1': 'Orchestral Rise'},
}
PROBE_VERSION = 2
PROBE_GROUPS = ('register', 'tone', 'response', 'regen')
PROBE_GROUP_FIELDS = {
    'register': ('electric_pitch_offset', 'electric_pitch_scale', 'order_rpm_scale'),
    'tone': ('richness', 'electric_cutoff', 'electric_depth', 'electric_growl'),
    'response': ('drive_cruise_gain', 'acceleration_richness', 'drive_attack_s',
                 'drive_release_s', 'order_throttle_rpm_boost'),
    'regen': ('electric_regen_gain', 'electric_regen_richness', 'regen_attack_s', 'regen_release_s'),
}
# Increasing response strength shortens these envelopes.
_REVERSED_PROBE_FIELDS = {'drive_attack_s', 'drive_release_s', 'regen_attack_s', 'regen_release_s'}
RECIPE_PROBE_GROUPS = {'sport_ice_v1': ('register', 'response')}
# Provisional attenuation from the steady 110 km/h review RMS.
RECIPE_LISTENING_GAIN = {
    'comfort_clean_v1': 1., 'comfort_warm_v1': .63,
    'sport_electric_v1': .38, 'sport_ice_v1': 1.,
    'deep_traction_v1': .83, 'deep_orchestral_v1': 1.,
}
RECIPE_BASES = {
    recipe_id: SOUND_RECIPES[mode][name]
    for mode, recipes in RECIPE_NAMES.items()
    for recipe_id, name in recipes.items()
}

# Each pair gives physical values at normalized control 0 and 1; the preview is 0.5.
# Coupled fields move together so a candidate remains within its recipe's character.
WINDOWS = {
    'comfort_clean_v1': {
        'register': {'electric_pitch_offset': (105., 125.), 'electric_pitch_scale': (.10, .24)},
        'tone': {'richness': (.025, .10), 'electric_cutoff': (420., 650.),
                 'electric_depth': (.025, .07), 'electric_growl': (.05, .22)},
        'response': {'drive_cruise_gain': (.12, .30), 'acceleration_richness': (.012, .06),
                     'drive_attack_s': (.22, .10), 'drive_release_s': (.40, .22)},
        'regen': {'electric_regen_gain': (.12, .32), 'regen_attack_s': (.28, .17),
                  'regen_release_s': (.42, .24)},
    },
    'comfort_warm_v1': {
        'register': {'electric_pitch_offset': (70., 90.), 'electric_pitch_scale': (.18, .34)},
        'tone': {'richness': (.07, .20), 'electric_cutoff': (350., 580.),
                 'electric_depth': (.08, .16), 'electric_growl': (.15, .36)},
        'response': {'drive_cruise_gain': (.22, .44), 'acceleration_richness': (.012, .06),
                     'drive_attack_s': (.22, .10), 'drive_release_s': (.40, .22)},
        'regen': {'electric_regen_gain': (.12, .32), 'regen_attack_s': (.28, .17),
                  'regen_release_s': (.42, .24)},
    },
    'sport_electric_v1': {
        'register': {'electric_pitch_offset': (0., 12.), 'electric_pitch_scale': (.75, 1.18)},
        'tone': {'richness': (.30, .58), 'electric_cutoff': (700., 1050.),
                 'electric_depth': (.08, .18), 'electric_growl': (.75, 1.)},
        'response': {'drive_cruise_gain': (.55, .85), 'acceleration_richness': (.12, .24),
                     'drive_attack_s': (.11, .05), 'drive_release_s': (.19, .09)},
        'regen': {'electric_regen_gain': (.24, .45), 'electric_regen_richness': (.30, .60),
                  'regen_attack_s': (.20, .10), 'regen_release_s': (.30, .17)},
    },
    'sport_ice_v1': {
        'register': {'order_rpm_scale': (1.20, 1.45)},
        'response': {'order_throttle_rpm_boost': (2400., 3800.)},
    },
    'deep_traction_v1': {
        'register': {'electric_pitch_offset': (25., 40.), 'electric_pitch_scale': (.43, .68)},
        'tone': {'richness': (.15, .30), 'electric_cutoff': (450., 700.),
                 'electric_depth': (.15, .27), 'electric_growl': (.08, .25)},
        'response': {'drive_cruise_gain': (.27, .47), 'acceleration_richness': (.06, .16),
                     'drive_attack_s': (.30, .16), 'drive_release_s': (.52, .30)},
        'regen': {'electric_regen_gain': (.20, .40), 'regen_attack_s': (.40, .22),
                  'regen_release_s': (.55, .35)},
        'layer': {'traction_mix': (.25, .52), 'orchestral_mix': (.35, .62)},
    },
    'deep_orchestral_v1': {
        'register': {'electric_pitch_offset': (35., 50.), 'electric_pitch_scale': (.65, .90)},
        'tone': {'richness': (.16, .30), 'electric_cutoff': (650., 900.),
                 'electric_depth': (.10, .20), 'electric_growl': (.08, .25)},
        'response': {'drive_cruise_gain': (.38, .62), 'acceleration_richness': (.06, .16),
                     'drive_attack_s': (.45, .25), 'drive_release_s': (.70, .40)},
        'regen': {'electric_regen_gain': (.20, .40), 'regen_attack_s': (.40, .22),
                  'regen_release_s': (.55, .35)},
        'layer': {'traction_mix': (.02, .15), 'orchestral_mix': (.72, .98)},
    },
}


def recipe_ids(mode):
    if mode not in RECIPE_NAMES:
        raise ValueError('Unknown sound mode.')
    return tuple(RECIPE_NAMES[mode])


def recipe_controls(recipe_id):
    if recipe_id not in WINDOWS:
        raise ValueError('Unknown sound recipe.')
    return tuple(WINDOWS[recipe_id])


def recipe_bounds(recipe_id):
    if recipe_id not in WINDOWS:
        raise ValueError('Unknown sound recipe.')
    base = RECIPE_BASES[recipe_id]
    return {key: (min(low, base[key], high), max(low, base[key], high))
            for group in WINDOWS[recipe_id].values() for key, (low, high) in group.items()}


def mode_bounds(mode):
    """Return shared physical bounds across a mode's recipes, grouped for tuning."""
    if mode not in RECIPE_NAMES:
        raise ValueError('Unknown sound mode.')
    result = {group: {} for group in PROBE_GROUPS}
    for recipe_id in recipe_ids(mode):
        base = RECIPE_BASES[recipe_id]
        recipe_limits = recipe_bounds(recipe_id)
        for group, fields in PROBE_GROUP_FIELDS.items():
            for field in fields:
                if field not in base:
                    continue
                low, high = recipe_limits.get(field, (base[field], base[field]))
                previous = result[group].get(field)
                result[group][field] = ((min(low, previous[0]), max(high, previous[1]))
                                        if previous else (low, high))
    return result


def recipe_probe_groups(recipe_id):
    if recipe_id not in RECIPE_BASES:
        raise ValueError('Unknown sound recipe.')
    return RECIPE_PROBE_GROUPS.get(recipe_id, PROBE_GROUPS)


def probe_profile(mode, recipe_id, controls):
    """Map four linked normalized probe groups through shared mode-level bounds."""
    if mode not in RECIPE_NAMES or recipe_id not in RECIPE_NAMES[mode]:
        raise ValueError('Unknown sound recipe for mode.')
    if set(controls) != set(recipe_probe_groups(recipe_id)) or any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 <= value <= 1 for value in controls.values()):
        raise ValueError('Invalid probe controls.')
    profile = dict(RECIPE_BASES[recipe_id])
    bounds = mode_bounds(mode)
    for group, position in controls.items():
        for field in PROBE_GROUP_FIELDS[group]:
            if field not in profile or field not in bounds[group]:
                continue
            low, high = bounds[group][field]
            if field in _REVERSED_PROBE_FIELDS:
                low, high = high, low
            center = RECIPE_BASES[recipe_id][field]
            profile[field] = (low + (center - low) * 2 * position if position < .5
                              else center + (high - center) * (2 * position - 1))
    return profile


def recipe_profile(recipe_id, controls):
    if recipe_id not in WINDOWS:
        raise ValueError('Unknown sound recipe.')
    if set(controls) != set(WINDOWS[recipe_id]) or any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 <= value <= 1 for value in controls.values()):
        raise ValueError('Invalid recipe controls.')
    profile = dict(RECIPE_BASES[recipe_id])
    for group, physical in WINDOWS[recipe_id].items():
        position = controls[group]
        for key, (low, high) in physical.items():
            center = RECIPE_BASES[recipe_id][key]
            profile[key] = (low + (center - low) * 2 * position if position < .5
                            else center + (high - center) * (2 * position - 1))
    return profile
