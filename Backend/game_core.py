# game_core.py — вся игровая логика: страны, атаки, заражение, квиз.
# Не зависит от Flask — работает как чистая Python-библиотека.

import json            # чтение balance.json
import random          # случайный выбор вопросов и бросок кубика успеха атаки
from typing import Dict, List, Tuple  # подсказки типов для читаемости кода
from dataclasses import dataclass     # удобное создание классов-данных без лишнего кода
from lessons import LESSONS           # тексты объяснений после каждой атаки


@dataclass
class EconomicConnection:
    # Одна экономическая связь между двумя странами — торговая, долговая или энергетическая.
    from_country: str
    to_country: str
    connection_type: str  # 'trade', 'debt', 'energy'
    strength: float       # 0–1, сила связи
    data: dict


class Country:
    # Хранит экономические показатели одной страны и методы получения урона и восстановления.
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
        # Начальные значения — нижняя граница при восстановлении
        self.initial_inflation = data['inflation']
        self.initial_unemployment = data['unemployment']
        self.foreign_reserves = data.get('foreign_reserves_usd_billion', 100)
        self.human_development_index = data.get('human_development_index', 0.7)
        self.corruption_perception_index = data.get('corruption_perception_index', 50)
        self.external_debt_holders = data.get('external_debt_holders', {})
        self.energy_dependencies = data.get('energy_dependencies', {})
        self.trade_blocs = data.get('trade_blocs', [])

    def take_damage(self, damage: int, multiplier: float = 1.0):
        # Снижает здоровье страны и ухудшает экономические показатели.
        effective = int(damage * multiplier)
        self.economic_health = max(0, self.economic_health - effective)
        if effective > 0:
            self.unemployment = min(40, self.unemployment + effective / 20)
            self.inflation = min(50, self.inflation + effective / 25)
            if self.foreign_reserves > 0:
                self.foreign_reserves = max(0, self.foreign_reserves - effective * 0.5)

    def recover(self, amount: int):
        # Восстанавливает здоровье и показатели, не превышая начальные значения.
        self.economic_health = min(self.initial_health, self.economic_health + amount)
        self.unemployment = max(self.initial_unemployment, self.unemployment - amount / 30)
        self.inflation = max(self.initial_inflation, self.inflation - amount / 40)
        if self.human_development_index > 0.8:
            self.foreign_reserves = min(self.foreign_reserves + amount * 0.3, 5000)

    def is_collapsed(self) -> bool:
        # Возвращает True если здоровье ниже 20% — страна начинает деградировать сама по себе.
        return self.economic_health <= 20
    
    def get_reserve_protection(self) -> float:
        """Возвращает множитель защиты от финансовых атак на основе резервов"""
        if self.foreign_reserves > 1000:  # > $1 трлн
            return 0.5  # 50% защита
        elif self.foreign_reserves > 500:  # > $500 млрд
            return 0.7  # 30% защита
        elif self.foreign_reserves > 200:  # > $200 млрд
            return 0.85  # 15% защита
        else:
            return 1.0  # нет защиты
    
    def get_corruption_multiplier(self) -> float:
        """Возвращает множитель уязвимости на основе коррупции"""
        if self.corruption_perception_index < 30:  # Высокая коррупция
            return 1.5  # +50% урон
        elif self.corruption_perception_index < 50:  # Средняя коррупция
            return 1.2  # +20% урон
        else:  # Низкая коррупция
            return 1.0  # без изменений
    
    def get_hdi_recovery_bonus(self) -> float:
        """Возвращает бонус к восстановлению на основе ИЧР"""
        if self.human_development_index > 0.9:
            return 1.5  # +50% к восстановлению
        elif self.human_development_index > 0.8:
            return 1.2  # +20% к восстановлению
        else:
            return 1.0

class Attack:
    # Один вид атаки со стоимостью, базовым уроном, риском раскрытия и множителями для разных условий цели.
    def __init__(self, data: dict):
        self.name = data['name']
        self.base_cost = data['base_cost']
        self.base_damage = data['base_damage']
        self.base_risk = data['base_risk']
        self.attack_type = data['attack_type']
        self.tooltip = data.get('tooltip', '')
        self.multipliers = data.get('multipliers', {})

class GlobalEconomyGame:
    # Центральный класс игры: страны, атаки, механика кризиса и сохранение прогресса.
    # Насколько присутствие в альянсе повышает риск раскрытия при атаке
    ALLIANCE_RISK = {
        'НАТО': 1.3,
        'G7': 1.1,
        'ЕС': 1.2,
        'БРИКС': 1.1,
        'Five Eyes': 1.5,
        'Союзник США': 1.2,
        'ШОС': 1.1,
    }

    # Смягчение урона по типу атаки в зависимости от членства в альянсе
    ALLIANCE_DEFENSE = {
        'G7': {
            'currency_crisis': 0.70,  # экстренные кредиты МВФ и координация валют
            'debt_spiral': 0.72,       # члены G7 спасают друг друга пакетами помощи
        },
        'ЕС': {
            'energy_embargo': 0.62,    # регламент солидарности ЕС и совместные газовые резервы
            'trade_blockade': 0.80,    # единый рынок ЕС даёт альтернативные каналы торговли
        },
        'БРИКС': {
            'trade_blockade': 0.85,    # альтернативные торговые маршруты БРИКС
        },
        'Five Eyes': {
            'cyber_attack': 0.38,      # совместный разведывательный обмен в сфере кибербезопасности
        },
        'НАТО': {
            'social_unrest': 0.82,     # устойчивость демократических институтов
        },
        'ШОС': {
            'social_unrest': 0.90,     # механизмы политической стабилизации
        },
    }
    
    TRADE_BLOC_SUPPORT = {
        'ЕС': 1.5,  # Страны ЕС поддерживают друг друга
        'USMCA': 1.3,  # Североамериканская зона
        'RCEP': 1.2,  # Азиатско-тихоокеанская зона
        'Mercosur': 1.1,  # Южная Америка
        'ЕАЭС': 1.2,  # Евразийский союз
        'GCC': 1.3,  # Совет сотрудничества арабских государств
        'SADC': 1.1,  # Юг Африки
        'SAARC': 1.1,  # Южная Азия
        'CPTPP': 1.2,  # Транстихоокеанское партнёрство
        'ЕАСТ': 1.3,  # Европейская ассоциация свободной торговли
    }

    def __init__(self, json_file: str):
        # Загружает данные из balance.json и инициализирует новую игру.
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.countries: Dict[str, Country] = {}
        for cdata in data['countries']:
            c = Country(cdata)
            self.countries[c.name] = c

        self.attacks: List[Attack] = [Attack(a) for a in data['attacks']]
        self.global_params = data['global_params']
        self.ip = 1000
        self.reveal = 0
        self.day = 0
        self.game_over = False
        self.win = False
        self.connections: List[EconomicConnection] = []
        self._build_connection_graph()
        self._quiz_answer: str = ""
        self._quiz_explanation: str = ""
        self._quiz_reward: int = 0
        self.quiz_today_count: int = 0
        self.quiz_reset_day: int = 0
        self.asked_quiz_ids: list = []
        self.consecutive_failures: int = 0

    def _build_connection_graph(self):
        # Строит граф торговых, долговых и энергетических связей между странами.
        for country in self.countries.values():
            for partner, share in country.trade_partners.items():
                if partner in self.countries:
                    self.connections.append(EconomicConnection(
                        country.name, partner, 'trade', share, {}
                    ))

            for creditor, amount in country.external_debt_holders.items():
                if creditor in self.countries:
                    strength = min(amount / 1000, 1.0)
                    self.connections.append(EconomicConnection(
                        country.name, creditor, 'debt', strength, {'amount': amount}
                    ))
            
            # Энергетические связи
            for supplier, share in country.energy_dependencies.items():
                if supplier in self.countries:
                    self.connections.append(EconomicConnection(
                        country.name, supplier, 'energy', share, {}
                    ))
    
    def _get_trade_bloc_multiplier(self, country: Country) -> float:
        """Возвращает множитель поддержки от торговых блоков"""
        max_mult = 1.0
        for bloc in country.trade_blocs:
            mult = self.TRADE_BLOC_SUPPORT.get(bloc, 1.0)
            if mult > max_mult:
                max_mult = mult
        return max_mult

    def _get_alliance_defense(self, country: Country, attack_type: str) -> Tuple[float, str]:
        """Returns (damage_reduction_multiplier, explanation) from alliance membership."""
        best_mult = 1.0
        notes = []
        alliance_names = [
            a if isinstance(a, str) else a.get('name', '')
            for a in country.alliances
        ]
        for name in alliance_names:
            reductions = self.ALLIANCE_DEFENSE.get(name, {})
            reduction = reductions.get(attack_type, 1.0)
            if reduction < best_mult:
                best_mult = reduction
                mechanism = {
                    'currency_crisis': f"{name} смягчил удар — экстренные кредиты МВФ стабилизируют валюту",
                    'debt_spiral': f"{name} смягчил удар — союзники поддержали пакетом финансовой помощи",
                    'energy_embargo': f"{name} смягчил удар — страны блока делятся энергоресурсами",
                    'trade_blockade': f"{name} смягчил удар — альтернативные рынки снижают потери",
                    'social_unrest': f"{name} смягчил удар — институты удержали протесты",
                    'cyber_attack': f"{name} смягчил удар — совместная разведка предупредила атаку",
                }.get(attack_type, f"{name} смягчил удар — союзники оказали поддержку")
                notes.append(mechanism)
        return best_mult, "; ".join(notes)

    def _get_attack_multiplier_and_explanation(self, attack: Attack, country: Country) -> Tuple[float, str, str]:
        """Возвращает (множитель, объяснение успеха/неудачи, образовательный урок)"""
        mult = 1.0
        explanation = ""
        lesson = ""

        if attack.attack_type == 'currency_crisis':
            debt_ratio = country.debt / country.gdp * 100 if country.gdp > 0 else 0
            reserves = country.foreign_reserves
            high_debt = debt_ratio > 80
            low_reserves = reserves < 200

            if high_debt and low_reserves:
                mult = attack.multipliers.get('high_debt_low_reserves', 2.2)
                explanation = LESSONS['currency_crisis']['success_high_debt_low_reserves']['text'].format(
                    debt=round(debt_ratio, 1), reserves=round(reserves, 1))
                lesson = LESSONS['currency_crisis']['success_high_debt_low_reserves']['lesson']
            elif high_debt:
                mult = attack.multipliers.get('high_debt', 1.5)
                explanation = LESSONS['currency_crisis']['success_high_debt']['text'].format(debt=round(debt_ratio, 1))
                lesson = LESSONS['currency_crisis']['success_high_debt']['lesson']
            elif low_reserves:
                mult = attack.multipliers.get('low_reserves', 1.3)
                explanation = LESSONS['currency_crisis']['success_low_reserves']['text'].format(reserves=round(reserves, 1))
                lesson = LESSONS['currency_crisis']['success_low_reserves']['lesson']
            else:
                mult = attack.multipliers.get('low_debt_high_reserves', 0.4)
                explanation = LESSONS['currency_crisis']['failure']['text'].format(
                    debt=round(debt_ratio, 1), reserves=round(reserves, 1))
                lesson = LESSONS['currency_crisis']['failure']['lesson']

        elif attack.attack_type == 'debt_spiral':
            debt_ratio = country.debt / country.gdp * 100 if country.gdp > 0 else 0
            critical_t = attack.multipliers.get('conditions', {}).get('critical_threshold', 100)
            high_t = attack.multipliers.get('conditions', {}).get('high_threshold', 80)

            if debt_ratio > critical_t:
                mult = attack.multipliers.get('critical_debt', 2.1)
                explanation = LESSONS['debt_spiral']['critical']['text'].format(debt=round(debt_ratio, 1))
                lesson = LESSONS['debt_spiral']['critical']['lesson']
            elif debt_ratio > high_t:
                mult = attack.multipliers.get('high_debt', 1.4)
                explanation = LESSONS['debt_spiral']['high']['text'].format(debt=round(debt_ratio, 1))
                lesson = LESSONS['debt_spiral']['high']['lesson']
            else:
                mult = attack.multipliers.get('low_debt', 0.3)
                explanation = LESSONS['debt_spiral']['failure']['text'].format(debt=round(debt_ratio, 1))
                lesson = LESSONS['debt_spiral']['failure']['lesson']

        elif attack.attack_type == 'trade_blockade':
            trade_dependency = sum(country.trade_partners.values()) * 100
            num_partners = len(country.trade_partners)
            high_dependency = trade_dependency > 50
            concentrated = num_partners <= 3

            if high_dependency and concentrated:
                mult = attack.multipliers.get('high_dependency', 1.8) * attack.multipliers.get('concentrated_partners', 1.5)
                explanation = LESSONS['trade_blockade']['success_high_dependency']['text'].format(
                    dependency=round(trade_dependency, 1)) + f" Всего {num_partners} партнёра — нет диверсификации."
                lesson = LESSONS['trade_blockade']['success_high_dependency']['lesson']
            elif high_dependency:
                mult = attack.multipliers.get('high_dependency', 1.8)
                explanation = LESSONS['trade_blockade']['success_high_dependency']['text'].format(
                    dependency=round(trade_dependency, 1))
                lesson = LESSONS['trade_blockade']['success_high_dependency']['lesson']
            elif concentrated:
                mult = attack.multipliers.get('concentrated_partners', 1.5)
                explanation = LESSONS['trade_blockade']['success_concentrated']['text'].format(partners=num_partners)
                lesson = LESSONS['trade_blockade']['success_concentrated']['lesson']
            else:
                mult = attack.multipliers.get('low_dependency', 0.4)
                explanation = LESSONS['trade_blockade']['failure']['text'].format(dependency=round(trade_dependency, 1))
                lesson = LESSONS['trade_blockade']['failure']['lesson']

        elif attack.attack_type == 'energy_embargo':
            energy_import_pct = country.energy_import * 100
            energy_export_pct = country.energy_export * 100
            is_exporter = energy_export_pct > 40

            if is_exporter:
                mult = attack.multipliers.get('energy_exporter', 0.2)
                explanation = f"Страна экспортирует {round(energy_export_pct, 1)}% энергии — эмбарго контрпродуктивно."
                lesson = "Экспортёры энергии не просто устойчивы — они сами могут использовать энергию как оружие."
            elif energy_import_pct > 40:
                mult = attack.multipliers.get('high_import', 2.0)
                explanation = LESSONS['energy_embargo']['success_high_import']['text'].format(
                    import_value=round(energy_import_pct, 1))
                lesson = LESSONS['energy_embargo']['success_high_import']['lesson']
            else:
                mult = attack.multipliers.get('low_import', 0.4)
                explanation = LESSONS['energy_embargo']['failure']['text'].format(
                    import_value=round(energy_import_pct, 1))
                lesson = LESSONS['energy_embargo']['failure']['lesson']

        elif attack.attack_type == 'social_unrest':
            inflation = country.inflation
            unemployment = country.unemployment
            corruption = country.corruption_perception_index
            high_inflation = inflation > 8
            high_unemployment = unemployment > 10
            high_corruption = corruption < 35

            if high_inflation and high_unemployment and high_corruption:
                mult = attack.multipliers.get('triple_threat', 2.5)
                explanation = (f"Тройной удар: инфляция {round(inflation,1)}% + безработица {round(unemployment,1)}% "
                               f"+ коррупция (индекс {corruption}) — взрывная смесь.")
                lesson = LESSONS['social_unrest']['triple_threat']['lesson']
            elif high_inflation and high_unemployment:
                mult = attack.multipliers.get('both_high', 2.0)
                explanation = f"Инфляция {round(inflation,1)}% + безработица {round(unemployment,1)}% = двойной удар по уровню жизни."
                lesson = LESSONS['social_unrest']['both_high']['lesson']
            elif high_inflation:
                mult = attack.multipliers.get('high_inflation', 1.7)
                explanation = LESSONS['social_unrest']['success_high_inflation']['text'].format(inflation=round(inflation, 1))
                lesson = LESSONS['social_unrest']['success_high_inflation']['lesson']
            elif high_unemployment:
                mult = attack.multipliers.get('high_unemployment', 1.9)
                explanation = LESSONS['social_unrest']['success_high_unemployment']['text'].format(unemployment=round(unemployment, 1))
                lesson = LESSONS['social_unrest']['success_high_unemployment']['lesson']
            elif high_corruption:
                mult = attack.multipliers.get('high_corruption', 1.5)
                explanation = f"Коррупционный скандал работает: индекс восприятия коррупции {corruption} — доверие к власти подорвано."
                lesson = LESSONS['social_unrest']['high_corruption']['lesson']
            else:
                mult = attack.multipliers.get('low_all', 0.4)
                explanation = LESSONS['social_unrest']['failure']['text'].format(
                    inflation=round(inflation, 1), unemployment=round(unemployment, 1))
                lesson = LESSONS['social_unrest']['failure']['lesson']

        elif attack.attack_type == 'cyber_attack':
            digital = country.digitalization
            high_t = attack.multipliers.get('conditions', {}).get('high_threshold', 75)
            mid_t = attack.multipliers.get('conditions', {}).get('mid_threshold', 55)

            if digital > high_t:
                mult = attack.multipliers.get('high_digital', 1.9)
                explanation = LESSONS['cyber_attack']['high_digital']['text'].format(digital=digital)
                lesson = LESSONS['cyber_attack']['high_digital']['lesson']
            elif digital > mid_t:
                mult = attack.multipliers.get('mid_digital', 1.0)
                explanation = LESSONS['cyber_attack']['mid_digital']['text'].format(digital=digital)
                lesson = LESSONS['cyber_attack']['mid_digital']['lesson']
            else:
                mult = attack.multipliers.get('low_digital', 0.4)
                explanation = LESSONS['cyber_attack']['low_digital']['text'].format(digital=digital)
                lesson = LESSONS['cyber_attack']['low_digital']['lesson']

        else:
            mult = 1.0
            explanation = "Атака применена."
            lesson = ""

        if attack.attack_type not in ['cyber_attack', 'social_unrest']:
            corruption_mult = country.get_corruption_multiplier()
            if corruption_mult > 1.0:
                mult *= corruption_mult
                explanation += f" Коррупция (ИКВ {country.corruption_perception_index}) усилила урон."

        if attack.attack_type in ['currency_crisis', 'debt_spiral']:
            reserve_protection = country.get_reserve_protection()
            if reserve_protection < 1.0:
                mult *= reserve_protection

        alliance_mult, alliance_note = self._get_alliance_defense(country, attack.attack_type)
        if alliance_mult < 1.0:
            mult *= alliance_mult
            explanation += f" {alliance_note}."

        return mult, explanation, lesson

    def _calculate_risk(self, attack: Attack, target: Country) -> int:
        risk = attack.base_risk * target.weight
        for alliance in target.alliances:
            name = alliance if isinstance(alliance, str) else alliance.get('name', '')
            mult = self.ALLIANCE_RISK.get(name, 1.0)
            if name == 'Five Eyes' and attack.attack_type != 'кибер':
                continue
            risk *= mult
        return int(risk)

    def _spread_damage_with_tracking(self, source_name: str, initial_damage: int) -> List[dict]:
        """Распространяет урон и возвращает список затронутых стран с типами связей"""
        affected = []
        visited = set()
        queue = [(source_name, initial_damage, 1.0)]
        
        while queue:
            curr_name, damage, factor = queue.pop(0)
            if curr_name in visited:
                continue
            visited.add(curr_name)
            
            curr_country = self.countries.get(curr_name)
            if not curr_country:
                continue
            
            # союзники по тому же альянсу получают 30 процентов от урона текущей страны
            for alliance in curr_country.alliances:
                alliance_name = alliance if isinstance(alliance, str) else alliance.get('name', '')
                for other_name, other_country in self.countries.items():
                    if other_name == curr_name or other_name in visited:
                        continue
                    other_alliance_names = [a if isinstance(a, str) else a.get('name', '') for a in other_country.alliances]
                    if alliance_name in other_alliance_names:
                        alliance_transfer = int(damage * 0.3 * factor)
                        if alliance_transfer > 0:
                            other_country.take_damage(alliance_transfer)
                            affected.append({
                                'country': other_name,
                                'damage': alliance_transfer,
                                'connection_type': 'alliance',
                                'alliance': alliance_name
                            })
                            queue.append((other_name, alliance_transfer, factor * 0.3))
            
            # кредиторы получают до 20% урона в зависимости от суммы долга
            for debtor_name, debt_amount in curr_country.external_debt_holders.items():
                if debtor_name in self.countries and debtor_name not in visited:
                    strength = min(debt_amount / 1000, 1.0)
                    debt_transfer = int(damage * strength * 0.2 * factor)
                    if debt_transfer > 0:
                        debtor_country = self.countries[debtor_name]
                        debtor_country.take_damage(debt_transfer)
                        affected.append({
                            'country': debtor_name,
                            'damage': debt_transfer,
                            'connection_type': 'debt',
                            'amount': debt_amount
                        })
                        queue.append((debtor_name, debt_transfer, factor * 0.3))
            
            # связи из графа — каждая передаёт разную долю урона в зависимости от типа и силы
            relevant_connections = [
                c for c in self.connections 
                if c.from_country == curr_name and c.to_country not in visited
            ]
            
            for conn in relevant_connections:
                if conn.connection_type == 'trade':
                    # торговый партнёр получает силу_связи умноженную на коэффициент заражения из balance.json
                    transfer = int(damage * conn.strength * self.global_params['contagion_factor'] * factor)
                elif conn.connection_type == 'debt':
                    # кредитор получает 50 процентов урона; если его долг выше 90 процентов ВВП удар вырастает в полтора раза
                    transfer = int(damage * conn.strength * 0.5 * factor)
                    if transfer > 5 and conn.to_country in self.countries:
                        creditor = self.countries[conn.to_country]
                        if creditor.debt > creditor.gdp * 0.9:
                            transfer = int(transfer * 1.5)
                elif conn.connection_type == 'energy':
                    # энергетически зависимая страна получает 60 процентов урона умноженных на долю зависимости
                    transfer = int(damage * conn.strength * 0.6 * factor)
                else:
                    # прочие типы связей передают 20 процентов урона
                    transfer = int(damage * conn.strength * 0.2 * factor)
                
                if transfer > 0 and conn.to_country in self.countries:
                    partner_country = self.countries[conn.to_country]
                    partner_country.take_damage(transfer)
                    affected.append({
                        'country': conn.to_country,
                        'damage': transfer,
                        'connection_type': conn.connection_type,
                        'strength': conn.strength
                    })
                    queue.append((conn.to_country, transfer, factor * 0.5))
        
        return affected

    def _spread_damage(self, source_name: str, initial_damage: int):
        """Распространяет урон через все типы связей (без отслеживания)"""
        self._spread_damage_with_tracking(source_name, initial_damage)

    def apply_attack(self, attack_name: str, target_name: str) -> Tuple[bool, str, dict]:
        if self.game_over:
            return False, "Игра окончена", {}

        attack = next(a for a in self.attacks if a.name == attack_name)
        target = self.countries[target_name]
        cost = int(attack.base_cost * target.weight)

        reveal_cost_mult = 1.0
        if self.reveal >= 70:
            reveal_cost_mult = 1.30
        elif self.reveal >= 40:
            reveal_cost_mult = 1.15
        effective_cost = int(cost * reveal_cost_mult)

        if self.ip < effective_cost:
            return False, f"Недостаточно очков влияния (нужно {effective_cost})", {}

        # После 2 провалов подряд шанс 80%, после 3 — гарантированный успех
        if self.consecutive_failures >= 3:
            base_chance = 100
        elif self.consecutive_failures >= 2:
            base_chance = 80
        else:
            base_chance = 65
        success = random.randint(1, 100) <= base_chance

        multiplier, explanation, lesson = self._get_attack_multiplier_and_explanation(attack, target)
        if not success:
            multiplier = 0.3
            explanation = "Операция провалена — цель устояла."

        damage = int(attack.base_damage * multiplier) if success else int(attack.base_damage * 0.3)
        target.take_damage(damage)
        self.ip -= effective_cost

        attack_details = {
            'explanation': explanation,
            'lesson': lesson,
            'multiplier': round(multiplier, 2),
            'damage': damage,
            'affected_countries': []
        }

        # Раскрытие зависит от эффективности: точный удар оставляет меньше следов чем провал
        if success:
            reveal_delta = 3 if multiplier >= 1.5 else 6 if multiplier >= 1.0 else 11
        else:
            reveal_delta = 15
        _, alliance_note = self._get_alliance_defense(target, attack.attack_type)
        if alliance_note:
            reveal_delta += 3

        self.reveal = min(100, self.reveal + reveal_delta)

        if success:
            self.consecutive_failures = 0
            bonus = int(effective_cost * 0.30)
            self.ip += bonus
            msg = f"{attack.name} → {target_name}: -{damage} | +{bonus} IP | давление +{reveal_delta}"
            affected = self._spread_damage_with_tracking(target_name, damage)
            attack_details['affected_countries'] = affected
        else:
            self.consecutive_failures += 1
            penalty = int(effective_cost * 0.1)
            self.ip = max(0, self.ip - penalty)
            msg = f"{attack.name} → {target_name}: провал | -{penalty} IP | давление +{reveal_delta}"

        attack_details['reveal_delta'] = reveal_delta
        attack_details['reveal_now'] = self.reveal

        if self.reveal >= 100:
            self.game_over = True
            msg += " | Операция раскрыта — игра окончена"

        avg_health = sum(c.economic_health for c in self.countries.values()) / len(self.countries)
        if avg_health <= self.global_params['world_health_threshold']:
            self.game_over = True
            self.win = True

        return success, msg, attack_details

    def daily_update(self):
        # Продвигает игру на один день: списывает IP, снижает давление, обновляет здоровье стран.
        if self.game_over:
            return
        self.day += 1
        self.ip = max(0, self.ip - self.global_params['daily_maintenance_cost'])
        # Давление спадает само по себе — просто ждать тоже стратегия
        self.reveal = max(0, self.reveal - self.global_params.get('reveal_decay', 2))
        # Лимит квиза: 3 вопроса раз в 4 игровых дня
        if self.day >= self.quiz_reset_day + 4:
            self.quiz_today_count = 0
            self.quiz_reset_day = self.day

        for country in self.countries.values():
            h = country.economic_health
            if h > 60:
                # Активное восстановление — сложно удержать под ударом
                regen = self.global_params['recovery_rate_high']
                regen = int(regen * self._get_trade_bloc_multiplier(country))
                regen = int(regen * country.get_hdi_recovery_bonus())
                country.recover(max(1, regen))
            elif h > 40:
                # Медленное восстановление
                regen = self.global_params.get('recovery_rate_medium', 1)
                country.recover(regen)
            elif h > 20:
                # Стабильный упадок
                country.take_damage(1)
            else:
                # Каскадный коллапс ниже 20%
                country.take_damage(3)

        if self.reveal >= 100:
            self.game_over = True
        avg_health = sum(c.economic_health for c in self.countries.values()) / len(self.countries)
        if avg_health <= self.global_params['world_health_threshold']:
            self.game_over = True
            self.win = True

    def _reveal_level(self) -> str:
        if self.reveal < 40: return 'low'
        if self.reveal < 70: return 'medium'
        if self.reveal < 90: return 'high'
        return 'critical'

    def get_state(self) -> dict:
        # Собирает текущее состояние игры в словарь для отправки на фронтенд.
        avg_health = sum(c.economic_health for c in self.countries.values()) / len(self.countries)
        return {
            'ip': self.ip,
            'reveal': self.reveal,
            'reveal_level': self._reveal_level(),
            'quiz_remaining': max(0, 3 - self.quiz_today_count),
            'day': self.day,
            'game_over': self.game_over,
            'win': self.win,
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
                    'alliances': c.alliances,
                    'foreign_reserves': round(c.foreign_reserves, 1),
                    'human_development_index': c.human_development_index,
                    'corruption_perception_index': c.corruption_perception_index,
                    'external_debt_holders': c.external_debt_holders,
                    'energy_dependencies': c.energy_dependencies,
                    'trade_blocs': c.trade_blocs,
                }
                for c in self.countries.values()
            ],
            'attacks': [
                {
                    'name': a.name,
                    'cost': a.base_cost,
                    'damage': a.base_damage,
                    'min_damage': max(1, int(a.base_damage * min(
                        (v for v in a.multipliers.values() if isinstance(v, (int, float))), default=1.0
                    ))),
                    'max_damage': int(a.base_damage * max(
                        (v for v in a.multipliers.values() if isinstance(v, (int, float))), default=1.0
                    )),
                    'risk': a.base_risk,
                    'tooltip': a.tooltip
                }
                for a in self.attacks
            ],
        }

    def to_dict(self):
        # Сериализует состояние игры в словарь для сохранения в базе данных.
        return {
            'ip': self.ip,
            'reveal': self.reveal,
            'quiz_today_count': self.quiz_today_count,
            'quiz_reset_day': self.quiz_reset_day,
            'asked_quiz_ids': self.asked_quiz_ids,
            'consecutive_failures': self.consecutive_failures,
            'day': self.day,
            'game_over': self.game_over,
            'win': self.win,
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
                'initial_health': c.initial_health,
                'initial_inflation': c.initial_inflation,
                'initial_unemployment': c.initial_unemployment,
                'foreign_reserves': c.foreign_reserves,
                'human_development_index': c.human_development_index,
                'corruption_perception_index': c.corruption_perception_index,
                'external_debt_holders': c.external_debt_holders,
                'energy_dependencies': c.energy_dependencies,
                'trade_blocs': c.trade_blocs,
            } for c in self.countries.values()},
            'attacks': [a.__dict__ for a in self.attacks]
        }


    QUIZ_DAILY_LIMIT = 3

    def get_quiz_question(self) -> dict:
        # Выбирает случайный незаданный вопрос из пула. Возвращает ошибку если лимит исчерпан.
        if self.quiz_today_count >= self.QUIZ_DAILY_LIMIT:
            days_left = (self.quiz_reset_day + 4) - self.day
            return {'error': f'Лимит разведки исчерпан. Через {days_left} дн. откроется снова.'}
        pool = self._build_quiz_pool()
        unasked = [q for q in pool if q['question'] not in self.asked_quiz_ids]
        if len(unasked) < 2:
            self.asked_quiz_ids = []
            unasked = pool
        q = random.choice(unasked)
        self.asked_quiz_ids.append(q['question'])
        # Правильный ответ хранится на сервере — клиент его не видит до проверки
        self._quiz_answer = q['answer']
        self._quiz_explanation = q['explanation']
        self._quiz_reward = q['reward']
        return {
            'question': q['question'],
            'options': q['options'],
            'hint': q.get('hint', ''),
            'reward': q['reward'],
            'remaining': self.QUIZ_DAILY_LIMIT - self.quiz_today_count,
        }

    def submit_quiz_answer(self, answer: str) -> dict:
        # Проверяет ответ, начисляет IP и снижает давление при правильном ответе.
        if not self._quiz_answer:
            return {'error': 'Нет активного вопроса'}
        correct = answer.strip() == self._quiz_answer.strip()
        explanation = self._quiz_explanation
        reward = self._quiz_reward if correct else 0
        reveal_bonus = 0
        if correct:
            self.ip += reward
            reveal_bonus = -10
            self.reveal = max(0, self.reveal + reveal_bonus)
        self.quiz_today_count += 1
        self._quiz_answer = ""
        return {
            'correct': correct,
            'ip_gained': reward,
            'reveal_change': reveal_bonus,
            'explanation': explanation,
            'remaining': max(0, self.QUIZ_DAILY_LIMIT - self.quiz_today_count),
        }

    def _build_quiz_pool(self) -> list:
        pool = []

        # Динамический вопрос: наибольший долг относительно ВВП
        by_debt = sorted(self.countries.values(), key=lambda c: c.debt / c.gdp, reverse=True)
        others = [c.name for c in by_debt[3:]]
        opts = [by_debt[0].name] + random.sample(others, min(3, len(others)))
        random.shuffle(opts)
        pool.append({
            'question': 'Какая страна сейчас имеет наибольший долг относительно ВВП?',
            'options': opts[:4],
            'answer': by_debt[0].name,
            'reward': 200,
            'hint': 'Смотри колонку Долг/ВВП в Аналитике.',
            'explanation': (f"{by_debt[0].name}: долг {round(by_debt[0].debt / by_debt[0].gdp * 100)}% ВВП. "
                           "Это как ипотека больше годового дохода — каждый новый кредит стоит дороже."),
        })

        # Динамический вопрос: наибольшая зависимость от импорта энергии
        by_energy = sorted(self.countries.values(), key=lambda c: c.energy_import, reverse=True)
        if by_energy[0].energy_import > 0.3:
            others_e = [c.name for c in by_energy[3:]]
            opts_e = [by_energy[0].name] + random.sample(others_e, min(3, len(others_e)))
            random.shuffle(opts_e)
            pool.append({
                'question': 'Какая страна больше всего зависит от импорта энергии?',
                'options': opts_e[:4],
                'answer': by_energy[0].name,
                'reward': 180,
                'hint': 'Энергетический шантаж работает против стран с импортом >40%.',
                'explanation': (f"{by_energy[0].name} импортирует {round(by_energy[0].energy_import * 100)}% энергии. "
                               "Если поставки перекрыть, останавливаются заводы и растут цены на всё."),
            })

        # Динамический вопрос: страна в наихудшем экономическом состоянии
        weakest = min(self.countries.values(), key=lambda c: c.economic_health)
        if weakest.economic_health < 78:
            others_w = [c.name for c in sorted(self.countries.values(), key=lambda c: c.economic_health, reverse=True)[:5]]
            opts_w = [weakest.name] + random.sample(others_w, min(3, len(others_w)))
            random.shuffle(opts_w)
            pool.append({
                'question': 'Какая страна сейчас в наихудшем экономическом состоянии?',
                'options': opts_w[:4],
                'answer': weakest.name,
                'reward': 160,
                'hint': 'Ниже 20% — страна начинает разрушаться сама.',
                'explanation': (f"{weakest.name}: здоровье {weakest.economic_health}%. "
                               "Ниже 20% запускается автоматический коллапс — соседи тоже пострадают."),
            })

        # Static theory questions — 25 вопросов, охватывают разные темы макроэкономики
        pool += [
            {
                'question': 'Что происходит, когда государственный долг превышает 100% ВВП?',
                'options': ['Рост ускоряется', 'Инвесторы требуют более высокие ставки по облигациям', 'Экспорт увеличивается', 'Инфляция исчезает'],
                'answer': 'Инвесторы требуют более высокие ставки по облигациям',
                'reward': 180,
                'hint': 'Чем рискованнее заёмщик, тем дороже ему занимать.',
                'explanation': 'При долге >90% ВВП рынки считают страну ненадёжной и требуют более высокий процент. Долг растёт ещё быстрее — классическая долговая ловушка. Именно так Греция в 2010 году дошла до ставок в 25%.',
            },
            {
                'question': 'Почему большие золотовалютные резервы защищают страну от валютных атак?',
                'options': ['Страна может напечатать больше денег', 'Центробанк скупает нацвалюту и удерживает курс', 'Резервы увеличивают ВВП', 'Долг списывается автоматически'],
                'answer': 'Центробанк скупает нацвалюту и удерживает курс',
                'reward': 170,
                'hint': 'Резервы — это финансовый щит от спекулянтов.',
                'explanation': 'Когда спекулянты атакуют валюту, центробанк продаёт резервы и скупает нацвалюту. Без резервов курс рухнет мгновенно. Китай держит $3.2 трлн резервов именно для такой защиты.',
            },
            {
                'question': 'Почему кибератака опаснее всего для передовых цифровых экономик?',
                'options': ['У них нет армии', 'Их финансы и расчёты полностью зависят от IT-систем', 'Они производят больше товаров', 'У них нет резервов'],
                'answer': 'Их финансы и расчёты полностью зависят от IT-систем',
                'reward': 190,
                'hint': 'Парадокс: чем умнее экономика, тем уязвимее к цифровым ударам.',
                'explanation': 'США, Япония, Южная Корея — биржи, банки, расчёты работают через единые IT-сети. Атака на межбанковские системы может заморозить всю торговлю за часы. В 2021 году взлом Colonial Pipeline остановил 45% топливных поставок восточного побережья США.',
            },
            {
                'question': 'Что такое "эффект заражения" в макроэкономике?',
                'options': ['Болезнь населения', 'Кризис в одной стране распространяется на партнёров через торговлю и долги', 'Рост инфляции у соседей', 'Рост военных расходов'],
                'answer': 'Кризис в одной стране распространяется на партнёров через торговлю и долги',
                'reward': 150,
                'hint': 'Кризис 2008 в США → весь мир. Почему?',
                'explanation': 'Банки США держали ипотечные облигации. Когда они рухнули, европейские банки потеряли деньги, кредиты подорожали, торговля упала. Всё связано через финансовые цепочки — классический эффект домино.',
            },
            {
                'question': 'Что такое количественное смягчение (QE)?',
                'options': ['Повышение налогов', 'Центробанк печатает деньги и скупает гособлигации', 'Снижение таможенных пошлин', 'Списание внешнего долга'],
                'answer': 'Центробанк печатает деньги и скупает гособлигации',
                'reward': 160,
                'hint': 'QE — инструмент, который ФРС использовала после 2008 и COVID.',
                'explanation': 'При QE центробанк создаёт новые деньги и покупает облигации. Это снижает долгосрочные ставки и стимулирует кредитование. После 2008 ФРС влила в экономику свыше $3 трлн. Риск — разгон инфляции.',
            },
            {
                'question': 'В чём разница между дефицитом бюджета и государственным долгом?',
                'options': ['Это одно и то же', 'Дефицит — разрыв за один год, долг — накопленная сумма всех дефицитов', 'Долг — это дефицит умноженный на ВВП', 'Дефицит бывает только у бедных стран'],
                'answer': 'Дефицит — разрыв за один год, долг — накопленная сумма всех дефицитов',
                'reward': 150,
                'hint': 'Дефицит — это то, что не хватает за год. Долг — то, что накопилось за всё время.',
                'explanation': 'Дефицит бюджета — когда расходы больше доходов за год. Каждый год дефицита увеличивает общий долг. США имеют дефицит ~6% ВВП ежегодно, и именно поэтому их долг перевалил за 120% ВВП.',
            },
            {
                'question': 'Чем занимается МВФ (Международный валютный фонд)?',
                'options': ['Управляет мировой торговлей', 'Выдаёт кредиты странам в кризисе в обмен на экономические реформы', 'Регулирует курсы всех валют', 'Управляет золотым запасом ООН'],
                'answer': 'Выдаёт кредиты странам в кризисе в обмен на экономические реформы',
                'reward': 155,
                'hint': 'МВФ — "скорая помощь" для экономик, но с жёсткими условиями.',
                'explanation': 'МВФ спасал Грецию, Аргентину, Украину и другие страны. Кредиты выдаются при условии жёстких реформ: сокращение расходов, повышение налогов, либерализация экономики. Не все пациенты выживали.',
            },
            {
                'question': 'Почему высокая инфляция разрушает экономику?',
                'options': ['Потому что снижает экспорт', 'Потому что обесценивает сбережения и делает планирование невозможным', 'Потому что увеличивает государственный долг', 'Потому что снижает цены на нефть'],
                'answer': 'Потому что обесценивает сбережения и делает планирование невозможным',
                'reward': 145,
                'hint': 'Если цены растут на 50% в месяц, кто будет инвестировать?',
                'explanation': 'При высокой инфляции деньги теряют ценность быстрее, чем люди успевают их тратить. Бизнесы не могут планировать, сбережения сгорают, зарплаты не успевают расти. Турция в 2022 году: инфляция 80%, лира потеряла 40% за год.',
            },
            {
                'question': 'Что такое сравнительное преимущество в торговле?',
                'options': ['Страна экспортирует только то, что производит лучше всех в мире', 'Страна торгует тем, что производит с наименьшими относительными затратами', 'Крупные страны всегда выигрывают в торговле', 'Торговля выгодна только экспортёрам'],
                'answer': 'Страна торгует тем, что производит с наименьшими относительными затратами',
                'reward': 170,
                'hint': 'Рикардо объяснил: даже если ты хуже во всём, торговать всё равно выгодно.',
                'explanation': 'Даже если Китай производит всё дешевле США, им выгодно торговать: Китай специализируется на производстве, США — на технологиях и услугах. Каждый делает то, что у него получается относительно лучше.',
            },
            {
                'question': 'Что спровоцировало Азиатский финансовый кризис 1997 года?',
                'options': ['Война в Персидском заливе', 'Страны взяли огромные долги в долларах, а резервов не хватило защитить валюты', 'Падение цен на нефть', 'Эпидемия'],
                'answer': 'Страны взяли огромные долги в долларах, а резервов не хватило защитить валюты',
                'reward': 175,
                'hint': 'Таиланд, Индонезия, Южная Корея — у всех была одна и та же уязвимость.',
                'explanation': 'Таиланд, Индонезия и другие страны набрали долларовых долгов, рассчитывая на фиксированный курс. Когда спекулянты атаковали их валюты, резервов не хватило. Бат Таиланда рухнул вдвое, кризис перекинулся на весь регион.',
            },
            {
                'question': 'Что такое бегство капитала?',
                'options': ['Эмиграция богатых граждан', 'Массовый вывод денег из страны в кризисный период', 'Снижение иностранных инвестиций', 'Распродажа золотых резервов'],
                'answer': 'Массовый вывод денег из страны в кризисный период',
                'reward': 155,
                'hint': 'Когда инвесторы боятся потерять деньги, они их забирают.',
                'explanation': 'При нестабильности иностранные и местные инвесторы выводят деньги из страны. Валюта падает, процентные ставки растут, кредиты дорожают — и экономика входит в штопор. Россия потеряла $80 млрд за 2022 год.',
            },
            {
                'question': 'Что такое SWIFT и почему отключение от него критично?',
                'options': ['Торговая организация', 'Система межбанковских сообщений для международных переводов', 'Биржа ценных бумаг', 'Международный валютный резерв'],
                'answer': 'Система межбанковских сообщений для международных переводов',
                'reward': 165,
                'hint': 'Без SWIFT банки не могут отправлять деньги за рубеж.',
                'explanation': 'SWIFT соединяет более 11 000 банков в 200+ странах. Отключение = нельзя платить за импорт, получать деньги за экспорт, расплачиваться по долгам. В 2022 году Россия лишилась доступа к SWIFT, что осложнило все международные транзакции.',
            },
            {
                'question': 'Что такое стагфляция?',
                'options': ['Быстрый рост экономики', 'Одновременный рост инфляции и безработицы при стагнации ВВП', 'Дефляция плюс высокий рост', 'Рост ВВП без инфляции'],
                'answer': 'Одновременный рост инфляции и безработицы при стагнации ВВП',
                'reward': 170,
                'hint': 'Классический пример — США в 1970-х после нефтяного шока.',
                'explanation': 'Обычно инфляция и безработица движутся в разные стороны (кривая Филлипса). Стагфляция — исключение: экономика не растёт, но цены всё равно растут. В 1970-х нефтяной шок ОПЕК вызвал именно это в США и Европе.',
            },
            {
                'question': 'Зачем центральному банку нужна независимость от правительства?',
                'options': ['Чтобы устанавливать налоги', 'Чтобы не поддаваться давлению и не печатать деньги перед выборами', 'Чтобы управлять государственными расходами', 'Чтобы устанавливать таможенные пошлины'],
                'answer': 'Чтобы не поддаваться давлению и не печатать деньги перед выборами',
                'reward': 160,
                'hint': 'Политикам перед выборами всегда хочется "немного" напечатать денег.',
                'explanation': 'Если правительство контролирует центробанк, оно может печатать деньги для финансирования расходов. Это ведёт к инфляции. Независимый ЦБ может сказать "нет". Именно поэтому ФРС США и ЕЦБ юридически независимы от своих правительств.',
            },
            {
                'question': 'Что такое дефицит счёта текущих операций?',
                'options': ['Государство тратит больше, чем получает налогов', 'Страна покупает у мира больше, чем продаёт', 'Центробанк потратил больше резервов', 'Банки выдали больше кредитов, чем приняли депозитов'],
                'answer': 'Страна покупает у мира больше, чем продаёт',
                'reward': 155,
                'hint': 'Это как личный бюджет: тратишь больше, чем зарабатываешь.',
                'explanation': 'США хронически покупают у мира больше, чем продают — их дефицит около $800 млрд в год. Это означает, что доллары утекают за рубеж, а в страну поступают товары. Долгосрочный дефицит накапливает внешний долг.',
            },
            {
                'question': 'Что происходит с экономикой при дефолте государства?',
                'options': ['Автоматически улучшается', 'Потеря доступа к кредитам, коллапс валюты, падение уровня жизни', 'Снижается инфляция', 'Увеличивается ВВП'],
                'answer': 'Потеря доступа к кредитам, коллапс валюты, падение уровня жизни',
                'reward': 175,
                'hint': 'Аргентина объявляла дефолт 9 раз — и каждый раз это было болезненно.',
                'explanation': 'После дефолта страна теряет доверие кредиторов и не может брать новые займы. Валюта рушится, импорт дорожает, безработица растёт. Аргентина 2001: банки заморозили вклады, люди потеряли сбережения, страна получила пять президентов за неделю.',
            },
            {
                'question': 'Что означает индекс человеческого развития (ИЧР)?',
                'options': ['Только ВВП на душу населения', 'Комплексная оценка: доходы, образование и продолжительность жизни', 'Уровень коррупции в стране', 'Военный потенциал государства'],
                'answer': 'Комплексная оценка: доходы, образование и продолжительность жизни',
                'reward': 145,
                'hint': 'ИЧР придумал экономист Амартья Сен, чтобы не мерить развитие только деньгами.',
                'explanation': 'ИЧР = (здоровье + образование + доход) / 3. Норвегия — 0.96, Нигер — 0.4. Страны с высоким ИЧР быстрее восстанавливаются после кризисов: качественные институты, образованное население и медицина.',
            },
            {
                'question': 'Почему энергетическая зависимость от одной страны опасна?',
                'options': ['Потому что энергия дорожает', 'Поставщик получает политический рычаг и может шантажировать импортёра', 'Потому что нарушаются правила ВТО', 'Потому что снижается ВВП'],
                'answer': 'Поставщик получает политический рычаг и может шантажировать импортёра',
                'reward': 160,
                'hint': 'Германия зависела от российского газа на 55% — и это стоило ей дорого.',
                'explanation': 'В 2022 году Россия перекрыла газ Европе. Германия, Австрия и другие страны оказались заложниками одного поставщика. Цены на газ выросли в 15 раз. Диверсификация поставок — главный урок энергетической политики.',
            },
            {
                'question': 'Как высокая коррупция усиливает экономические кризисы?',
                'options': ['Никак не влияет', 'Деньги на антикризисные меры разворовываются, а госинституты не работают эффективно', 'Снижает государственный долг', 'Ускоряет восстановление'],
                'answer': 'Деньги на антикризисные меры разворовываются, а госинституты не работают эффективно',
                'reward': 165,
                'hint': 'Коррумпированное правительство не может эффективно реагировать на кризис.',
                'explanation': 'В коррумпированных странах антикризисные пакеты разворовываются, законы не исполняются, а доверие к власти низкое. Вместо стабилизации кризис углубляется. Именно поэтому индекс ИКВ ниже 35 усиливает урон от любой атаки.',
            },
            {
                'question': 'Что такое Бреттон-Вудская система и почему она важна?',
                'options': ['Военный альянс 1944 года', 'Послевоенный порядок, привязавший валюты к доллару и создавший МВФ и Всемирный банк', 'Торговое соглашение о нефти', 'Система распределения золота между странами'],
                'answer': 'Послевоенный порядок, привязавший валюты к доллару и создавший МВФ и Всемирный банк',
                'reward': 175,
                'hint': '1944 год — конференция в США, которая определила финансовый порядок на 30 лет.',
                'explanation': 'В 1944 году союзники создали новую систему: все валюты привязаны к доллару, доллар — к золоту ($35 за унцию). Также созданы МВФ и Всемирный банк. В 1971 году Никсон отменил золотую привязку — мир перешёл к плавающим курсам.',
            },
            {
                'question': 'Почему девальвация (обесценение) национальной валюты одновременно помогает экспорту и вредит импорту?',
                'options': ['Это невозможно одновременно', 'Экспорт дешевеет для иностранцев, а импорт дорожает для своих', 'Оба направления выигрывают', 'Оба направления проигрывают'],
                'answer': 'Экспорт дешевеет для иностранцев, а импорт дорожает для своих',
                'reward': 165,
                'hint': 'Слабая валюта — хорошо для заводов, плохо для магазинов.',
                'explanation': 'Если рубль падает, российские товары для иностранцев становятся дешевле — экспорт растёт. Но импортные товары дорожают для россиян. Поэтому страны-экспортёры иногда намеренно держат слабую валюту (как делал Китай).',
            },
            {
                'question': 'Что стало главной причиной кризиса 2008 года?',
                'options': ['Рост цен на нефть', 'Крах ипотечных ценных бумаг в США, которые держали банки по всему миру', 'Банкротство Японии', 'Торговая война США и Китая'],
                'answer': 'Крах ипотечных ценных бумаг в США, которые держали банки по всему миру',
                'reward': 170,
                'hint': 'Ипотека для ненадёжных заёмщиков + глобальные банки = мировой кризис.',
                'explanation': 'Американские банки выдавали ипотеки всем подряд и перепродавали их как ценные бумаги. Когда должники перестали платить, бумаги рухнули. Европейские банки держали эти бумаги и тоже потеряли деньги. Мировая торговля рухнула на 12% за один год.',
            },
            {
                'question': 'Почему торговые санкции неэффективны против стран с диверсифицированной торговлей?',
                'options': ['Потому что их защищает армия', 'Страна легко находит новых партнёров и перенаправляет торговые потоки', 'Потому что они богаче', 'Санкции вообще никогда не работают'],
                'answer': 'Страна легко находит новых партнёров и перенаправляет торговые потоки',
                'reward': 155,
                'hint': 'Если у тебя 20 покупателей и один уходит — ты не почувствуешь.',
                'explanation': 'Санкции работают, когда страна зависит от 1-2 рынков сбыта. Если торговля диверсифицирована, потеря одного партнёра компенсируется остальными. Россия переориентировалась на Азию после западных санкций, сохранив экспорт.',
            },
            {
                'question': 'Что измеряет ВВП и что он не учитывает?',
                'options': ['ВВП измеряет всё, включая счастье', 'ВВП считает рыночную стоимость товаров и услуг, но не учитывает неравенство и качество жизни', 'ВВП измеряет только промышленность', 'ВВП и ВНП — это одно и то же'],
                'answer': 'ВВП считает рыночную стоимость товаров и услуг, но не учитывает неравенство и качество жизни',
                'reward': 150,
                'hint': 'Страна может иметь высокий ВВП, но при этом огромное неравенство.',
                'explanation': 'ВВП — сумма всех товаров и услуг за год. Но он не считает, как распределено богатство, насколько чистый воздух, насколько счастливы люди. Поэтому и создали ИЧР: не всё можно измерить деньгами.',
            },
            {
                'question': 'Почему страны с высокой безработицей более уязвимы к социальным потрясениям?',
                'options': ['Безработные не платят налоги', 'Безработица создаёт армию недовольных людей, которых легко мобилизовать на протест', 'Снижается военный бюджет', 'Растёт государственный долг'],
                'answer': 'Безработица создаёт армию недовольных людей, которых легко мобилизовать на протест',
                'reward': 150,
                'hint': 'Человек без работы и денег злее, чем человек с работой.',
                'explanation': 'Безработные потеряли источник дохода и смысл занятости. Они более восприимчивы к протестным движениям и популистским лозунгам. В Испании и Греции в 2012-2015 годах безработица выше 25% привела к масштабным беспорядкам.',
            },
            {
                'question': 'Что такое ВВП на душу населения и почему он важнее общего ВВП?',
                'options': ['Это сумма всех зарплат в стране', 'Общий ВВП делённый на количество жителей — показывает реальный уровень жизни', 'Это ВВП без учёта экспорта', 'Это ВВП за вычетом государственного долга'],
                'answer': 'Общий ВВП делённый на количество жителей — показывает реальный уровень жизни',
                'reward': 140,
                'hint': 'Индия больше Швейцарии по общему ВВП, но Swiss люди живут намного богаче.',
                'explanation': 'Общий ВВП Индии больше швейцарского, но в Индии 1.4 млрд человек. ВВП на душу: Швейцария $85 000, Индия $2 500. Именно поэтому для сравнения уровня жизни используют показатель на душу населения.',
            },
            {
                'question': 'Что такое "голландская болезнь" в экономике?',
                'options': ['Эпидемия в Нидерландах', 'Когда добыча ресурсов разрушает другие отрасли экономики через укрепление валюты', 'Чрезмерные социальные расходы', 'Зависимость от туризма'],
                'answer': 'Когда добыча ресурсов разрушает другие отрасли экономики через укрепление валюты',
                'reward': 180,
                'hint': 'Нидерланды нашли газ в 1960-х — и почти потеряли всю промышленность.',
                'explanation': 'Когда страна начинает массово экспортировать ресурсы, её валюта укрепляется. Это делает все остальные товары дорогими для иностранцев — экспортёры теряют рынки. Нефтяные страны часто страдают от этого: нефть есть, а промышленности нет.',
            },
            {
                'question': 'Что такое кредитный рейтинг страны (AAA, BB и т.д.)?',
                'options': ['Оценка военной мощи', 'Оценка надёжности страны как заёмщика — насколько вероятен дефолт', 'Оценка качества жизни', 'Оценка размера экономики'],
                'answer': 'Оценка надёжности страны как заёмщика — насколько вероятен дефолт',
                'reward': 155,
                'hint': 'AAA — самый надёжный заёмщик, D — уже в дефолте.',
                'explanation': 'Агентства Moody\'s, S&P, Fitch оценивают насколько вероятно что страна не отдаст долги. AAA — США, Германия. BB и ниже — "мусорный" рейтинг, займы стоят значительно дороже. Снижение рейтинга сразу поднимает стоимость новых кредитов.',
            },
            {
                'question': 'Что произошло с Исландией в 2008 году?',
                'options': ['Вулкан уничтожил экономику', 'Три крупнейших банка страны обанкротились, долг достиг 900% ВВП', 'Страна вышла из ЕС', 'Упали цены на рыбу'],
                'answer': 'Три крупнейших банка страны обанкротились, долг достиг 900% ВВП',
                'reward': 170,
                'hint': 'Маленькая страна — огромные банки. Это и стало проблемой.',
                'explanation': 'Исландские банки раздулись до 900% ВВП страны, занимая деньги по всему миру. В 2008 году они рухнули — страна не могла их спасти. Исландия ввела контроль капитала и позволила банкам обанкротиться. Через 5 лет экономика восстановилась — это исключение из правил.',
            },
            {
                'question': 'Что такое суверенный фонд благосостояния?',
                'options': ['Пенсионный фонд для чиновников', 'Государственный инвестиционный фонд, копящий доходы от ресурсов для будущих поколений', 'Фонд помощи бедным странам', 'Резерв на случай войны'],
                'answer': 'Государственный инвестиционный фонд, копящий доходы от ресурсов для будущих поколений',
                'reward': 160,
                'hint': 'Норвегия скопила $1.7 трлн из нефтяных доходов — это больше $300 000 на каждого гражданина.',
                'explanation': 'Когда нефть или газ закончится, деньги останутся. Норвегский пенсионный фонд — крупнейший в мире, владеет долями в тысячах компаний по всему миру. Саудовская Аравия, ОАЭ, Сингапур тоже имеют такие фонды.',
            },
            {
                'question': 'Что такое "carry trade" в финансах?',
                'options': ['Перевозка товаров через границу', 'Берёшь кредит в стране с низкой ставкой и вкладываешь в страну с высокой ставкой', 'Торговля валютой на бирже', 'Перекладывание активов между банками'],
                'answer': 'Берёшь кредит в стране с низкой ставкой и вкладываешь в страну с высокой ставкой',
                'reward': 175,
                'hint': 'Берёшь в Японии под 0.1% — вкладываешь в Турции под 45%. Разница — твой доход.',
                'explanation': 'Именно это делают крупные инвесторы: занимают иены под почти нулевую ставку и покупают высокодоходные активы в других странах. Когда все начинают сворачивать эту стратегию одновременно — валюты развивающихся стран резко падают.',
            },
            {
                'question': 'Что такое Вашингтонский консенсус?',
                'options': ['Военный договор США', 'Набор экономических реформ — свободный рынок, приватизация, открытость торговли — которые МВФ требовал от кризисных стран', 'Соглашение о климате', 'Торговый договор стран Америки'],
                'answer': 'Набор экономических реформ — свободный рынок, приватизация, открытость торговли — которые МВФ требовал от кризисных стран',
                'reward': 165,
                'hint': '1980-90-е: МВФ давал деньги только если страна проводила эти реформы.',
                'explanation': 'МВФ и Всемирный банк требовали приватизировать госкомпании, снять торговые барьеры, сократить государственные расходы. Критики говорят, что это работало для богатых стран, но разрушило многие развивающиеся экономики.',
            },
            {
                'question': 'Что такое эффект мультипликатора в экономике?',
                'options': ['Рост цен из-за инфляции', 'Каждый вложенный в экономику рубль запускает цепочку расходов и создаёт больший суммарный эффект', 'Рост производства при снижении налогов', 'Увеличение денежной массы центробанком'],
                'answer': 'Каждый вложенный в экономику рубль запускает цепочку расходов и создаёт больший суммарный эффект',
                'reward': 155,
                'hint': 'Государство потратило 100 рублей — экономика выросла на 150-200.',
                'explanation': 'Государство платит строителям за дорогу. Строители тратят зарплату в магазинах. Магазины платят поставщикам. Каждый рубль проходит через несколько рук. Поэтому государственные расходы в кризис дают эффект больше суммы вложений.',
            },
            {
                'question': 'Почему центробанки таргетируют инфляцию в 2%?',
                'options': ['Это случайная цифра', 'Небольшая инфляция стимулирует расходы, оставляет пространство для снижения ставок и компенсирует ошибки измерения', 'Выше 2% запрещено законом', 'Такое требование ВТО'],
                'answer': 'Небольшая инфляция стимулирует расходы, оставляет пространство для снижения ставок и компенсирует ошибки измерения',
                'reward': 160,
                'hint': 'Нулевая инфляция — тоже плохо. Почему?',
                'explanation': 'При нулевой инфляции люди откладывают покупки — зачем платить сейчас, если завтра цены те же или ниже? Экономика замедляется. 2% — золотая середина: деньги работают, но не обесцениваются быстро. Это стандарт ФРС, ЕЦБ и большинства центробанков.',
            },
            {
                'question': 'Что случилось во время нефтяного эмбарго ОПЕК в 1973 году?',
                'options': ['Нефть закончилась физически', 'Арабские страны остановили поставки нефти на Запад — цены выросли в 4 раза, западные экономики погрузились в рецессию', 'США победили ОПЕК через санкции', 'Началась война за нефть'],
                'answer': 'Арабские страны остановили поставки нефти на Запад — цены выросли в 4 раза, западные экономики погрузились в рецессию',
                'reward': 165,
                'hint': 'Первый настоящий энергетический шок в истории.',
                'explanation': 'В ответ на поддержку Израиля арабские страны ОПЕК прекратили экспорт нефти в США и Европу. За несколько месяцев цена нефти выросла с $3 до $12. Очереди на заправках, рецессия, конец "экономического чуда" Европы. Именно тогда началось массовое изучение энергетической безопасности.',
            },
            {
                'question': 'Что такое долларизация экономики?',
                'options': ['Когда страна покупает много американских товаров', 'Когда страна официально или фактически использует доллар вместо своей валюты', 'Когда США влияют на экономику другой страны', 'Когда курс привязан к доллару'],
                'answer': 'Когда страна официально или фактически использует доллар вместо своей валюты',
                'reward': 150,
                'hint': 'Эквадор, Панама, Зимбабве отказались от собственных денег.',
                'explanation': 'После гиперинфляции Зимбабве в 2008 году (230 миллионов процентов!) страна перешла на доллар. Плюс — нет инфляции. Минус — нельзя печатать деньги в кризис и нет собственной монетарной политики. Это радикальное решение проблемы слабой валюты.',
            },
            {
                'question': 'Что такое дефляция и почему она опасна?',
                'options': ['Слишком медленная инфляция', 'Общее снижение цен — люди откладывают покупки, компании теряют выручку, экономика сжимается', 'Снижение государственных расходов', 'Укрепление национальной валюты'],
                'answer': 'Общее снижение цен — люди откладывают покупки, компании теряют выручку, экономика сжимается',
                'reward': 160,
                'hint': 'Япония 30 лет боролась с дефляцией. И проиграла.',
                'explanation': 'Если цены падают, люди ждут. Зачем покупать телевизор сейчас, если через месяц он будет дешевле? Компании продают меньше, режут зарплаты, увольняют. Люди тратят ещё меньше. Порочный круг. Именно в этой ловушке Япония провела "потерянное десятилетие" 1990-2000-х.',
            },
            {
                'question': 'Что такое реструктуризация долга?',
                'options': ['Полное списание долга', 'Переговоры с кредиторами об изменении условий — продлении сроков или снижении суммы — чтобы избежать дефолта', 'Продажа долга другому кредитору', 'Выпуск новых облигаций'],
                'answer': 'Переговоры с кредиторами об изменении условий — продлении сроков или снижении суммы — чтобы избежать дефолта',
                'reward': 155,
                'hint': 'Лучше получить меньше, чем не получить ничего.',
                'explanation': 'Когда страна не может платить, она договаривается с кредиторами. Греция в 2012 году списала 50% долга перед частными кредиторами — крупнейшая реструктуризация в истории. Кредиторы согласились, потому что полный дефолт принёс бы им ещё большие потери.',
            },
            {
                'question': 'Что такое счёт текущих операций в балансе платежей?',
                'options': ['Баланс расходов и доходов государственного бюджета', 'Разница между тем, что страна получила от внешнего мира и тем, что заплатила — товары, услуги, доходы', 'Сумма всех банковских вкладов', 'Торговый оборот с соседями'],
                'answer': 'Разница между тем, что страна получила от внешнего мира и тем, что заплатила — товары, услуги, доходы',
                'reward': 160,
                'hint': 'Профицит — страна зарабатывает больше, чем тратит на мировом рынке.',
                'explanation': 'Германия и Китай — профицит (зарабатывают больше). США и Великобритания — дефицит (тратят больше, чем получают). Хронический дефицит означает что страна живёт в долг у остального мира. Это устойчиво, пока есть доверие к экономике.',
            },
            {
                'question': 'Почему рост цен на энергию разгоняет инфляцию во всей экономике?',
                'options': ['Только цены на бензин растут', 'Энергия входит в себестоимость практически всех товаров и услуг — дороже энергия, дороже всё', 'Потребители паникуют и скупают всё подряд', 'Центробанки печатают больше денег'],
                'answer': 'Энергия входит в себестоимость практически всех товаров и услуг — дороже энергия, дороже всё',
                'reward': 150,
                'hint': 'Транспорт, производство, отопление — всё требует энергии.',
                'explanation': 'Когда дорожает газ, растут расходы заводов на производство, магазинов на отопление, транспорта на перевозку. Это называется инфляция издержек. В 2022 году рост цен на энергию в Европе дал 8-10% инфляции — максимум за 40 лет.',
            },
            {
                'question': 'Что такое фискальная политика государства?',
                'options': ['Политика центробанка по ставкам', 'Управление государственными расходами и налогами для влияния на экономику', 'Политика в области торговых тарифов', 'Управление валютными резервами'],
                'answer': 'Управление государственными расходами и налогами для влияния на экономику',
                'reward': 145,
                'hint': 'В отличие от монетарной политики, это инструмент правительства, а не центробанка.',
                'explanation': 'В кризис государство может увеличить расходы (строить дороги, выплачивать пособия) или снизить налоги — чтобы стимулировать спрос. В период перегрева экономики наоборот — повысить налоги. США потратили $5 трлн на стимулирование во время COVID.',
            },
            {
                'question': 'Что произошло с Аргентиной в 2001 году?',
                'options': ['Военный переворот обрушил экономику', 'Аргентина объявила дефолт на $95 млрд, заморозила вклады, сменила пять президентов за неделю', 'Землетрясение уничтожило промышленность', 'МВФ принудительно списал долги'],
                'answer': 'Аргентина объявила дефолт на $95 млрд, заморозила вклады, сменила пять президентов за неделю',
                'reward': 170,
                'hint': 'Крупнейший дефолт в истории на тот момент.',
                'explanation': 'Аргентина жила с фиксированным курсом песо к доллару, накапливая долги. Когда резервы кончились, страна объявила дефолт. Банки заморозили счета — люди не могли снять свои деньги. Начались погромы. За одну неделю сменилось пять президентов. Урок: фиксированный курс без резервов — путь к катастрофе.',
            },
            {
                'question': 'Что такое режим свободно плавающего обменного курса?',
                'options': ['Курс устанавливает государство каждую неделю', 'Курс определяется спросом и предложением на валютном рынке без вмешательства государства', 'Курс привязан к корзине валют', 'Курс меняется только раз в год'],
                'answer': 'Курс определяется спросом и предложением на валютном рынке без вмешательства государства',
                'reward': 150,
                'hint': 'Большинство крупных экономик сейчас используют именно этот режим.',
                'explanation': 'Доллар, евро, иена — все плавающие. Если экономика слабеет, валюта падает автоматически — это делает экспорт дешевле и помогает восстановлению. Фиксированный курс лишает экономику этого буфера. Именно поэтому фиксированные режимы часто заканчиваются кризисами.',
            },
            {
                'question': 'Почему снижение ключевой ставки центробанка стимулирует экономику?',
                'options': ['Государство получает больше налогов', 'Кредиты дешевеют, бизнес берёт займы и инвестирует, потребители берут ипотеку — спрос растёт', 'Государство может больше тратить', 'Инфляция автоматически снижается'],
                'answer': 'Кредиты дешевеют, бизнес берёт займы и инвестирует, потребители берут ипотеку — спрос растёт',
                'reward': 150,
                'hint': 'После 2008 ФРС снизила ставку почти до нуля. Почему?',
                'explanation': 'Ключевая ставка — цена денег для банков. Банки снижают ставки по кредитам. Компании берут займы на расширение, люди на ипотеку. Экономика оживает. Обратная сторона: слишком дешёвые деньги надувают пузыри на рынках — как это случилось перед кризисом 2008 года.',
            },
            {
                'question': 'Что такое ВТО и зачем она нужна?',
                'options': ['Военный альянс торговых государств', 'Международная организация, устанавливающая правила мировой торговли и разрешающая споры между странами', 'Организация нефтяных экспортёров', 'Финансовый регулятор банков'],
                'answer': 'Международная организация, устанавливающая правила мировой торговли и разрешающая споры между странами',
                'reward': 145,
                'hint': 'Без ВТО каждая страна могла бы ставить любые таможенные барьеры.',
                'explanation': 'ВТО создана в 1995 году. Она следит чтобы страны не вводили произвольные пошлины и торговые барьеры. При споре (например, США обвиняют Китай в субсидировании) дело рассматривает комиссия ВТО. Россия вступила в ВТО в 2012 году после 18 лет переговоров.',
            },
            {
                'question': 'Почему высокий внешний долг в иностранной валюте особенно опасен?',
                'options': ['Иностранцы берут большие проценты', 'Если национальная валюта упадёт, долг в пересчёте на неё вырастет автоматически — страна может не справиться', 'Иностранные кредиторы менее терпеливы', 'Это запрещено международным правом'],
                'answer': 'Если национальная валюта упадёт, долг в пересчёте на неё вырастет автоматически — страна может не справиться',
                'reward': 175,
                'hint': 'Таиланд 1997: бат упал вдвое — долларовый долг удвоился в батах.',
                'explanation': 'Если страна должна $100 млрд, а её валюта упала вдвое, то в пересчёте на местную валюту долг удвоился — хотя в долларах остался тем же. Именно это убило Таиланд и Индонезию в 1997 году. Поэтому эксперты рекомендуют странам занимать в своей валюте.',
            },
        ]
        return pool

    @classmethod
    def from_dict(cls, data):
        # Восстанавливает объект игры из словаря, сохранённого в базе данных.
        instance = cls.__new__(cls)
        instance.ip = data['ip']
        instance.reveal = data.get('reveal', 0)
        instance.quiz_today_count = data.get('quiz_today_count', 0)
        instance.quiz_reset_day = data.get('quiz_reset_day', 0)
        instance.asked_quiz_ids = data.get('asked_quiz_ids', [])
        instance.consecutive_failures = data.get('consecutive_failures', 0)
        instance.day = data['day']
        instance.game_over = data['game_over']
        instance.win = data['win']
        instance.global_params = data['global_params']
        instance.connections = []
        instance._quiz_answer = ""
        instance._quiz_explanation = ""
        instance._quiz_reward = 0

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
                'energy_export': cdata.get('energy_export', 0),
                'foreign_reserves_usd_billion': cdata.get('foreign_reserves', 100),
                'human_development_index': cdata.get('human_development_index', 0.7),
                'corruption_perception_index': cdata.get('corruption_perception_index', 50),
                'external_debt_holders': cdata.get('external_debt_holders', {}),
                'energy_dependencies': cdata.get('energy_dependencies', {}),
                'trade_blocs': cdata.get('trade_blocs', []),
            })
            c.initial_health = cdata['initial_health']
            # Восстанавливаем начальные значения; если сохранение старое — берём текущие
            c.initial_inflation = cdata.get('initial_inflation', cdata['inflation'])
            c.initial_unemployment = cdata.get('initial_unemployment', cdata['unemployment'])
            instance.countries[name] = c

        instance.attacks = [Attack(a) for a in data['attacks']]
        instance._build_connection_graph()
        return instance