import React, { useState, useEffect, useRef } from "react";
import "./GamePage.css";
import { WorldMap } from "react-svg-worldmap";

function GamePage({ nickname }) {
    const [gameState, setGameState] = useState(null);
    const [selectedCountryName, setSelectedCountryName] = useState(null);
    const [selectedAttack, setSelectedAttack] = useState(null);
    const [log, setLog] = useState([]);
    const [activeTab, setActiveTab] = useState("map");
    const [toast, setToast] = useState(null);
    const intervalRef = useRef(null);

    const fetchGameState = async () => {
        try {
            const res = await fetch(`http://localhost:5003/game/state?nickname=${nickname}`);
            const data = await res.json();
            setGameState(data);
            if (data.last_event && data.last_event !== "") {
                addLog(`Событие: ${data.last_event}`);
            }
        } catch (err) {
            console.error(err);
        }
    };

    const performAttack = async () => {
        if (!selectedCountryName || !selectedAttack) {
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
                    target_name: selectedCountryName
                })
            });
            const data = await res.json();
            if (data.success) {
                const newSi = data.state.countries.find(c => c.name === selectedCountryName)?.si;
                showToast(`Успех! Стабильность ${selectedCountryName}: ${newSi}`, "success");
            } else {
                showToast(`Провал!`, "error");
            }
            addLog(data.message);
            setGameState(data.state);
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
                    body: JSON.stringify({ nickname })
                });
                const newState = await res.json();
                setGameState(newState);
                addLog(`День ${newState.day} прошёл.`);
            } catch (err) {
                console.error(err);
            }
        }, 10000);
        return () => clearInterval(intervalRef.current);
    }, [nickname]);

    const addLog = (msg) => {
        const time = new Date().toLocaleTimeString();
        setLog(prev => [`[${time}] ${msg}`, ...prev].slice(0, 30));
    };

    const showToast = (msg, type = "info") => {
        setToast({ msg, type });
        setTimeout(() => setToast(null), 3000);
    };

    if (!gameState) return <div className="loading" style={{ padding: 40, textAlign: "center", color: "#00d4ff" }}>Загрузка...</div>;

    const { ip, reveal, day, current_round, total_rounds, game_over, win, countries, attacks, current_targets } = gameState;

    const isTarget = (countryName) => current_targets.some(t => t.name === countryName);

    const getCountryColor = (country) => {
        if (!isTarget(country.name)) return "#3a4048";
        const si = country.si;
        if (si >= 70) return "#2ecc71";
        if (si >= 40) return "#f39c12";
        if (si >= 20) return "#e67e22";
        return "#e74c3c";
    };

    const countryCodeMap = {
        "США": "US", "Китай": "CN", "Россия": "RU", "Германия": "DE",
        "Франция": "FR", "Великобритания": "GB", "Япония": "JP", "Индия": "IN",
        "Бразилия": "BR", "Канада": "CA", "Австралия": "AU", "Мексика": "MX",
        "Турция": "TR", "ЮАР": "ZA", "Южная Корея": "KR", "Саудовская Аравия": "SA"
    };

    const mapData = countries.map(c => ({
        country: countryCodeMap[c.name] || c.name.slice(0, 2),
        value: c.si,
        name: c.name
    }));

    const handleCountryClick = (countryInfo) => {
        if (game_over) {
            showToast("Игра окончена", "error");
            return;
        }
        const countryCode = typeof countryInfo === "string" ? countryInfo : countryInfo.countryCode;
        const countryName = Object.keys(countryCodeMap).find(key => countryCodeMap[key] === countryCode);
        if (!countryName) return;

        if (!isTarget(countryName)) {
            showToast(`${countryName} не является целью текущего раунда`, "warning");
            return;
        }
        setSelectedCountryName(countryName);
        const country = countries.find(c => c.name === countryName);
        addLog(`Выбрана цель: ${countryName} (SI: ${country.si})`);
    };

    const getAttackCost = (attack) => {
        if (!selectedCountryName) return attack.cost;
        const target = countries.find(c => c.name === selectedCountryName);
        if (!target) return attack.cost;
        const weight = target.weight || 1;
        return Math.floor(attack.cost * weight);
    };

    return (
        <div className="game-page">
            {toast && <div className={`toast ${toast.type}`}>{toast.msg}</div>}

            <div className="game-header">
                <div className="header-content">
                    <div className="logo-area">
                        <div className="globe-icon">🌐</div>
                        <h1>WORLD ECONOMIC SIMULATOR</h1>
                    </div>
                    <div className="stats-bar">
                        <div className="stat">💎 {ip}</div>
                        <div className="stat">🕵️ {reveal}%</div>
                        <div className="stat">📅 {day}</div>
                        <div className="stat">🎯 {current_round}/{total_rounds}</div>
                        <div className="user-badge">{nickname}</div>
                    </div>
                </div>
            </div>

            <div className="round-targets-banner">
                <div className="round-label">РАУНД {current_round} / {total_rounds}</div>
                <div className="targets-list">
                    {current_targets.map(t => (
                        <span key={t.name} className="target-badge">
                            {t.name} <strong>(SI: {t.si})</strong>
                        </span>
                    ))}
                </div>
                <div className="hint">Нажми на страну на карте или на кнопку ниже</div>
            </div>

            <div className="game-tabs">
                <button className={`tab-btn ${activeTab === "map" ? "active" : ""}`} onClick={() => setActiveTab("map")}>
                    КАРТА
                </button>
                <button className={`tab-btn ${activeTab === "attacks" ? "active" : ""}`} onClick={() => setActiveTab("attacks")}>
                    АРСЕНАЛ
                </button>
            </div>

            {activeTab === "map" && (
                <div className="game-layout">
                    <div className="map-container">
                        <div className="world-map-wrapper">
                            <WorldMap
                                data={mapData}
                                onClickFunction={handleCountryClick}
                                styleFunction={(context) => {
                                    const countryName = Object.keys(countryCodeMap).find(k => countryCodeMap[k] === context.country);
                                    const isSelected = selectedCountryName === countryName;
                                    return {
                                        fill: getCountryColor({ name: countryName, si: context.countryValue }),
                                        stroke: isSelected ? "#00d4ff" : "#2a3a4a",
                                        strokeWidth: isSelected ? 2 : 0.8,
                                        cursor: "pointer"
                                    };
                                }}
                            />
                        </div>
                        <div className="targets-list-compact">
                            {current_targets.map(t => (
                                <button
                                    key={t.name}
                                    className={`target-btn ${selectedCountryName === t.name ? "selected" : ""}`}
                                    onClick={() => {
                                        if (game_over) return;
                                        setSelectedCountryName(t.name);
                                        addLog(`Выбрана цель: ${t.name} (SI: ${t.si})`);
                                    }}
                                >
                                    {t.name} (SI: {t.si})
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="game-panel">
                        <div className="selected-info">
                            {selectedCountryName ? `Цель: ${selectedCountryName}` : "Выберите страну"}
                        </div>
                        <button className="attack-action" onClick={performAttack} disabled={game_over}>
                            НАНЕСТИ УДАР
                        </button>
                        <div className="log-list">
                            {log.map((l, i) => <div key={i} className="log-entry">{l}</div>)}
                        </div>
                    </div>
                </div>
            )}

            {activeTab === "attacks" && (
                <div className="attacks-tab">
                    <h3>Выберите тип атаки</h3>
                    <div className="attacks-grid">
                        {attacks.map(a => {
                            const cost = getAttackCost(a);
                            return (
                                <button
                                    key={a.name}
                                    className={`attack-card ${selectedAttack === a.name ? "active" : ""}`}
                                    onClick={() => setSelectedAttack(a.name)}
                                >
                                    <div className="attack-name">{a.name}</div>
                                    <div className="attack-stats">
                                        <span>💰 {cost} IP</span>
                                        <span>💥 {a.damage}</span>
                                        <span>⚠️ {a.risk}</span>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                    {selectedAttack && (
                        <div className="selected-attack-info">
                            Выбрана атака: {selectedAttack}
                        </div>
                    )}
                </div>
            )}

            {game_over && (
                <div className="game-over-modal">
                    <div className="modal-content">
                        <h2>{win ? "ПОБЕДА" : "ПОРАЖЕНИЕ"}</h2>
                        <p>{win ? "Мировая экономика дестабилизирована" : "Вас раскрыли. Миссия провалена."}</p>
                        <button onClick={() => window.location.reload()}>Начать заново</button>
                    </div>
                </div>
            )}
        </div>
    );
}

export default GamePage;