import React, { useState, useEffect, useRef } from "react";
import "./GamePage.css";
import { WorldMap } from "react-svg-worldmap";

// Вспомогательная функция для расчёта мультипликатора и итоговых параметров атаки на клиенте
function computeAttackDetails(attack, country) {
    if (!country) return null;
    // Базовая стоимость с учётом веса
    const cost = Math.floor(attack.cost * (country.weight || 1));

    // Мультипликатор урона берём из логики игры
    let multiplier = 1.0;
    const notes = [];

    // Тип атаки: кибер, экономическая, финансовая, энергетическая, социальная
    if (attack.tooltip && attack.tooltip.includes("цифровизации")) {
        if (country.digitalization >= 80) {
            multiplier *= 1.5;
            notes.push("+50% (высокая цифровизация)");
        } else if (country.digitalization <= 40) {
            multiplier *= 0.6;
            notes.push("-40% (низкая цифровизация)");
        }
    }
    if (attack.tooltip && attack.tooltip.includes("экспортно-ориентированных")) {
        if (country.export_oriented) {
            multiplier *= 1.4;
            notes.push("+40% (экспортно-ориентированная экономика)");
        } else {
            multiplier *= 0.8;
            notes.push("-20% (большой внутренний рынок)");
        }
    }
    if (attack.tooltip && attack.tooltip.includes("госдолгом")) {
        if (country.debt > country.gdp) {
            multiplier *= 1.5;
            notes.push("+50% (высокий долг > ВВП)");
        } else {
            multiplier *= 0.7;
            notes.push("-30% (низкий долг)");
        }
    }
    if (attack.tooltip && attack.tooltip.includes("импортёров энергии")) {
        if (country.energy_import > 0.4) {
            multiplier *= 1.5;
            notes.push("+50% (высокая зависимость от импорта энергии)");
        } else if (country.energy_export > 0.4) {
            multiplier *= 0.6;
            notes.push("-40% (страна-экспортёр)");
        }
    }
    if (attack.tooltip && (attack.tooltip.includes("безработице") || attack.tooltip.includes("инфляции"))) {
        if (country.unemployment > 8 || country.inflation > 8) {
            multiplier *= 1.5;
            notes.push("+50% (высокая безработица/инфляция)");
        }
    }

    const baseDamage = attack.damage;
    const damage = Math.floor(baseDamage * multiplier);
    const risk = Math.floor(attack.risk * (country.weight || 1));

    return { cost, damage, risk, multiplier, notes };
}

// Определение уязвимостей страны
function getCountryVulnerabilities(country) {
    const v = [];
    if (country.debt > country.gdp) v.push("Высокий долг (уязвима к Валютному кризису и Дефолту)");
    if (country.digitalization >= 80) v.push("Высокая цифровизация (уязвима к Кибератаке)");
    if (country.export_oriented) v.push("Экспортно-ориентированная (уязвима к Торговой войне)");
    if (country.energy_import > 0.4) v.push("Зависимость от импорта энергии (уязвима к Энергоколлапсу)");
    if (country.unemployment > 8 || country.inflation > 8) v.push("Социальная напряжённость (уязвима к Социальному протесту)");
    if (v.length === 0) v.push("Явных уязвимостей нет");
    return v;
}

function GamePage({ nickname }) {
    const [gameState, setGameState] = useState(null);
    const [selectedCountry, setSelectedCountry] = useState(null);
    const [selectedAttack, setSelectedAttack] = useState(null);
    const [log, setLog] = useState([]);
    const [activeTab, setActiveTab] = useState("map");
    const [toast, setToast] = useState(null);
    const [showTutorial, setShowTutorial] = useState(false);
    const [mapVersion, setMapVersion] = useState(0);
    const intervalRef = useRef(null);
    const [hoveredCountry, setHoveredCountry] = useState(null);

    useEffect(() => {
        const tutorialShown = localStorage.getItem("tutorialShown");
        if (!tutorialShown) setShowTutorial(true);
    }, []);

    const closeTutorial = () => {
        setShowTutorial(false);
        localStorage.setItem("tutorialShown", "true");
    };

    const fetchGameState = async () => {
        try {
            const res = await fetch(`http://localhost:5003/game/state?nickname=${nickname}`);
            const data = await res.json();
            setGameState(data);
            if (data.last_event && data.last_event !== "") {
                addLog(`📢 Событие: ${data.last_event}`);
            }
        } catch (err) {
            console.error(err);
        }
    };

    const resetGame = async () => {
        if (window.confirm("Начать новую игру? Весь прогресс будет потерян.")) {
            try {
                const res = await fetch("http://localhost:5003/reset_game", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ nickname }),
                });
                const data = await res.json();
                if (res.ok) {
                    setGameState(data.state);
                    setSelectedCountry(null);
                    setSelectedAttack(null);
                    setMapVersion((prev) => prev + 1);
                    addLog("🔄 Игра сброшена. Начинаем заново!");
                    showToast("Новая игра начата!", "success");
                } else {
                    showToast("Ошибка сброса", "error");
                }
            } catch (err) {
                showToast("Ошибка соединения", "error");
            }
        }
    };

    const performAttack = async () => {
        if (!selectedCountry || !selectedAttack) {
            showToast("Выбери страну и атаку", "warning");
            return;
        }
        try {
            const res = await fetch("http://localhost:5003/game/attack", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    nickname,
                    attack_name: selectedAttack,
                    target_name: selectedCountry,
                }),
            });
            const data = await res.json();
            if (data.success) {
                showToast(`✅ Успех! ${data.message}`, "success");
            } else {
                showToast(`❌ Провал! ${data.message}`, "error");
            }
            addLog(data.message);
            setGameState(data.state);
            setMapVersion((prev) => prev + 1);
        } catch (err) {
            showToast("Ошибка соединения", "error");
        }
    };

    useEffect(() => {
        fetchGameState();
        intervalRef.current = setInterval(async () => {
            try {
                const res = await fetch("http://localhost:5003/game/daily", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ nickname }),
                });
                const newState = await res.json();
                setGameState(newState);
                setMapVersion((prev) => prev + 1);
                addLog(`📅 День ${newState.day} прошёл. Глобальное здоровье: ${newState.global_health}%`);
            } catch (err) {
                console.error(err);
            }
        }, 10000);
        return () => clearInterval(intervalRef.current);
    }, [nickname]);

    const addLog = (msg) => {
        const time = new Date().toLocaleTimeString();
        setLog((prev) => [`[${time}] ${msg}`, ...prev].slice(0, 30));
    };

    const showToast = (msg, type = "info") => {
        setToast({ msg, type });
        setTimeout(() => setToast(null), 3000);
    };

    if (!gameState) return <div className="loading">Загрузка...</div>;

    const { ip, reveal, day, game_over, win, global_health, countries, attacks } = gameState;

    const countryCodeMap = {
        "США": "US",
        "Китай": "CN",
        "Россия": "RU",
        "Германия": "DE",
        "Франция": "FR",
        "Великобритания": "GB",
        "Япония": "JP",
        "Индия": "IN",
        "Бразилия": "BR",
        "Канада": "CA",
        "Австралия": "AU",
        "Мексика": "MX",
        "Турция": "TR",
        "ЮАР": "ZA",
        "Южная Корея": "KR",
        "Саудовская Аравия": "SA",
    };

    const getCountryColor = (health) => {
        if (health >= 80) return "#1a5a2a";
        if (health >= 70) return "#3a7a3a";
        if (health >= 60) return "#5a9a4a";
        if (health >= 50) return "#c4a43a";
        if (health >= 40) return "#d4a02a";
        if (health >= 30) return "#cc6a2a";
        if (health >= 20) return "#b53a2a";
        if (health >= 10) return "#9a1a1a";
        return "#6a0a0a";
    };

    const mapData = countries
        .map((country) => ({
            country: countryCodeMap[country.name],
            value: country.economic_health,
            name: country.name,
        }))
        .filter((item) => item.country);

    const getStyle = ({ countryCode }) => {
        const countryName = Object.keys(countryCodeMap).find((key) => countryCodeMap[key] === countryCode);
        const country = countries.find((c) => c.name === countryName);
        if (!country)
            return { fill: "#0a1225", stroke: "#3a6a9a", strokeWidth: 1, cursor: "default" };
        const isSelected = selectedCountry === countryName;
        const fillColor = getCountryColor(country.economic_health);
        return {
            fill: fillColor,
            stroke: isSelected ? "#00ffff" : "#ffffff",
            strokeWidth: isSelected ? 3 : 1,
            cursor: "pointer",
            filter: isSelected ? "drop-shadow(0 0 8px #00ffff)" : "none",
        };
    };

    const handleCountryClick = ({ countryCode }) => {
        if (game_over) {
            showToast("Игра окончена", "error");
            return;
        }
        const countryName = Object.keys(countryCodeMap).find((key) => countryCodeMap[key] === countryCode);
        if (!countryName) return;
        setSelectedCountry(countryName);
        addLog(`🎯 Выбрана цель: ${countryName}`);
    };

    const getTooltipText = ({ countryName }) => {
        const country = countries.find((c) => c.name === countryName);
        if (!country) return countryName;
        return `${countryName} | 💚${country.economic_health}% | 💰ВВП:${country.gdp} | 💸Долг:${country.debt}% | 📈Инфл:${country.inflation}% | 🧑‍💼Безр:${country.unemployment}%`;
    };

    const getAttackCost = (attack) => {
        if (!selectedCountry) return attack.cost;
        const target = countries.find((c) => c.name === selectedCountry);
        if (!target) return attack.cost;
        return Math.floor(attack.cost * (target.weight || 1));
    };

    const handleRowMouseEnter = (countryName) => setHoveredCountry(countryName);
    const handleRowMouseLeave = () => setHoveredCountry(null);

    const currentHoveredCountry = hoveredCountry ? countries.find((c) => c.name === hoveredCountry) : null;

    return (
        <div className="game-page">
            {showTutorial && (
                <div className="tutorial-overlay" onClick={closeTutorial}>
                    <div className="tutorial-modal" onClick={(e) => e.stopPropagation()}>
                        <button className="tutorial-close" onClick={closeTutorial}>✕</button>
                        <div className="tutorial-icon">🌍</div>
                        <h2>ГЛОБАЛЬНЫЙ ЭКОНОМИЧЕСКИЙ СИМУЛЯТОР</h2>
                        <p className="tutorial-role">Твоя роль: Дестабилизатор мировой экономики</p>
                        <div className="tutorial-section">
                            <h3>🎯 ЦЕЛЬ</h3>
                            <p>Обрушить среднее экономическое здоровье всех стран ниже 30%.</p>
                        </div>
                        <div className="tutorial-section">
                            <h3>⚔️ КАК ИГРАТЬ</h3>
                            <ul>
                                <li>Кликай на страны на карте, чтобы выбрать цель</li>
                                <li>Выбирай атаку во вкладке "Арсенал атак"</li>
                                <li>Следи за раскрываемостью — если 100%, ты проиграл</li>
                                <li>Урон от атаки распространяется на торговых партнёров</li>
                                <li>Используй вкладку "Аналитика" для поиска уязвимостей</li>
                            </ul>
                        </div>
                        <button className="tutorial-button" onClick={closeTutorial}>НАЧАТЬ ИГРУ</button>
                    </div>
                </div>
            )}

            {toast && <div className={`toast ${toast.type}`}>{toast.msg}</div>}

            <div className="game-header">
                <div className="header-content">
                    <div className="logo-area">
                        <div className="globe-icon">🌐</div>
                        <h1>GLOBAL ECONOMIC SIMULATOR</h1>
                    </div>
                    <div className="stats-bar">
                        <div className="stat">💎 IP: {ip}</div>
                        <div className="stat">🕵️ Раскрыто: {reveal}%</div>
                        <div className="stat">📅 День: {day}</div>
                        <div className="stat">🌍 Глоб. здоровье: {global_health}%</div>
                        <div className="user-badge">
                            👤 {nickname}
                            <button className="reset-game-btn" onClick={resetGame}>🔄</button>
                        </div>
                    </div>
                </div>
            </div>

            <div className="game-tabs">
                <button className={`tab-btn ${activeTab === "map" ? "active" : ""}`} onClick={() => setActiveTab("map")}>🗺️ КАРТА</button>
                <button className={`tab-btn ${activeTab === "attacks" ? "active" : ""}`} onClick={() => setActiveTab("attacks")}>⚔️ АРСЕНАЛ</button>
                <button className={`tab-btn ${activeTab === "analytics" ? "active" : ""}`} onClick={() => setActiveTab("analytics")}>📊 АНАЛИТИКА</button>
            </div>

            {activeTab === "map" && (
                <div className="game-layout">
                    <div className="map-container">
                        <div className="world-map-wrapper">
                            <WorldMap
                                key={mapVersion}
                                data={mapData}
                                styleFunction={getStyle}
                                onClickFunction={handleCountryClick}
                                tooltipTextFunction={getTooltipText}
                            />
                        </div>
                    </div>
                    <div className="game-panel">
                        {selectedCountry && (
                            <div className="selected-info">
                                🎯 Цель: {selectedCountry}
                            </div>
                        )}
                        <button className="attack-action" onClick={performAttack} disabled={game_over || !selectedCountry || !selectedAttack}>
                            {selectedAttack ? `НАПАСТЬ (${selectedAttack})` : "ВЫБЕРИ АТАКУ В АРСЕНАЛЕ"}
                        </button>
                        <div className="log-list">
                            <div className="log-title">📋 ЖУРНАЛ</div>
                            {log.map((l, i) => <div key={i} className="log-entry">{l}</div>)}
                        </div>
                    </div>
                </div>
            )}

            {activeTab === "attacks" && (
                <div className="attacks-tab">
                    <h3>⚔️ ВЫБЕРИТЕ ТИП АТАКИ</h3>
                    <div className="attacks-grid">
                        {attacks.map((a) => {
                            const cost = getAttackCost(a);
                            const target = selectedCountry ? countries.find(c => c.name === selectedCountry) : null;
                            const effectiveness = target ? computeAttackDetails(a, target) : null;
                            return (
                                <div
                                    key={a.name}
                                    className={`attack-card ${selectedAttack === a.name ? "active" : ""}`}
                                    onClick={() => setSelectedAttack(a.name)}
                                >
                                    <div className="attack-name">⚔️ {a.name}</div>
                                    <div className="attack-stats">
                                        <span>💎 {effectiveness ? effectiveness.cost : cost}</span>
                                        <span>💥 {effectiveness ? effectiveness.damage : a.damage}</span>
                                        <span>🕵️‍♂️ {effectiveness ? effectiveness.risk : a.risk}</span>
                                    </div>
                                    {a.tooltip && <div className="attack-tooltip">{a.tooltip}</div>}
                                    {effectiveness && effectiveness.notes && effectiveness.notes.length > 0 && (
                                        <div className="attack-effectiveness">
                                            {effectiveness.notes.map((note, i) => (
                                                <span key={i} className="eff-note">{note}</span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                    {selectedAttack && <div className="selected-attack-info">⚔️ Выбрана атака: {selectedAttack}</div>}
                </div>
            )}

            {activeTab === "analytics" && (
                <div className="analytics-tab">
                    <h3>📊 ЭКОНОМИЧЕСКАЯ АНАЛИТИКА</h3>
                    <div className="analytics-table">
                        <table>
                            <thead>
                                <tr>
                                    <th>Страна</th>
                                    <th>Здоровье</th>
                                    <th>ВВП</th>
                                    <th>Долг (% ВВП)</th>
                                    <th>Инфляция</th>
                                    <th>Безработица</th>
                                    <th>Торг. баланс</th>
                                    <th>Альянсы</th>
                                </tr>
                            </thead>
                            <tbody>
                                {countries.map((c) => (
                                    <tr
                                        key={c.name}
                                        className={selectedCountry === c.name ? "selected-row" : ""}
                                        onClick={() => { setSelectedCountry(c.name); setActiveTab("map"); }}
                                        onMouseEnter={() => handleRowMouseEnter(c.name)}
                                        onMouseLeave={handleRowMouseLeave}
                                    >
                                        <td><strong>{c.name}</strong></td>
                                        <td style={{ color: getCountryColor(c.economic_health) }}>{c.economic_health}%</td>
                                        <td>{c.gdp}</td>
                                        <td>{c.debt}%</td>
                                        <td>{c.inflation}%</td>
                                        <td>{c.unemployment}%</td>
                                        <td>{c.trade_balance > 0 ? `+${c.trade_balance}` : c.trade_balance}</td>
                                        <td>{c.alliances.map(a => typeof a === 'string' ? a : a.name).join(', ')}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <div className="analytics-hint">💡 Наведи на строку страны, чтобы увидеть уязвимости; кликни — выбрать на карте</div>

                    {currentHoveredCountry && (
                        <div className="country-tooltip">
                            <h4>{currentHoveredCountry.name} <span style={{ fontSize: "0.7em", color: "#aaa" }}>Вес {currentHoveredCountry.weight}</span></h4>
                            <div className="tooltip-grid">
                                <div>Здоровье: {currentHoveredCountry.economic_health}%</div>
                                <div>ВВП: {currentHoveredCountry.gdp} | Долг: {currentHoveredCountry.debt}%</div>
                                <div>Инфляция: {currentHoveredCountry.inflation}% | Безработица: {currentHoveredCountry.unemployment}%</div>
                                <div>Торг. баланс: {currentHoveredCountry.trade_balance}</div>
                                <div>Цифровизация: {currentHoveredCountry.digitalization}%</div>
                                <div>Экспортно-ориентирована: {currentHoveredCountry.export_oriented ? "да" : "нет"}</div>
                                <div>Импорт энергии: {Math.round(currentHoveredCountry.energy_import * 100)}% | Экспорт: {Math.round(currentHoveredCountry.energy_export * 100)}%</div>
                            </div>
                            <div className="tooltip-alliances">
                                Альянсы: {currentHoveredCountry.alliances.map(a => typeof a === 'string' ? a : a.name).join(', ') || "нет"}
                            </div>
                            <div className="tooltip-partners">
                                Торговые партнёры: {Object.entries(currentHoveredCountry.trade_partners || {}).slice(0, 5).map(([p, s]) => (`${p}(${Math.round(s * 100)}%)`)).join(', ')}
                            </div>
                            <div className="tooltip-vulnerabilities">
                                <strong>Уязвимости:</strong>
                                <ul>
                                    {getCountryVulnerabilities(currentHoveredCountry).map((v, i) => <li key={i}>{v}</li>)}
                                </ul>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {game_over && (
                <div className="game-over-modal">
                    <div className="modal-content">
                        <h2>{win ? "🏆 ПОБЕДА" : "💀 ПОРАЖЕНИЕ"}</h2>
                        <p>{win ? "Мировая экономика рухнула!" : "Вас раскрыли. Миссия провалена."}</p>
                        <button onClick={resetGame}>🔄 Начать новую игру</button>
                    </div>
                </div>
            )}
        </div>
    );
}

export default GamePage;