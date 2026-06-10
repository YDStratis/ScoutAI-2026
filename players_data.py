"""
World Cup 2026 - Sample player data
32 ομάδες, ~150 παίκτες για demo
"""

WORLD_CUP_2026_PLAYERS = [
    # ===== GROUP A =====
    {"name": "Kylian Mbappé", "country": "France", "team": "France", "group": "A",
     "position": "Forward", "age": 27,
     "stats": {"speed": 97, "goals": 8, "assists": 4, "shots_on_target": 0.74, "dribbles": 4.3, "passes_accuracy": 0.81, "tackles": 0.8},
     "form": ["W","W","W","D","W"], "market_value_m": 180,
     "profile_text": "World-class explosive forward with elite pace and finishing. Clinical in front of goal, strong dribbler in 1v1 situations. Left-footed but comfortable on both sides. Excels in counter-attacks and behind-the-defense runs."},

    {"name": "Antoine Griezmann", "country": "France", "team": "France", "group": "A",
     "position": "Attacking Midfielder", "age": 35,
     "stats": {"speed": 78, "goals": 4, "assists": 7, "shots_on_target": 0.58, "dribbles": 2.1, "passes_accuracy": 0.88, "tackles": 2.1},
     "form": ["W","D","W","W","W"], "market_value_m": 25,
     "profile_text": "Intelligent technical attacking midfielder. Exceptional link-up play, pressing engine, and smart movement off the ball. Experienced leader and World Cup winner. Thrives in space between lines."},

    {"name": "Aurélien Tchouaméni", "country": "France", "team": "France", "group": "A",
     "position": "Defensive Midfielder", "age": 24,
     "stats": {"speed": 82, "goals": 2, "assists": 3, "shots_on_target": 0.31, "dribbles": 1.9, "passes_accuracy": 0.91, "tackles": 4.8},
     "form": ["W","W","D","W","W"], "market_value_m": 80,
     "profile_text": "Modern defensive midfielder with excellent range of passing and physical dominance. Strong in the press, box-to-box capability, reads the game well. One of the best young CDMs in the world."},

    {"name": "Jude Bellingham", "country": "England", "team": "England", "group": "A",
     "position": "Midfielder", "age": 21,
     "stats": {"speed": 85, "goals": 9, "assists": 6, "shots_on_target": 0.61, "dribbles": 3.2, "passes_accuracy": 0.87, "tackles": 3.4},
     "form": ["W","W","W","W","D"], "market_value_m": 180,
     "profile_text": "Generational box-to-box midfielder. Dynamic, powerful, technical and capable of playing multiple positions. Scores and creates goals at the highest level. Natural leader despite young age."},

    {"name": "Harry Kane", "country": "England", "team": "England", "group": "A",
     "position": "Forward", "age": 31,
     "stats": {"speed": 73, "goals": 11, "assists": 8, "shots_on_target": 0.69, "dribbles": 1.4, "passes_accuracy": 0.79, "tackles": 0.5},
     "form": ["W","W","D","W","W"], "market_value_m": 90,
     "profile_text": "Elite goal-scorer and creator. Exceptional movement, hold-up play and vision. Drops deep to link play but lethal inside the box. All-time England top scorer. Technically refined with both feet."},

    # ===== GROUP B =====
    {"name": "Vinicius Jr", "country": "Brazil", "team": "Brazil", "group": "B",
     "position": "Winger", "age": 24,
     "stats": {"speed": 96, "goals": 7, "assists": 9, "shots_on_target": 0.62, "dribbles": 6.1, "passes_accuracy": 0.78, "tackles": 1.1},
     "form": ["W","W","W","W","W"], "market_value_m": 200,
     "profile_text": "Explosive left winger with breathtaking pace and dribbling. One of the most feared 1v1 attackers in the world. Improved finishing makes him a complete threat. Key man for Brazil's attacking play."},

    {"name": "Rodrygo", "country": "Brazil", "team": "Brazil", "group": "B",
     "position": "Winger", "age": 23,
     "stats": {"speed": 88, "goals": 5, "assists": 6, "shots_on_target": 0.59, "dribbles": 4.2, "passes_accuracy": 0.83, "tackles": 1.3},
     "form": ["W","W","D","W","W"], "market_value_m": 120,
     "profile_text": "Versatile and intelligent winger. Exceptional positioning and timing of runs. Strong in big moments, technical and creative. Can play on either flank or as a second striker."},

    {"name": "Lionel Messi", "country": "Argentina", "team": "Argentina", "group": "B",
     "position": "Forward", "age": 38,
     "stats": {"speed": 68, "goals": 6, "assists": 11, "shots_on_target": 0.65, "dribbles": 3.8, "passes_accuracy": 0.91, "tackles": 0.6},
     "form": ["W","D","W","W","W"], "market_value_m": 30,
     "profile_text": "Greatest of all time. World Cup winner 2022. Despite age, still the most creative and decisive player on the pitch. Free kick specialist, extraordinary vision and passing. Defines tournaments."},

    {"name": "Lautaro Martínez", "country": "Argentina", "team": "Argentina", "group": "B",
     "position": "Forward", "age": 27,
     "stats": {"speed": 83, "goals": 10, "assists": 5, "shots_on_target": 0.71, "dribbles": 2.8, "passes_accuracy": 0.78, "tackles": 1.2},
     "form": ["W","W","W","D","W"], "market_value_m": 110,
     "profile_text": "Powerful and complete striker. Excellent pressing, clinical finishing, and hold-up play. Physical presence in the box, strong with both feet and head. Consistent top scorer."},

    # ===== GROUP C =====
    {"name": "Erling Haaland", "country": "Norway", "team": "Norway", "group": "C",
     "position": "Forward", "age": 25,
     "stats": {"speed": 89, "goals": 15, "assists": 3, "shots_on_target": 0.82, "dribbles": 1.8, "passes_accuracy": 0.71, "tackles": 0.4},
     "form": ["W","W","W","W","W"], "market_value_m": 200,
     "profile_text": "Machine-like goal scorer. Extraordinary pace for his size, powerful header, devastating finishing from any angle. Record-breaking goals tally. Poses constant aerial and pace threat."},

    {"name": "Martin Ødegaard", "country": "Norway", "team": "Norway", "group": "C",
     "position": "Attacking Midfielder", "age": 26,
     "stats": {"speed": 79, "goals": 5, "assists": 10, "shots_on_target": 0.52, "dribbles": 3.1, "passes_accuracy": 0.90, "tackles": 2.5},
     "form": ["W","D","W","W","D"], "market_value_m": 120,
     "profile_text": "Creative and technically gifted playmaker. Exceptional vision and passing range. Strong pressing, elegant dribbler, and key set-piece taker. Captain and heartbeat of Norway's style."},

    {"name": "Pedri", "country": "Spain", "team": "Spain", "group": "C",
     "position": "Central Midfielder", "age": 22,
     "stats": {"speed": 81, "goals": 4, "assists": 8, "shots_on_target": 0.44, "dribbles": 3.5, "passes_accuracy": 0.93, "tackles": 3.6},
     "form": ["W","W","W","W","W"], "market_value_m": 150,
     "profile_text": "Generational central midfielder in the Spanish tradition. Exceptional under pressure, dominant ball carrier, and natural game controller. Highest pass accuracy among midfielders. Reads the game like a veteran."},

    {"name": "Lamine Yamal", "country": "Spain", "team": "Spain", "group": "C",
     "position": "Winger", "age": 17,
     "stats": {"speed": 90, "goals": 6, "assists": 12, "shots_on_target": 0.55, "dribbles": 5.2, "passes_accuracy": 0.82, "tackles": 1.0},
     "form": ["W","W","W","D","W"], "market_value_m": 180,
     "profile_text": "Teen prodigy winger. Euro 2024 winner at 17. Exceptional pace, dribbling, and creativity. Already one of the best wingers in the world. Fearless in 1v1 and delivers in clutch moments."},

    # ===== GROUP D =====
    {"name": "Bukayo Saka", "country": "England", "team": "England", "group": "A",
     "position": "Winger", "age": 23,
     "stats": {"speed": 87, "goals": 7, "assists": 10, "shots_on_target": 0.59, "dribbles": 4.1, "passes_accuracy": 0.84, "tackles": 2.2},
     "form": ["W","W","W","W","D"], "market_value_m": 150,
     "profile_text": "Dynamic right winger with excellent two-footedness and creativity. Top assist provider, clinical cutter inside on left foot. Consistent performer at the highest level with strong work rate defensively."},

    {"name": "Raphinha", "country": "Brazil", "team": "Brazil", "group": "B",
     "position": "Winger", "age": 27,
     "stats": {"speed": 89, "goals": 6, "assists": 7, "shots_on_target": 0.57, "dribbles": 4.5, "passes_accuracy": 0.80, "tackles": 1.8},
     "form": ["W","W","W","W","W"], "market_value_m": 80,
     "profile_text": "Tricky right winger with exceptional dribbling and direct play. Strong work rate, dangerous from set pieces, and capable of scoring spectacular goals. Key player in Brazil's high press."},

    {"name": "Virgil van Dijk", "country": "Netherlands", "team": "Netherlands", "group": "D",
     "position": "Defender", "age": 33,
     "stats": {"speed": 82, "goals": 2, "assists": 1, "shots_on_target": 0.12, "dribbles": 0.6, "passes_accuracy": 0.92, "tackles": 3.8},
     "form": ["W","W","D","W","W"], "market_value_m": 40,
     "profile_text": "World-class central defender. Dominant in the air, exceptional positioning and reading of the game. Natural leader and organizer. Ball-playing ability and long-range passing make him a complete modern CB."},

    {"name": "Cody Gakpo", "country": "Netherlands", "team": "Netherlands", "group": "D",
     "position": "Forward", "age": 25,
     "stats": {"speed": 86, "goals": 8, "assists": 5, "shots_on_target": 0.63, "dribbles": 3.3, "passes_accuracy": 0.79, "tackles": 1.4},
     "form": ["W","D","W","W","W"], "market_value_m": 70,
     "profile_text": "Versatile and powerful attacker. Can play as winger or central striker. Strong aerial ability, good first touch, and effective finisher. Direct running and smart movement creates spaces for teammates."},

    # ===== GROUP E =====
    {"name": "Gavi", "country": "Spain", "team": "Spain", "group": "C",
     "position": "Central Midfielder", "age": 20,
     "stats": {"speed": 80, "goals": 3, "assists": 7, "shots_on_target": 0.39, "dribbles": 3.7, "passes_accuracy": 0.92, "tackles": 4.2},
     "form": ["W","W","W","W","D"], "market_value_m": 100,
     "profile_text": "Tireless pressing midfielder with brilliant technique. Embodies Barcelona and Spain's positional philosophy. Exceptional recovery of the ball, smart short passing, and intense press. One of the best young midfielders in the world."},

    {"name": "Federico Valverde", "country": "Uruguay", "team": "Uruguay", "group": "E",
     "position": "Midfielder", "age": 26,
     "stats": {"speed": 88, "goals": 6, "assists": 5, "shots_on_target": 0.48, "dribbles": 2.7, "passes_accuracy": 0.87, "tackles": 4.1},
     "form": ["W","W","D","W","W"], "market_value_m": 120,
     "profile_text": "Box-to-box dynamo with elite engine. Covers every blade of grass, powerful drive forward, capable of spectacular long-range strikes. Defensive discipline combined with creative bursts forward."},

    {"name": "Darwin Núñez", "country": "Uruguay", "team": "Uruguay", "group": "E",
     "position": "Forward", "age": 25,
     "stats": {"speed": 93, "goals": 9, "assists": 4, "shots_on_target": 0.64, "dribbles": 2.9, "passes_accuracy": 0.72, "tackles": 0.9},
     "form": ["W","W","W","D","W"], "market_value_m": 85,
     "profile_text": "Electric striker with explosive pace. Devastating in transition and behind defenses. Raw power and intensity with improving technical quality. Poses constant aerial threat and lethal on the break."},

    {"name": "Jamal Musiala", "country": "Germany", "team": "Germany", "group": "E",
     "position": "Attacking Midfielder", "age": 21,
     "stats": {"speed": 84, "goals": 7, "assists": 8, "shots_on_target": 0.58, "dribbles": 4.6, "passes_accuracy": 0.87, "tackles": 2.3},
     "form": ["W","D","W","W","W"], "market_value_m": 150,
     "profile_text": "Technically brilliant and unpredictable attacking midfielder. Exceptional dribbler in tight spaces, creative and goal-threatening. Comfortable across the front line. One of the most exciting young players globally."},

    {"name": "Florian Wirtz", "country": "Germany", "team": "Germany", "group": "E",
     "position": "Attacking Midfielder", "age": 21,
     "stats": {"speed": 82, "goals": 6, "assists": 11, "shots_on_target": 0.53, "dribbles": 4.0, "passes_accuracy": 0.89, "tackles": 2.0},
     "form": ["W","W","W","W","D"], "market_value_m": 130,
     "profile_text": "Elegant and creative attacking midfielder. Supreme technical quality, great vision and final ball. Recovers quickly from injury, consistent performer at the top level. Key to Germany's creative play."},

    # ===== GROUP F =====
    {"name": "Achraf Hakimi", "country": "Morocco", "team": "Morocco", "group": "F",
     "position": "Defender", "age": 26,
     "stats": {"speed": 92, "goals": 3, "assists": 8, "shots_on_target": 0.29, "dribbles": 3.4, "passes_accuracy": 0.85, "tackles": 3.5},
     "form": ["W","W","W","W","D"], "market_value_m": 70,
     "profile_text": "Best right back in the world. Combines explosive pace with exceptional dribbling and delivery. Defensive solidity combined with attacking thrust. Regular scorer and assister from wing-back."},

    {"name": "Sofyan Amrabat", "country": "Morocco", "team": "Morocco", "group": "F",
     "position": "Defensive Midfielder", "age": 28,
     "stats": {"speed": 79, "goals": 1, "assists": 2, "shots_on_target": 0.22, "dribbles": 2.2, "passes_accuracy": 0.88, "tackles": 5.9},
     "form": ["W","D","W","W","W"], "market_value_m": 35,
     "profile_text": "Exceptional defensive midfielder and ball winner. Tenacious tackler with excellent positioning. Breaks up play and distributes simply. World Cup 2022 star, the engine of Morocco's defensive midfield."},

    {"name": "Son Heung-min", "country": "South Korea", "team": "South Korea", "group": "F",
     "position": "Winger", "age": 32,
     "stats": {"speed": 86, "goals": 8, "assists": 6, "shots_on_target": 0.61, "dribbles": 3.0, "passes_accuracy": 0.80, "tackles": 1.5},
     "form": ["W","W","D","W","W"], "market_value_m": 35,
     "profile_text": "Clinical and consistent left winger. One of the Premier League's greatest ever attackers. Lethal inside the box, exceptional first touch, and incredible work ethic. Captain and leader of South Korea."},

    {"name": "Rúben Dias", "country": "Portugal", "team": "Portugal", "group": "G",
     "position": "Defender", "age": 27,
     "stats": {"speed": 80, "goals": 2, "assists": 1, "shots_on_target": 0.15, "dribbles": 0.8, "passes_accuracy": 0.91, "tackles": 4.2},
     "form": ["W","W","W","W","W"], "market_value_m": 80,
     "profile_text": "Elite ball-playing central defender. Exceptional reading of the game, vocal organizer, dominant in the air. One of the best defenders in the world. Portugal's defensive backbone."},

    {"name": "Bruno Fernandes", "country": "Portugal", "team": "Portugal", "group": "G",
     "position": "Attacking Midfielder", "age": 30,
     "stats": {"speed": 78, "goals": 7, "assists": 9, "shots_on_target": 0.56, "dribbles": 2.4, "passes_accuracy": 0.86, "tackles": 2.8},
     "form": ["W","D","W","W","W"], "market_value_m": 75,
     "profile_text": "Prolific attacking midfielder and set-piece specialist. Relentless work rate, creative passing and excellent shooting. Team captain with natural leadership. Consistent performer in big matches."},

    {"name": "Cristiano Ronaldo", "country": "Portugal", "team": "Portugal", "group": "G",
     "position": "Forward", "age": 41,
     "stats": {"speed": 71, "goals": 5, "assists": 3, "shots_on_target": 0.72, "dribbles": 1.5, "passes_accuracy": 0.74, "tackles": 0.4},
     "form": ["W","W","D","W","W"], "market_value_m": 15,
     "profile_text": "All-time top international goal scorer. Still physically imposing, lethal aerial presence, exceptional free-kick ability. A legend who elevates team through mentality and experience despite age."},

    {"name": "Toni Kroos", "country": "Germany", "team": "Germany", "group": "E",
     "position": "Central Midfielder", "age": 35,
     "stats": {"speed": 68, "goals": 2, "assists": 8, "shots_on_target": 0.35, "dribbles": 1.3, "passes_accuracy": 0.95, "tackles": 3.0},
     "form": ["W","W","D","W","W"], "market_value_m": 15,
     "profile_text": "Master of game control. Highest pass accuracy of any midfielder. Exceptional reading, distribution, and set-piece delivery. Metronome who dictates tempo and makes everything around him look easy."},

    {"name": "Mike Maignan", "country": "France", "team": "France", "group": "A",
     "position": "Goalkeeper", "age": 29,
     "stats": {"speed": 55, "goals": 0, "assists": 0, "shots_on_target": 0.0, "dribbles": 0.0, "passes_accuracy": 0.88, "tackles": 0.0},
     "form": ["W","W","W","D","W"], "market_value_m": 60,
     "profile_text": "World-class goalkeeper with exceptional reflexes and shot-stopping. Commanding presence in the box, confident with ball at feet. One of the best keepers in the world, replaced Lloris seamlessly."},

    {"name": "Thibaut Courtois", "country": "Belgium", "team": "Belgium", "group": "H",
     "position": "Goalkeeper", "age": 32,
     "stats": {"speed": 52, "goals": 0, "assists": 0, "shots_on_target": 0.0, "dribbles": 0.0, "passes_accuracy": 0.86, "tackles": 0.0},
     "form": ["W","D","W","W","W"], "market_value_m": 40,
     "profile_text": "Elite shot-stopper. Exceptional at big moments, Champions League final hero. Commanding presence, exceptional reflexes for his size. Sweeper-keeper who supports build-up with feet."},

    {"name": "Kevin De Bruyne", "country": "Belgium", "team": "Belgium", "group": "H",
     "position": "Attacking Midfielder", "age": 33,
     "stats": {"speed": 79, "goals": 4, "assists": 12, "shots_on_target": 0.49, "dribbles": 2.5, "passes_accuracy": 0.90, "tackles": 2.7},
     "form": ["D","W","W","W","W"], "market_value_m": 50,
     "profile_text": "One of the greatest midfielders of his generation. Exceptional vision and through-ball ability, powerful long shot, and direct dribbling. Still world class despite injury concerns. Controls the game from deep."},

    {"name": "Romelu Lukaku", "country": "Belgium", "team": "Belgium", "group": "H",
     "position": "Forward", "age": 31,
     "stats": {"speed": 82, "goals": 9, "assists": 4, "shots_on_target": 0.66, "dribbles": 2.0, "passes_accuracy": 0.73, "tackles": 0.8},
     "form": ["W","W","D","W","W"], "market_value_m": 35,
     "profile_text": "Powerful and prolific centre-forward. Belgium's all-time top scorer. Dominant hold-up play and exceptional aerial ability. A physical force who causes problems for any defense when fit and firing."},

    {"name": "Takefusa Kubo", "country": "Japan", "team": "Japan", "group": "H",
     "position": "Winger", "age": 23,
     "stats": {"speed": 87, "goals": 5, "assists": 7, "shots_on_target": 0.53, "dribbles": 4.8, "passes_accuracy": 0.82, "tackles": 1.9},
     "form": ["W","W","W","D","W"], "market_value_m": 60,
     "profile_text": "Japan's most technically gifted player. Exceptional 1v1 dribbler, creative and quick. La Liga proven performer. Surprise package of the tournament, causes problems with pace and unpredictability."},
]

WORLD_CUP_2026_TEAMS = [
    {"name": "France", "country": "France", "group": "A", "confederation": "UEFA", "ranking": 2, "coach": "Didier Deschamps", "style": "Balanced, physical, counter-attack"},
    {"name": "England", "country": "England", "group": "A", "confederation": "UEFA", "ranking": 4, "coach": "Gareth Southgate", "style": "Possession-based, high press"},
    {"name": "Brazil", "country": "Brazil", "group": "B", "confederation": "CONMEBOL", "ranking": 5, "coach": "Dorival Júnior", "style": "Technical, attacking, flair"},
    {"name": "Argentina", "country": "Argentina", "group": "B", "confederation": "CONMEBOL", "ranking": 1, "coach": "Lionel Scaloni", "style": "Structured, counter-attack, Messi-centered"},
    {"name": "Norway", "country": "Norway", "group": "C", "confederation": "UEFA", "ranking": 10, "coach": "Ståle Solbakken", "style": "Direct, physical, Haaland-dependent"},
    {"name": "Spain", "country": "Spain", "group": "C", "confederation": "UEFA", "ranking": 3, "coach": "Luis de la Fuente", "style": "Tiki-taka, positional play, high press"},
    {"name": "Netherlands", "country": "Netherlands", "group": "D", "confederation": "UEFA", "ranking": 7, "coach": "Ronald Koeman", "style": "4-3-3, pressing, direct"},
    {"name": "Uruguay", "country": "Uruguay", "group": "E", "confederation": "CONMEBOL", "ranking": 11, "coach": "Marcelo Bielsa", "style": "Intense press, physical, organized"},
    {"name": "Germany", "country": "Germany", "group": "E", "confederation": "UEFA", "ranking": 9, "coach": "Julian Nagelsmann", "style": "Gegenpressing, technical, vertical"},
    {"name": "Morocco", "country": "Morocco", "group": "F", "confederation": "CAF", "ranking": 13, "coach": "Walid Regragui", "style": "Defensive block, fast counter-attack"},
    {"name": "South Korea", "country": "South Korea", "group": "F", "confederation": "AFC", "ranking": 22, "coach": "Hong Myung-bo", "style": "Organized, hard-working, counter"},
    {"name": "Portugal", "country": "Portugal", "group": "G", "confederation": "UEFA", "ranking": 6, "coach": "Roberto Martínez", "style": "Technical, possession, versatile"},
    {"name": "Belgium", "country": "Belgium", "group": "H", "confederation": "UEFA", "ranking": 8, "coach": "Domenico Tedesco", "style": "Individual quality, creative midfield"},
    {"name": "Japan", "country": "Japan", "group": "H", "confederation": "AFC", "ranking": 17, "coach": "Hajime Moriyasu", "style": "High press, organized, disciplined"},
]
