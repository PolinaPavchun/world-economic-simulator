import json
import random
from typing import Dict, List, Tuple


class Country:
    """Текущее состояние и характеристики страны"""
    
    def __init__(self, name: str, weight: float, alliances: List[str], 
                 lat: float, lon: float, initial_si: int):
        self.name = name                      # название страны
        self.weight = weight                  # вес страны 
        self.alliances = alliances            # список альянсов 
        self.lat = lat                        # широта для карты
        self.lon = lon                        # долгота для карты
        self.initial_si = initial_si          # начальная стабильность
        self.si = initial_si                  # текущая стабильность 
        
    def get_color(self) -> str:
        """Цвет точки, отображающую страну на карте"""
        if self.si >= 70:
            return '#2ecc71'      
        elif self.si >= 40:
            return '#f39c12'      
        elif self.si >= 20:
            return '#e67e22'      
        else:
            return '#e74c3c'      
    
    def get_status(self) -> str:
        """Состояния страны"""
        if self.si >= 70:
            return "Стабильна"
        elif self.si >= 40:
            return "Напряженно"
        elif self.si >= 20:
            return "Кризис"
        else:
            return "Коллапс"
    
    def take_damage(self, damage: int):
        """Наносим урон стабильности"""
        self.si = max(0, self.si - damage)
    
    def recover(self, amount: int):
        """Восстанавливаем стабильность"""
        self.si = min(self.initial_si, self.si + amount)


class Attack:
    """Параметры атак"""
    
    def __init__(self, name: str, base_cost: int, base_damage: int, 
                 base_risk: int, attack_type: str):
        self.name = name                      # название атаки
        self.base_cost = base_cost            # базовая стоимость
        self.base_damage = base_damage        # базовый урон по стабильности
        self.base_risk = base_risk            # базовый риск раскрытия
        self.attack_type = attack_type        # тип атаки 


class Game:
    """Главный класс игры - здесь всё работает"""
    
    # Множители риска для альянсов
    ALLIANCE_MULTIPLIERS = {
        'НАТО': 1.3,
        'G7': 1.1,
        'ЕС': 1.2,
        'БРИКС': 1.1,
        'Five Eyes': 1.5,      # только для кибератак
        'Союзник США': 1.2,
    }
    
    def __init__(self, json_file: str):
        """Запуск новой игры"""
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.countries: Dict[str, Country] = {
            c['name']: Country(**c) for c in data['countries']
        }
        self.attacks: List[Attack] = [Attack(**a) for a in data['attacks']]

        # Основные показатели игры
        self.ip = 500                     # очки влияния (IP)
        self.reveal = 0                   # раскрываемость 
        self.day = 0                      # текущий игровой день
        self.current_round = 1            # какой сейчас раунд 
        self.current_targets: List[Country] = []   # цели текущего раунда
        self.round_bonus_given = False    # бонус за раунд уже выдан?
        self.game_over = False             # игра закончена?
        self.win = False                   # победа или поражение?
        self.last_event = ""               # последнее текущее случайное событие
        self.rounds = []
        self._setup_rounds()
        self._start_round()
    
    def _setup_rounds(self):
        """Настраиваем 4 раунда: слабая → средняя → сильная → финал(три рандомных страны из всех категорий)"""
        weak = [name for name in self.countries if self.countries[name].weight <= 1.0]
        medium = [name for name in self.countries if 1.0 < self.countries[name].weight <= 1.5]
        strong = [name for name in self.countries if self.countries[name].weight > 1.5]

        self.rounds = [
            [random.choice(weak)],
            [random.choice(medium)],
            [random.choice(strong)],
            [random.choice(weak), random.choice(medium), random.choice(strong)]
        ]
    
    def _start_round(self):
        """Начинаем новый раунд, выбираем цели"""
        if self.current_round > len(self.rounds):
            self.game_over = True
            self.win = True
            return
        target_names = self.rounds[self.current_round - 1]
        self.current_targets = [self.countries[name] for name in target_names]
        self.round_bonus_given = False

    def _check_round_complete(self) -> bool:
        """Проверяем, все ли цели раунда в коллапсе (SI ≤ 20)"""
        return all(c.si <= 20 for c in self.current_targets)

    def _give_round_bonus(self) -> int:
        """Выдача бонусных очков за успешное прохождение раунда"""
        if self.round_bonus_given:
            return 0
        bonuses = {1: 100, 2: 150, 3: 200, 4: 250}
        bonus = bonuses[self.current_round]
        self.ip += bonus
        self.round_bonus_given = True
        return bonus

    def _calculate_risk(self, attack: Attack, target: Country) -> int:
        """Считаем риск раскрытия: базовый риск * вес страны * множители альянсов"""
        risk = attack.base_risk * target.weight
        for alliance in target.alliances:
            if alliance == 'Five Eyes' and attack.attack_type != 'кибер':
                continue
            risk *= self.ALLIANCE_MULTIPLIERS.get(alliance, 1.0)
        return int(risk)

    def apply_attack(self, attack_name: str, target_name: str) -> Tuple[bool, str]:
        """
        Проводим операцию против страны
        Возвращает успех атаки и сообщение для игрока
        """
        if self.game_over:
            return False, "Игра окончена"
        attack = next(a for a in self.attacks if a.name == attack_name)
        target = self.countries[target_name]
        cost = int(attack.base_cost * target.weight)
        if self.ip < cost:
            return False, f"Не хватает IP! Нужно: {cost}"
        success = random.randint(1, 100) <= (70 - self.reveal // 2)
        risk = self._calculate_risk(attack, target)
        damage = attack.base_damage if success else int(attack.base_damage * 0.3)
        self.ip -= cost
        target.take_damage(damage)

        if success:
            self.reveal = min(100, self.reveal + risk)
            bonus = int(cost * 0.35)
            self.ip += bonus
            msg = f"УСПЕХ! {attack_name}\nУрон: {damage} | Риск: +{risk} | Бонус: +{bonus} IP"
        else:
            penalty = int(cost * 0.2)
            self.ip = max(0, self.ip - penalty)
            msg = f"ПРОВАЛ! {attack_name}\nУрон: {damage} | Потеряно: {penalty} IP"

        if self.reveal >= 100:
            self.game_over = True
            msg += "\n🕵️‍♂️ ВАС РАСКРЫЛИ! Игра окончена."

        if self._check_round_complete():
            bonus = self._give_round_bonus()
            if self.current_round >= len(self.rounds):
                self.game_over = True
                self.win = True
                msg += f"\nПОБЕДА! +{bonus} IP"
            else:
                self.current_round += 1
                msg += f"\nРАУНД {self.current_round - 1} ПРОЙДЕН! +{bonus} IP"
                self._start_round()

        return success, msg

    def daily_update(self):
        """
        Каждый новый день:
        - снимаем ежедневное содержание
        - снижаем раскрываемость
        - страны восстанавливаются или падают дальше
        - может случиться случайное событие
        """
        if self.game_over:
            return
        self.day += 1
        self.ip = max(0, self.ip - 8)
        self.reveal = max(0, self.reveal - 2)
        for country in self.countries.values():
            if country.si > 50:
                regen = 2 if ('ЕС' in country.alliances or 'БРИКС' in country.alliances) else 1
                country.recover(regen)
            else:
                if country.si < 20:
                    country.take_damage(3)
                elif country.si < 30:
                    country.take_damage(2)
                elif country.si < 50:
                    country.take_damage(1)

        if random.random() < 0.2:
            self._trigger_random_event()
        else:
            self.last_event = ""

        if self.reveal >= 100:
            self.game_over = True
            self.last_event = "🕵️‍♂️ Вас раскрыли!"

        if self._check_round_complete():
            bonus = self._give_round_bonus()
            if self.current_round >= len(self.rounds):
                self.game_over = True
                self.win = True
                self.last_event = f"ПОБЕДА! +{bonus} IP"
            else:
                self.current_round += 1
                self.last_event = f"Раунд {self.current_round - 1} пройден! +{bonus} IP"
                self._start_round()

    def _trigger_random_event(self):
        """Случайные события"""
        events = [
            ("💵 Спонсорская помощь", lambda: setattr(self, 'ip', self.ip + 100)),
            ("🔍 Утечка информации", lambda: setattr(self, 'reveal', min(100, self.reveal + 15))),
            ("🌍 Пандемия", lambda: [c.take_damage(int(c.si * 0.05)) for c in self.countries.values()]),
            ("🏦 Банковский кризис", lambda: [c.take_damage(int(c.si * 0.03)) for c in self.countries.values()]),
            ("💡 Технологический прорыв", lambda: self.countries['Китай'].recover(10)),
            ("🛢️ Нефтяной кризис", lambda: self.countries['Германия'].take_damage(8)),
            ("🌪️ Природная катастрофа", lambda: random.choice(list(self.countries.values())).take_damage(10)),
        ]
        name, effect = random.choice(events)
        effect()
        self.last_event = name

    def get_state(self) -> dict:
        """
        Собираем всё, что нужно показать игроку на экране
        """
        return {
            'ip': self.ip,
            'reveal': self.reveal,
            'day': self.day,
            'current_round': self.current_round,
            'total_rounds': len(self.rounds),
            'game_over': self.game_over,
            'win': self.win,
            'last_event': self.last_event,
            'current_targets': [{'name': c.name, 'si': c.si, 'status': c.get_status()} for c in self.current_targets],
            'countries': [{'name': c.name, 'si': c.si, 'color': c.get_color(),
                           'status': c.get_status(), 'lat': c.lat, 'lon': c.lon} for c in self.countries.values()],
            'attacks': [{'name': a.name, 'cost': a.base_cost, 'damage': a.base_damage, 'risk': a.base_risk} for a in self.attacks]
        }


