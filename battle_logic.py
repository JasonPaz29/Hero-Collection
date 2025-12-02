import copy, random
team_synergies = {
    ("alpha", "beta", "gamma"): {"attack_boost": 1.10},
    ("delta", "epsilon", "zeta"): {"attack_boost": 1.15},
    ("alpha", "gamma", "epsilon"): {"defense_boost": 1.12},
    ("beta", "delta", "zeta"): {"defense_boost": 1.18},
    ("alpha", "delta", "zeta"): {"base_hp_boost": 1.20},
    ("beta", "gamma", "epsilon"): {"base_hp_boost": 1.25},
}

normalized_team_synergies = {}
for key, value in team_synergies.items():
    normalized_team_synergies[tuple(sorted(t.lower() for t in key))] = value

team_synergies = normalized_team_synergies


advantages = {"alpha": "beta",
               "beta": "gamma",
                "gamma": "delta",
                 "delta": "epsilon",
                   "epsilon": "zeta",
                     "zeta": "eta",
                       "eta": "alpha"}

class BattleResult:
    def __init__(self, winner, loser, log):
        self.winner = winner
        self.loser = loser
        self.log = log

def apply_team_synergy(team_heroes) -> bool:
    types = tuple(sorted([hero.greek_type.lower() for hero in team_heroes]))
    synergy = team_synergies.get(types, {})
    for hero in team_heroes:
        if "attack_boost" in synergy:
            hero.base_attack = int(hero.base_attack * synergy["attack_boost"])
        if "defense_boost" in synergy:
            hero.base_defense = int(hero.base_defense * synergy["defense_boost"])
        if "base_hp_boost" in synergy:
            hero.base_hp = int(hero.base_hp * synergy["base_hp_boost"])
    return True if synergy else False

def simulate_battle(team_heroes_a, team_heroes_b, name_a: str, name_b: str) -> BattleResult:
    miss_chance = 10

    started = False
    log = []
    turn = random.randint(0, 1)  # 0 for User A, 1 for User B
    ha1 = copy.deepcopy(team_heroes_a[0])
    ha2 = copy.deepcopy(team_heroes_a[1])
    ha3 = copy.deepcopy(team_heroes_a[2])
    hb1 = copy.deepcopy(team_heroes_b[0])
    hb2 = copy.deepcopy(team_heroes_b[1])
    hb3 = copy.deepcopy(team_heroes_b[2])

    apply_team_synergy(team_heroes_a)
    apply_team_synergy(team_heroes_b)
    if apply_team_synergy(team_heroes_a):
        log.append(f"{name_a}'s team synergy activated!")
    if apply_team_synergy(team_heroes_b):
        log.append(f"{name_b}'s team synergy activated!")

    while True:
        miss_random = random.randint(1, 100)
        if turn == 1:
            if not started:
                log.append(f"{name_b} starts the battle!")
                started = True
            attacker = next((h for h in team_heroes_b if h.base_hp > 0), None)
            defender = next((h for h in team_heroes_a if h.base_hp > 0), None)

            if not attacker and not defender:
                log.append("Both teams are out of heroes!")
                return BattleResult("Draw", "Draw", log)

            if not attacker:
                log.append(f"{name_a} wins the battle!")
                return BattleResult(name_a, name_b, log)

            if not defender:
                log.append(f"{name_b} wins the battle!")
                return BattleResult(name_b, name_a, log)
            if defender.greek_type.lower() == advantages.get(attacker.greek_type.lower()) and miss_random > miss_chance:
                attack_value = int(attacker.base_attack * 1.15) - defender.base_defense
                defender.base_hp -= max(attack_value, 1)
                log.append(f"{attacker.name} deals a super effective hit against {defender.name}, dealing {max(attack_value, 1)} damage!, leaving them with {defender.base_hp if defender.base_hp > 0 else 0} HP!")
            elif attacker.greek_type.lower() == advantages.get(defender.greek_type.lower()) and miss_random > miss_chance:
                attack_value = int(attacker.base_attack * 0.85) - defender.base_defense
                defender.base_hp -= max(attack_value, 1)
                log.append(f"{attacker.name} deals a not very effective hit against {defender.name}, dealing {max(attack_value, 1)} damage!, leaving them with {defender.base_hp if defender.base_hp > 0 else 0} HP!")
            elif miss_random <= miss_chance:
                attack_value = 0
                log.append(f"{attacker.name} tried to attack {defender.name} but missed!")
            else:
                attack_value = attacker.base_attack - defender.base_defense
                defender.base_hp -= max(attack_value, 1)
                log.append(f"{attacker.name} attacks {defender.name}, dealing {max(attack_value, 1)} damage!, leaving them with {defender.base_hp if defender.base_hp > 0 else 0} HP!")
            if defender.base_hp <= 0:
                defender.base_hp = 0
        else:
            if not started:
                log.append(f"{name_a} starts the battle!")
                started = True
            attacker = next((h for h in team_heroes_a if h.base_hp > 0), None)
            defender = next((h for h in team_heroes_b if h.base_hp > 0), None)

            if not attacker and not defender:
                log.append("Both teams are out of heroes!")
                return BattleResult("Draw", "Draw", log)

            if not attacker:
                log.append(f"{name_b} wins the battle!")
                return BattleResult(name_b, name_a, log)

            if not defender:
                log.append(f"{name_a} wins the battle!")
                return BattleResult(name_a, name_b, log)

            if defender.greek_type.lower() == advantages.get(attacker.greek_type.lower()) and miss_random > miss_chance:
                attack_value = int(attacker.base_attack * 1.15) - defender.base_defense
                defender.base_hp -= max(attack_value, 1)
                log.append(f"{attacker.name} deals a super effective hit against {defender.name}, dealing {max(attack_value, 1)} damage!, leaving them with {defender.base_hp if defender.base_hp > 0 else 0} HP!")
            elif attacker.greek_type.lower() == advantages.get(defender.greek_type.lower()) and miss_random > miss_chance:
                attack_value = int(attacker.base_attack * 0.85) - defender.base_defense
                defender.base_hp -= max(attack_value, 1)
                log.append(f"{attacker.name} deals a not very effective hit against {defender.name}, dealing {max(attack_value, 1)} damage!, leaving them with {defender.base_hp if defender.base_hp > 0 else 0} HP!")
            elif miss_random <= miss_chance:
                attack_value = 0
                log.append(f"{attacker.name} tried to attack {defender.name} but missed!")
            else:
                attack_value = attacker.base_attack - defender.base_defense
                defender.base_hp -= max(attack_value, 1)
                log.append(f"{attacker.name} attacks {defender.name}, dealing {max(attack_value, 1)} damage!, leaving them with {defender.base_hp if defender.base_hp > 0 else 0} HP!")
            if defender.base_hp <= 0:
                defender.base_hp = 0
        turn = 1 - turn
