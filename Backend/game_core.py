# =============================================================================
# game_core.py — игровой движок World Economic Simulator
# Содержит: классы Country, Attack, EconomicConnection и основной класс GlobalEconomyGame
# Все игровые расчёты (атаки, распространение кризиса, квиз) находятся здесь
# =============================================================================

import json
import random
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from lessons import LESSONS

@dataclass
class EconomicConnection:
    """Представляет экономическую связь между двумя странами"""
    from_country: str
    to_country: str
    connection_type: str  # 'trade', 'debt', 'energy'
    strength: float  # 0-1, сила связи
    data: dict  # дополнительные параметры

# -----------------------------------------------------------------------------
# Country — модель одной страны с её экономическими показателями
# Данные загружаются из balance.json; методы take_damage/recover меняют здоровье
# -----------------------------------------------------------------------------
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
        # Начальные значения — нижняя граница при восстановлении
        self.initial_inflation = data['inflation']
        self.initial_unemployment = data['unemployment']
        
        # НОВЫЕ ПОКАЗАТЕЛИ
        self.foreign_reserves = data.get('foreign_reserves_usd_billion', 100)
        self.human_development_index = data.get('human_development_index', 0.7)
        self.corruption_perception_index = data.get('corruption_perception_index', 50)
        self.central_bank_rate = data.get('central_bank_rate', 5.0)
        self.manufacturing_value_added_pct = data.get('manufacturing_value_added_pct', 15.0)
        self.current_account_balance_pct = data.get('current_account_balance_pct', 0.0)
        
        # НОВЫЕ ТИПЫ СВЯЗЕЙ
        self.external_debt_holders = data.get('external_debt_holders', {})
        self.energy_dependencies = data.get('energy_dependencies', {})
        self.trade_blocs = data.get('trade_blocs', [])
        
        # Флаги для механик
        self.sanctions_experience = False  # Были ли уже санкции
        self.capital_controls = False  # Введены ли ограничения на движение капитала

    def take_damage(self, damage: int, multiplier: float = 1.0):
        effective = int(damage * multiplier)
        self.economic_health = max(0, self.economic_health - effective)
        if effective > 0:
            self.unemployment = min(40, self.unemployment + effective / 20)
            self.inflation = min(50, self.inflation + effective / 25)
            
            # Урон влияет на резервы (чем больше урон, тем больше тратим резервов)
            if self.foreign_reserves > 0:
                reserve_loss = effective * 0.5  # 50% урона идёт из резервов
                self.foreign_reserves = max(0, self.foreign_reserves - reserve_loss)

    def recover(self, amount: int):
        self.economic_health = min(self.initial_health, self.economic_health + amount)
        # Не опускаем ниже начальных значений — нельзя «вылечить» страну до нуля
        self.unemployment = max(self.initial_unemployment, self.unemployment - amount / 30)
        self.inflation = max(self.initial_inflation, self.inflation - amount / 40)
        
        # Восстановление влияет на резервы (чем выше ИЧР, тем быстрее восстанавливаются)
        if self.human_development_index > 0.8:
            self.foreign_reserves = min(self.foreign_reserves + amount * 0.3, 5000)

    def is_collapsed(self) -> bool:
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
    def __init__(self, data: dict):
        self.name = data['name']
        self.base_cost = data['base_cost']
        self.base_damage = data['base_damage']
        self.base_risk = data['base_risk']
        self.attack_type = data['attack_type']
        self.tooltip = data.get('tooltip', '')
        self.multipliers = data.get('multipliers', {})

# -----------------------------------------------------------------------------
# GlobalEconomyGame — центральный класс игры
# Хранит состояние всех стран, обрабатывает атаки, тики дней и квиз
# Сохраняется в SQLite через методы to_dict() / from_dict()
# -----------------------------------------------------------------------------
class GlobalEconomyGame:
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

    # Alliance damage reduction per attack type
    # Models real-world collective defense / economic solidarity mechanisms
    ALLIANCE_DEFENSE = {
        'G7': {
            'currency_crisis': 0.70,  # IMF emergency loans, G7 currency coordination
            'debt_spiral': 0.72,       # G7 can rescue members via bailout packages
        },
        'ЕС': {
            'energy_embargo': 0.62,    # EU energy solidarity regulation, joint gas reserves
            'trade_blockade': 0.80,    # EU single market provides alternative channels
        },
        'БРИКС': {
            'trade_blockade': 0.85,    # BRICS alternative trade routes and markets
        },
        'Five Eyes': {
            'cyber_attack': 0.38,      # Joint cybersecurity intelligence sharing
        },
        'НАТО': {
            'social_unrest': 0.82,     # Democratic institutional resilience
        },
        'ШОС': {
            'social_unrest': 0.90,     # Political stability mechanisms
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
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.countries: Dict[str, Country] = {}
        for cdata in data['countries']:
            c = Country(cdata)
            self.countries[c.name] = c
        self.attacks: List[Attack] = [Attack(a) for a in data['attacks']]
        self.global_params = data['global_params']
        self.economic_lessons = data.get('economic_lessons', {})

        self.ip = 1000
        self.reveal = 0          # 0–100: давление на операцию
        self.day = 0
        self.game_over = False
        self.win = False
        self.last_event = ""
        self.last_lesson = None
        self.connections: List[EconomicConnection] = []
        self._build_connection_graph()
        self.discovered_laws: set = set()
        self._quiz_answer: str = ""
        self._quiz_explanation: str = ""
        self._quiz_reward: int = 0
        self.quiz_today_count: int = 0   # сколько раз уже отвечали сегодня
        self.quiz_reset_day: int = 0     # день, когда был последний сброс
        self.asked_quiz_ids: list = []   # вопросы, уже заданные в этой сессии

    def _build_connection_graph(self):
        """Строит граф экономических связей между странами"""
        for country in self.countries.values():
            # Торговые связи
            for partner, share in country.trade_partners.items():
                if partner in self.countries:
                    self.connections.append(EconomicConnection(
                        country.name, partner, 'trade', share, {}
                    ))
            
            # Долговые связи
            for creditor, amount in country.external_debt_holders.items():
                if creditor in self.countries:
                    # Нормализуем сумму (делим на 1000 для получения доли)
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
                    'currency_crisis': f"{name}: МВФ готов предоставить экстренные кредиты",
                    'debt_spiral': f"{name}: союзники организуют пакет финансовой помощи",
                    'energy_embargo': f"{name}: действует режим энергетической солидарности",
                    'trade_blockade': f"{name}: альтернативные рынки снижают зависимость",
                    'social_unrest': f"{name}: демократические институты сдерживают протесты",
                    'cyber_attack': f"{name}: совместная разведка кибер-угроз",
                }.get(attack_type, f"{name}: союзники оказывают поддержку")
                notes.append(mechanism)
        return best_mult, "; ".join(notes)

    def _get_attack_multiplier_and_explanation(self, attack: Attack, country: Country) -> Tuple[float, str, str]:
        """Возвращает (множитель, объяснение успеха/неудачи, образовательный урок)"""
        mult = 1.0
        explanation = ""
        lesson = ""

        # ── 1. ВАЛЮТНАЯ АТАКА ──────────────────────────────────────────────
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

        # ── 2. ДОЛГОВАЯ СПИРАЛЬ ────────────────────────────────────────────
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

        # ── 3. ТОРГОВЫЕ САНКЦИИ ────────────────────────────────────────────
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

        # ── 4. ЭНЕРГЕТИЧЕСКИЙ ШАНТАЖ ───────────────────────────────────────
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

        # ── 5. СОЦИАЛЬНЫЙ ВЗРЫВ ────────────────────────────────────────────
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

        # ── 6. КИБЕРАТАКА ──────────────────────────────────────────────────
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

        # ── Коррупция усиливает урон (кроме кибератак — там отдельная логика) ──
        if attack.attack_type not in ['cyber_attack', 'social_unrest']:
            corruption_mult = country.get_corruption_multiplier()
            if corruption_mult > 1.0:
                mult *= corruption_mult
                explanation += f" Коррупция (ИКВ {country.corruption_perception_index}) усилила урон."

        # ── Резервы защищают при финансовых атаках ──────────────────────────
        if attack.attack_type in ['currency_crisis', 'debt_spiral']:
            reserve_protection = country.get_reserve_protection()
            if reserve_protection < 1.0:
                mult *= reserve_protection

        # ── Защита альянсов ─────────────────────────────────────────────────
        alliance_mult, alliance_note = self._get_alliance_defense(country, attack.attack_type)
        if alliance_mult < 1.0:
            mult *= alliance_mult
            explanation += f" | 🛡️ {alliance_note} (×{alliance_mult:.2f})."

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
            
            # 1. Распространение через альянсы (30% урона союзникам)
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
            
            # 2. Распространение через долговые связи
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
            
            # 3. Распространение через торговые, долговые и энергетические связи
            relevant_connections = [
                c for c in self.connections 
                if c.from_country == curr_name and c.to_country not in visited
            ]
            
            for conn in relevant_connections:
                if conn.connection_type == 'trade':
                    transfer = int(damage * conn.strength * self.global_params['contagion_factor'] * factor)
                elif conn.connection_type == 'debt':
                    transfer = int(damage * conn.strength * 0.5 * factor)
                    if transfer > 5 and conn.to_country in self.countries:
                        creditor = self.countries[conn.to_country]
                        if creditor.debt > creditor.gdp * 0.9:
                            transfer = int(transfer * 1.5)
                elif conn.connection_type == 'energy':
                    transfer = int(damage * conn.strength * 0.6 * factor)
                else:
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

    # -------------------------------------------------------------------------
    # apply_attack — главная игровая функция
    # Принимает имя атаки и цели, рассчитывает урон с учётом всех множителей,
    # списывает IP, обновляет раскрытие и распространяет кризис по графу связей
    # -------------------------------------------------------------------------
    def apply_attack(self, attack_name: str, target_name: str) -> Tuple[bool, str, dict]:
        if self.game_over:
            return False, "Игра окончена", {}

        attack = next(a for a in self.attacks if a.name == attack_name)
        target = self.countries[target_name]
        cost = int(attack.base_cost * target.weight)
        if self.ip < cost:
            return False, f"Недостаточно очков влияния (нужно {cost})", {}

        success = random.randint(1, 100) <= 62

        multiplier, explanation, lesson = self._get_attack_multiplier_and_explanation(attack, target)
        if not success:
            multiplier = 0.3
            explanation = "Операция провалена — цель устояла."

        # ── Стоимость с учётом давления ────────────────────────────────────────
        reveal_cost_mult = 1.0
        if self.reveal >= 70:
            reveal_cost_mult = 1.30
        elif self.reveal >= 40:
            reveal_cost_mult = 1.15
        effective_cost = int(cost * reveal_cost_mult)
        if self.ip < effective_cost:
            return False, f"Недостаточно очков влияния (нужно {effective_cost}, есть {self.ip})", {}

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

        # ── Reveal: растёт от плохих/шумных операций ───────────────────────────
        # Эффективная атака (mult ≥ 1.5): +3  — чистый удар, мало следов
        # Нормальная атака  (mult 1–1.5):  +6
        # Неэффективная     (mult < 1):    +11 — много шума, мало результата
        # Провал:                          +15 — спалились
        # Защищённая цель (альянс):        +3  — сложная цель, больше следов
        if success:
            reveal_delta = 3 if multiplier >= 1.5 else 6 if multiplier >= 1.0 else 11
        else:
            reveal_delta = 15
        _, alliance_note = self._get_alliance_defense(target, attack.attack_type)
        if alliance_note:
            reveal_delta += 3

        self.reveal = min(100, self.reveal + reveal_delta)

        if success:
            bonus = int(effective_cost * 0.30)
            self.ip += bonus
            msg = f"{attack.name} → {target_name}: -{damage} | +{bonus} IP | давление +{reveal_delta}"
            affected = self._spread_damage_with_tracking(target_name, damage)
            attack_details['affected_countries'] = affected
            if lesson:
                self.last_lesson = lesson
        else:
            penalty = int(effective_cost * 0.1)
            self.ip = max(0, self.ip - penalty)
            msg = f"{attack.name} → {target_name}: провал | -{penalty} IP | давление +{reveal_delta}"

        # Добавляем в details информацию о давлении
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

    def _check_economic_laws(self, attack: Attack, target: Country, damage: int) -> Optional[str]:
        """Проверяет, не проявился ли какой-то экономический закон, и возвращает урок"""
        lessons = []
        
        # Эффект домино
        if damage > 10:
            affected_partners = [c for c in self.countries.values() 
                               if c.name != target.name and c.economic_health < target.economic_health]
            if len(affected_partners) >= 2:
                lessons.append("ЭФФЕКТ ДОМИНО: Кризис распространился на торговых партнёров!")
        
        # Долговая ловушка
        if target.debt > target.gdp * 0.9 and attack.attack_type in ['финансовая', 'санкции']:
            lessons.append("ДОЛГОВАЯ ЛОВУШКА: Высокий долг усугубил кризис!")
        
        # Энергетическая уязвимость
        if target.energy_import > 0.4 and attack.attack_type == 'энергетическая':
            lessons.append("ЭНЕРГЕТИЧЕСКАЯ УЯЗВИМОСТЬ: Зависимость от импорта энергии усилила урон!")
        
        # Бегство капитала
        if target.foreign_reserves < 200 and attack.attack_type in ['финансовая', 'санкции']:
            lessons.append("БЕГСТВО КАПИТАЛА: Низкие резервы не смогли защитить экономику!")
        
        if lessons:
            return " ".join(lessons)
        return None

    # -------------------------------------------------------------------------
    # daily_update — тик игрового дня (вызывается каждые 10 секунд реального времени)
    # Списывает IP за обслуживание, снижает раскрытие, восстанавливает/разрушает страны
    # и с вероятностью 20% запускает случайное экономическое событие
    # -------------------------------------------------------------------------
    def daily_update(self):
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
                # Зона 60–100: активное восстановление — сложно удержать под ударом
                regen = self.global_params['recovery_rate_high']  # = 3
                bloc_mult = self._get_trade_bloc_multiplier(country)
                regen = int(regen * bloc_mult)
                regen = int(regen * country.get_hdi_recovery_bonus())
                country.recover(max(1, regen))
            elif h > 40:
                # Зона 40–60: медленное восстановление — "тянут из болота"
                regen = self.global_params.get('recovery_rate_medium', 1)
                country.recover(regen)
            elif h > 20:
                # Зона 20–40: стабильный упадок
                country.take_damage(1)
            else:
                # Ниже 20%: каскадный коллапс
                country.take_damage(3)

        if random.random() < 0.2:
            self._trigger_random_event()

        if self.reveal >= 100:
            self.game_over = True
            self.last_event = "Операция раскрыта"
        avg_health = sum(c.economic_health for c in self.countries.values()) / len(self.countries)
        if avg_health <= self.global_params['world_health_threshold']:
            self.game_over = True
            self.win = True
            self.last_event = "Глобальный коллапс"

    def _trigger_random_event(self):
        events = [
            ("Финансовая поддержка", lambda: setattr(self, 'ip', self.ip + 150)),
            ("Пандемия", lambda: [c.take_damage(int(c.economic_health * 0.05)) for c in self.countries.values()]),
            ("Банковский кризис", lambda: [c.take_damage(int(c.economic_health * 0.03)) for c in self.countries.values()]),
            ("Нефтяной шок", lambda: [c.take_damage(8) for c in self.countries.values() if c.energy_import > 0.4]),
            ("Природная катастрофа", lambda: random.choice(list(self.countries.values())).take_damage(12)),
            ("Глобальная рецессия", lambda: [c.take_damage(5) for c in self.countries.values() if c.economic_health > 50]),
            ("Торговое соглашение", lambda: [c.recover(5) for c in self.countries.values() if c.export_oriented]),
            ("Долговой кризис", lambda: self._debt_crisis_event()),
            ("Бегство капитала", lambda: self._capital_flight_event()),
        ]
        name, effect = random.choice(events)
        effect()
        self.last_event = name

    def _debt_crisis_event(self):
        """Событие: долговой кризис в случайной стране с высоким долгом"""
        high_debt_countries = [c for c in self.countries.values() if c.debt > c.gdp * 0.9]
        if high_debt_countries:
            victim = random.choice(high_debt_countries)
            victim.take_damage(15)
            self.last_event = f"💸 Долговой кризис в {victim.name}!"

    def _capital_flight_event(self):
        """Событие: бегство капитала из страны с низкими резервами"""
        low_reserve_countries = [c for c in self.countries.values() if c.foreign_reserves < 200]
        if low_reserve_countries:
            victim = random.choice(low_reserve_countries)
            victim.take_damage(10)
            self.last_event = f"📉 Бегство капитала из {victim.name}!"

    def _reveal_level(self) -> str:
        if self.reveal < 40: return 'low'
        if self.reveal < 70: return 'medium'
        if self.reveal < 90: return 'high'
        return 'critical'

    def get_state(self) -> dict:
        avg_health = sum(c.economic_health for c in self.countries.values()) / len(self.countries)
        return {
            'ip': self.ip,
            'reveal': self.reveal,
            'reveal_level': self._reveal_level(),
            'quiz_remaining': max(0, 3 - self.quiz_today_count),
            'day': self.day,
            'game_over': self.game_over,
            'win': self.win,
            'last_event': self.last_event,
            'last_lesson': self.last_lesson,
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
                    # НОВЫЕ ПОКАЗАТЕЛИ
                    'foreign_reserves': round(c.foreign_reserves, 1),
                    'human_development_index': c.human_development_index,
                    'corruption_perception_index': c.corruption_perception_index,
                    'central_bank_rate': c.central_bank_rate,
                    'manufacturing_value_added_pct': c.manufacturing_value_added_pct,
                    'current_account_balance_pct': round(c.current_account_balance_pct, 1),
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
                    'risk': a.base_risk,
                    'tooltip': a.tooltip
                }
                for a in self.attacks
            ],
            'economic_lessons': self.economic_lessons
        }

    def to_dict(self):
        return {
            'ip': self.ip,
            'reveal': self.reveal,
            'quiz_today_count': self.quiz_today_count,
            'quiz_reset_day': self.quiz_reset_day,
            'asked_quiz_ids': self.asked_quiz_ids,
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
                'initial_health': c.initial_health,
                'initial_inflation': c.initial_inflation,
                'initial_unemployment': c.initial_unemployment,
                # НОВЫЕ ПОКАЗАТЕЛИ
                'foreign_reserves': c.foreign_reserves,
                'human_development_index': c.human_development_index,
                'corruption_perception_index': c.corruption_perception_index,
                'central_bank_rate': c.central_bank_rate,
                'manufacturing_value_added_pct': c.manufacturing_value_added_pct,
                'current_account_balance_pct': c.current_account_balance_pct,
                'external_debt_holders': c.external_debt_holders,
                'energy_dependencies': c.energy_dependencies,
                'trade_blocs': c.trade_blocs,
                'sanctions_experience': c.sanctions_experience,
            } for c in self.countries.values()},
            'attacks': [a.__dict__ for a in self.attacks]
        }

    # ─── Quiz system ───────────────────────────────────────────────────────

    QUIZ_DAILY_LIMIT = 3

    def get_quiz_question(self) -> dict:
        """Generate a question. Returns error if daily limit reached."""
        if self.quiz_today_count >= self.QUIZ_DAILY_LIMIT:
            days_left = (self.quiz_reset_day + 4) - self.day
            return {'error': f'Лимит разведки исчерпан. Через {days_left} дн. откроется снова.'}
        pool = self._build_quiz_pool()
        # Фильтруем уже заданные вопросы, чтобы не повторялись
        unasked = [q for q in pool if q['question'] not in self.asked_quiz_ids]
        if len(unasked) < 2:
            # Все вопросы пройдены — сбрасываем историю
            self.asked_quiz_ids = []
            unasked = pool
        q = random.choice(unasked)
        self.asked_quiz_ids.append(q['question'])
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
        if not self._quiz_answer:
            return {'error': 'Нет активного вопроса'}
        correct = answer.strip() == self._quiz_answer.strip()
        explanation = self._quiz_explanation
        reward = self._quiz_reward if correct else 0
        reveal_bonus = 0
        if correct:
            self.ip += reward
            # Правильный ответ снижает давление — разведка помогает прикрыть следы
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

        # Dynamic: highest debt
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

        # Dynamic: most energy-dependent importer
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

        # Dynamic: weakest country
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
        ]
        return pool

    @classmethod
    def from_dict(cls, data):
        instance = cls.__new__(cls)
        instance.ip = data['ip']
        instance.reveal = data.get('reveal', 0)
        instance.quiz_today_count = data.get('quiz_today_count', 0)
        instance.quiz_reset_day = data.get('quiz_reset_day', 0)
        instance.asked_quiz_ids = data.get('asked_quiz_ids', [])
        instance.day = data['day']
        instance.game_over = data['game_over']
        instance.win = data['win']
        instance.last_event = data.get('last_event', '')
        instance.global_params = data['global_params']
        instance.economic_lessons = data.get('economic_lessons', {})
        instance.last_lesson = data.get('last_lesson', None)
        instance.connections = []
        instance.discovered_laws = set()
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
                # НОВЫЕ ПОКАЗАТЕЛИ
                'foreign_reserves_usd_billion': cdata.get('foreign_reserves', 100),
                'human_development_index': cdata.get('human_development_index', 0.7),
                'corruption_perception_index': cdata.get('corruption_perception_index', 50),
                'central_bank_rate': cdata.get('central_bank_rate', 5.0),
                'manufacturing_value_added_pct': cdata.get('manufacturing_value_added_pct', 15.0),
                'current_account_balance_pct': cdata.get('current_account_balance_pct', 0.0),
                'external_debt_holders': cdata.get('external_debt_holders', {}),
                'energy_dependencies': cdata.get('energy_dependencies', {}),
                'trade_blocs': cdata.get('trade_blocs', []),
            })
            c.initial_health = cdata['initial_health']
            # Восстанавливаем начальные значения; если сохранение старое — берём текущие
            c.initial_inflation = cdata.get('initial_inflation', cdata['inflation'])
            c.initial_unemployment = cdata.get('initial_unemployment', cdata['unemployment'])
            c.sanctions_experience = cdata.get('sanctions_experience', False)
            instance.countries[name] = c

        instance.attacks = [Attack(a) for a in data['attacks']]
        instance._build_connection_graph()
        return instance