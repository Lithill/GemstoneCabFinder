"""Approximate *checking* intervals in days, never automatic watering orders.

Ranges assume ordinary draining pots in indoor light. Always use the species'
moisture check first. Winter/cool room slows drying; warm rooms may speed it up.
"""
# Each four-number list gives spring/summer minimum and maximum, then autumn/winter minimum and maximum, in days. These are moisture-check suggestions, not watering deadlines.
CHECK_INTERVALS = {
    "Money tree": [
        7,
        12,
        14,
        24
    ],
    "Button fern": [
        3,
        6,
        5,
        9
    ],
    "Christmas cactus": [
        7,
        12,
        12,
        21
    ],
    "Fishbone cactus": [
        7,
        12,
        12,
        20
    ],
    "Golden pothos": [
        7,
        12,
        12,
        21
    ],
    "Grape ivy": [
        5,
        9,
        9,
        16
    ],
    "Jade plant": [
        14,
        25,
        25,
        45
    ],
    "Kimberley queen fern": [
        2,
        5,
        4,
        8
    ],
    "Lipstick plant": [
        7,
        12,
        12,
        20
    ],
    "Mother-in-law's tongue": [
        18,
        30,
        30,
        50
    ],
    "Oxalis triangularis": [
        4,
        8,
        7,
        14
    ],
    "Parlour palm": [
        7,
        12,
        10,
        18
    ],
    "Porcelain plant (Hoya)": [
        10,
        18,
        18,
        30
    ],
    "Rattlesnake plant": [
        4,
        7,
        6,
        11
    ],
    "Silver inch plant": [
        5,
        9,
        8,
        15
    ],
    "String of hearts": [
        12,
        21,
        21,
        35
    ],
    "Cape sundew": [
        1,
        2,
        1,
        2
    ]
}
