import json
import random
from typing import Dict, List, Tuple

class Country:
    def __init__(self, data: dict):
        self.name = data['name']
        self.weight = data['weight']
        self.alliances = data.get('alliances', [])
        self.trade_partners = data.get('trade_partners', {})
        self.economic_health = data['economic_health']
        self.gdp = data['gdp']
        self.debt = data['debt']
        self.inflation = data['inflation']
        self.unemployment = data['unemployment']
        self.trade_balance = data.get('trade_balance', 0)
        self.digitalization = data.get('digitalization', 50)
        self.export_oriented = data.get('export_oriented', False)
        self.energy_import = data.get('energy_import', 0)
        self.energy_export = data.get('energy_export', 0)
        self.initial_health = data['economic_health']

    def take_damage(self, damage: int, multiplier: float = 1.0):
        effective = int(damage * multiplier)
        self.economic_health = max(0, self.economic_health - effective)
        if effective > 0:
            self.unemployment = min(40, self.unemployment + effective / 20)
            self.inflation = min(50, self.inflation + effective / 25)

    def recover(self, amount: int):
        self.economic_health = min(self.initial_health, self.economic_health + amount)
        self.unemployment = max(0, self.unemployment - amount / 30)
        self.inflation = max(0, self.inflation - amount / 40)

    def is_collapsed(self) -> bool:
        return self.economic_health <= 20

class Attack:
    def __init__(self, data: dict):
        self.name = data['name']
        self.base_cost = data['base_cost']
        self.base_damage = data['base_damage']
        self.base_risk = data['base_risk']
        self.attack_type = data['attack_type']
        self.tooltip = data.get('tooltip', '')
        self.multipliers = data.get('multipliers', {})

class GlobalEconomyGame:
    ALLIANCE_RISK = {
        'НАТО': 1.3,
        'G7': 1.1,
        'ЕС': 1.2,
        'БРИКС': 1.1,
        'Five Eyes': 1.5,
        'Союзник США': 1.2,
        'ШОС': 1.1,
    }

    def __init__(self, json_file: str):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.countries: Dict[str, Country] = {}
        for cdata in data['countries']:
            c = Country(cdata)
            self.countries[c.name] = c
        self.attacks: List[Attack] = [Attack(a) for a in data['attacks']]
        self.global_params = data['global_params']

        self.ip = 800
        self.reveal = 0
        self.day = 0
        self.game_over = False
        self.win = False
        self.last_event = ""

    def _get_attack_multiplier(self, attack: Attack, country: Country) -> float:
        mult = 1.0
        if attack.attack_type == 'кибер':
            if country.digitalization >= 80:
                mult *= attack.multipliers.get('digitalization_high', 1.5)
            elif country.digitalization <= 40:
                mult *= attack.multipliers.get('digitalization_low', 0.6)
        elif attack.attack_type == 'экономическая':
            if country.export_oriented:
                mult *= attack.multipliers.get('export_oriented', 1.4)
            else:
                mult *= attack.multipliers.get('large_domestic', 0.8)
        elif attack.attack_type == 'финансовая':
            if country.debt > country.gdp:
                mult *= attack.multipliers.get('high_debt', 1.5)
            else:
                mult *= attack.multipliers.get('low_debt', 0.7)
        elif attack.attack_type == 'энергетическая':
            if country.energy_import > 0.4:
                mult *= attack.multipliers.get('high_energy_import', 1.5)
            elif country.energy_export > 0.4:
                mult *= attack.multipliers.get('energy_exporter', 0.6)
        elif attack.attack_type == 'социальная':
            if country.unemployment > 8 or country.inflation > 8:
                mult *= 1.5
        return mult

    def _calculate_risk(self, attack: Attack, target: Country) -> int:
        risk = attack.base_risk * target.weight
        for alliance in target.alliances:
            name = alliance if isinstance(alliance, str) else alliance.get('name', '')
            mult = self.ALLIANCE_RISK.get(name, 1.0)
            if name == 'Five Eyes' and attack.attack_type != 'кибер':
                continue
            risk *= mult
        return int(risk)

    def _spread_damage(self, source_name: str, initial_damage: int):
        visited = set()
        queue = [(source_name, initial_damage, 1.0)]
        while queue:
            curr_name, damage, factor = queue.pop(0)
            if curr_name in visited:
                continue
            visited.add(curr_name)
            curr = self.countries[curr_name]
            for partner, share in curr.trade_partners.items():
                if partner in visited:
                    continue
                transfer = int(damage * share * self.global_params['contagion_factor'] * factor)
                if transfer > 0:
                    partner_country = self.countries[partner]
                    partner_country.take_damage(transfer)
                    queue.append((partner, transfer, factor * 0.5))

    def apply_attack(self, attack_name: str, target_name: str) -> Tuple[bool, str]:
        if self.game_over:
            return False, "Игра окончена"

        attack = next(a for a in self.attacks if a.name == attack_name)
        target = self.countries[target_name]
        cost = int(attack.base_cost * target.weight)
        if self.ip < cost:
            return False, f"Не хватает IP! Нужно: {cost}"

        success_chance = 70 - (self.reveal // 2)
        success = random.randint(1, 100) <= success_chance

        multiplier = self._get_attack_multiplier(attack, target) if success else 1.0
        damage = int(attack.base_damage * multiplier) if success else int(attack.base_damage * 0.3)
        risk = self._calculate_risk(attack, target)

        target.take_damage(damage)
        self.ip -= cost

        if success:
            self.reveal = min(100, self.reveal + risk)
            bonus = int(cost * 0.35)
            self.ip += bonus
            msg = f"✅ УСПЕХ! {attack.name} | Урон: {damage} | Риск: +{risk} | Бонус: +{bonus} IP"
            self._spread_damage(target_name, damage)
        else:
            penalty = int(cost * 0.2)
            self.ip = max(0, self.ip - penalty)
            msg = f"❌ ПРОВАЛ! {attack.name} | Урон: {damage} | Потеряно: {penalty} IP"

        if self.reveal >= 100:
            self.game_over = True
            msg += "\n🕵️‍♂️ ВАС РАСКРЫЛИ! Игра окончена."

        avg_health = sum(c.economic_health for c in self.countries.values()) / len(self.countries)
        if avg_health <= self.global_params['world_health_threshold']:
            self.game_over = True
            self.win = True
            msg += "\n🌍 ГЛОБАЛЬНЫЙ КОЛЛАПС! Вы победили."

        return success, msg

    def daily_update(self):
        if self.game_over:
            return
        self.day += 1
        self.ip = max(0, self.ip - self.global_params['daily_maintenance_cost'])
        self.reveal = max(0, self.reveal - self.global_params['reveal_decay'])

        for country in self.countries.values():
            if country.economic_health > 50:
                regen = self.global_params['recovery_rate_high']
                # ускоренное восстановление для членов ЕС или БРИКС
                for alliance in country.alliances:
                    name = alliance if isinstance(alliance, str) else alliance.get('name', '')
                    if name in ('ЕС', 'БРИКС'):
                        regen += 1
                        break
                country.recover(regen)
            else:
                if country.economic_health < 20:
                    country.take_damage(3)
                elif country.economic_health < 30:
                    country.take_damage(2)
                elif country.economic_health < 50:
                    country.take_damage(1)

        if random.random() < 0.2:
            self._trigger_random_event()

        avg_health = sum(c.economic_health for c in self.countries.values()) / len(self.countries)
        if avg_health <= self.global_params['world_health_threshold']:
            self.game_over = True
            self.win = True
            self.last_event = "Глобальный коллапс! Победа!"
        elif self.reveal >= 100:
            self.game_over = True
            self.last_event = "Вас раскрыли! Поражение."

    def _trigger_random_event(self):
        events = [
            ("💵 Спонсорская помощь", lambda: setattr(self, 'ip', self.ip + 150)),
            ("🔍 Утечка информации", lambda: setattr(self, 'reveal', min(100, self.reveal + 15))),
            ("🌍 Пандемия", lambda: [c.take_damage(int(c.economic_health * 0.05)) for c in self.countries.values()]),
            ("🏦 Банковский кризис", lambda: [c.take_damage(int(c.economic_health * 0.03)) for c in self.countries.values()]),
            ("💡 Технологический прорыв", lambda: self.countries['Китай'].recover(10)),
            ("🛢️ Нефтяной кризис", lambda: self.countries['Германия'].take_damage(8)),
            ("🌪️ Природная катастрофа", lambda: random.choice(list(self.countries.values())).take_damage(10)),
            ("📉 Мировая рецессия", lambda: [c.take_damage(5) for c in self.countries.values() if c.economic_health > 50]),
            ("🤝 Торговое соглашение", lambda: [c.recover(5) for c in self.countries.values() if c.export_oriented]),
            ("⚡ Киберщит", lambda: setattr(self, 'reveal', max(0, self.reveal - 10))),
        ]
        name, effect = random.choice(events)
        effect()
        self.last_event = name

    def get_state(self) -> dict:
        avg_health = sum(c.economic_health for c in self.countries.values()) / len(self.countries)
        return {
            'ip': self.ip,
            'reveal': self.reveal,
            'day': self.day,
            'game_over': self.game_over,
            'win': self.win,
            'last_event': self.last_event,
            'global_health': int(avg_health),
            'countries': [
                {
                    'name': c.name,
                    'economic_health': c.economic_health,
                    'weight': c.weight,
                    'gdp': c.gdp,
                    'debt': c.debt,
                    'inflation': round(c.inflation, 1),
                    'unemployment': round(c.unemployment, 1),
                    'trade_balance': c.trade_balance,
                    'digitalization': c.digitalization,
                    'export_oriented': c.export_oriented,
                    'energy_import': c.energy_import,
                    'energy_export': c.energy_export,
                    'trade_partners': c.trade_partners,
                    'alliances': c.alliances
                }
                for c in self.countries.values()
            ],
            'attacks': [
                {
                    'name': a.name,
                    'cost': a.base_cost,
                    'damage': a.base_damage,
                    'risk': a.base_risk,
                    'tooltip': a.tooltip
                }
                for a in self.attacks
            ]
        }

    def to_dict(self):
        return {
            'ip': self.ip,
            'reveal': self.reveal,
            'day': self.day,
            'game_over': self.game_over,
            'win': self.win,
            'last_event': self.last_event,
            'global_params': self.global_params,
            'countries': {c.name: {
                'name': c.name,
                'weight': c.weight,
                'alliances': c.alliances,
                'trade_partners': c.trade_partners,
                'economic_health': c.economic_health,
                'gdp': c.gdp,
                'debt': c.debt,
                'inflation': c.inflation,
                'unemployment': c.unemployment,
                'trade_balance': c.trade_balance,
                'digitalization': c.digitalization,
                'export_oriented': c.export_oriented,
                'energy_import': c.energy_import,
                'energy_export': c.energy_export,
                'initial_health': c.initial_health
            } for c in self.countries.values()},
            'attacks': [a.__dict__ for a in self.attacks]
        }

    @classmethod
    def from_dict(cls, data):
        instance = cls.__new__(cls)
        instance.ip = data['ip']
        instance.reveal = data['reaveal'] if 'reaveal' in data else data['reveal']
        instance.day = data['day']
        instance.game_over = data['game_over']
        instance.win = data['win']
        instance.last_event = data.get('last_event', '')
        instance.global_params = data['global_params']

        instance.countries = {}
        for name, cdata in data['countries'].items():
            c = Country({
                'name': cdata['name'],
                'weight': cdata['weight'],
                'alliances': cdata['alliances'],
                'trade_partners': cdata['trade_partners'],
                'economic_health': cdata['economic_health'],
                'gdp': cdata['gdp'],
                'debt': cdata['debt'],
                'inflation': cdata['inflation'],
                'unemployment': cdata['unemployment'],
                'trade_balance': cdata.get('trade_balance', 0),
                'digitalization': cdata.get('digitalization', 50),
                'export_oriented': cdata.get('export_oriented', False),
                'energy_import': cdata.get('energy_import', 0),
                'energy_export': cdata.get('energy_export', 0)
            })
            c.initial_health = cdata['initial_health']
            instance.countries[name] = c

        instance.attacks = [Attack(a) for a in data['attacks']]
        return instance
