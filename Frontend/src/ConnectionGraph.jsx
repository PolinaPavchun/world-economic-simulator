// ConnectionGraph.jsx — интерактивный граф экономических связей между странами.
// Физическая симуляция (force-directed layout): узлы отталкиваются, рёбра притягивают.

import React, { useEffect, useRef, useState, useMemo } from 'react';
// useEffect — запускает симуляцию при монтировании
// useMemo — кеширует список рёбер, не пересчитывает без изменений

// Цвета рёбер по типу связи
const CONN_COLORS = { trade: '#2ecc71', debt: '#e74c3c', energy: '#f39c12' };
// Подписи для кнопок-фильтров
const CONN_LABELS = { trade: 'Торговля', debt: 'Долг', energy: 'Энергия' };

// eslint-disable-next-line react-refresh/only-export-components
export const ALLIANCE_COLORS = {
  'НАТО': '#4488ff', 'ЕС': '#aa44ff', 'G7': '#ffdd44',
  'БРИКС': '#ff8844', 'ШОС': '#ff4444', 'Five Eyes': '#00ffcc',
  'Союзник США': '#88bbff', 'ЕАЭС': '#ff66aa',
};

// Строит список всех рёбер графа из данных стран.
// Торговля — двусторонняя (без стрелки), долг и энергия — направленные.
function buildAllEdges(countries) {
  const edges = [];
  const names = new Set(countries.map(c => c.name));

  const tradeSet = new Set();
  countries.forEach(c => {
    Object.entries(c.trade_partners || {}).forEach(([partner, share]) => {
      if (!names.has(partner)) return;
      const key = [c.name, partner].sort().join('|');
      if (tradeSet.has(key)) return;
      tradeSet.add(key);
      edges.push({ source: c.name, target: partner, type: 'trade', strength: share, directed: false });
    });

    // Долг: стрелка от кредитора к должнику
    Object.entries(c.external_debt_holders || {}).forEach(([creditor, amount]) => {
      if (names.has(creditor))
        edges.push({ source: creditor, target: c.name, type: 'debt', strength: Math.min(amount / 1200, 1), directed: true });
    });

    // Энергия: стрелка от поставщика к импортёру
    Object.entries(c.energy_dependencies || {}).forEach(([supplier, share]) => {
      if (names.has(supplier))
        edges.push({ source: supplier, target: c.name, type: 'energy', strength: share, directed: true });
    });
  });

  return edges;
}

function healthColor(h) {
  if (h >= 60) return '#27ae60';
  if (h >= 30) return '#e67e22';
  return '#e74c3c';
}

// Основной компонент графа связей
// Принимает: countries (массив), selectedCountry (строка|null), onSelectCountry (коллбэк)
export function ConnectionGraph({ countries, selectedCountry, onSelectCountry }) {
  const [filterTypes, setFilterTypes] = useState(['energy']); // какие типы рёбер показывать
  const [positions, setPositions] = useState({});  // {страна: {x, y}} — позиции узлов после симуляции
  const [hovered, setHovered] = useState(null);    // название страны под курсором
  const [simDone, setSimDone] = useState(false);   // завершилась ли физическая симуляция
  const nodesRef = useRef([]);  // узлы симуляции (x, y, vx, vy) — хранятся вне state, чтобы не вызывать лишних рендеров
  const rafRef = useRef(null);  // ID requestAnimationFrame — нужен для отмены при размонтировании
  const W = 820, H = 480; // размеры SVG-холста в пикселях (в системе координат viewBox)

  const countryLen = countries?.length || 0;

  useEffect(() => {
    // Запускает физическую симуляцию при изменении числа стран.
    if (!countryLen) return;
    setSimDone(false);
    const all = buildAllEdges(countries);
    const n = countries.length;

    // Начальные позиции узлов — равномерно по окружности
    nodesRef.current = countries.map((c, i) => {
      const θ = (2 * Math.PI * i) / n - Math.PI / 2;
      const r = Math.min(W, H) * 0.32;
      return { id: c.name, x: W / 2 + r * Math.cos(θ), y: H / 2 + r * Math.sin(θ), vx: 0, vy: 0, weight: c.weight || 1 };
    });

    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    let α = 1.0; // температура симуляции: убывает до нуля

    const tick = () => {
      α *= 0.993;
      if (α < 0.004) {
        setPositions(Object.fromEntries(nodesRef.current.map(nd => [nd.id, { x: nd.x, y: nd.y }])));
        setSimDone(true);
        return;
      }
      const nds = nodesRef.current;
      // Отталкивание между всеми парами узлов
      for (let i = 0; i < nds.length; i++) {
        for (let j = i + 1; j < nds.length; j++) {
          const dx = nds[i].x - nds[j].x, dy = nds[i].y - nds[j].y;
          const d2 = (dx * dx + dy * dy) || 1;
          const d = Math.sqrt(d2);
          const f = (5500 / d2) * α;
          nds[i].vx += (dx / d) * f; nds[i].vy += (dy / d) * f;
          nds[j].vx -= (dx / d) * f; nds[j].vy -= (dy / d) * f;
        }
      }
      // Притяжение вдоль рёбер к желаемому расстоянию
      all.forEach(e => {
        const s = nds.find(nd => nd.id === e.source), t = nds.find(nd => nd.id === e.target);
        if (!s || !t) return;
        const dx = t.x - s.x, dy = t.y - s.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
        const ideal = e.type === 'trade' ? 155 : 185;
        const f = (d - ideal) * 0.007 * α * (0.4 + e.strength);
        s.vx += (dx / d) * f; s.vy += (dy / d) * f;
        t.vx -= (dx / d) * f; t.vy -= (dy / d) * f;
      });
      nds.forEach(nd => {
        // Слабое притяжение к центру — узлы не улетают за края
        nd.vx += (W / 2 - nd.x) * 0.003 * α; nd.vy += (H / 2 - nd.y) * 0.003 * α;
        nd.vx *= 0.84; nd.vy *= 0.84;
        nd.x = Math.max(70, Math.min(W - 70, nd.x + nd.vx));
        nd.y = Math.max(40, Math.min(H - 40, nd.y + nd.vy));
      });
      setPositions(Object.fromEntries(nds.map(nd => [nd.id, { x: nd.x, y: nd.y }])));
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [countryLen]);

  // Включает или выключает отображение рёбер выбранного типа.
  const toggleFilter = t => setFilterTypes(p => p.includes(t) ? p.filter(x => x !== t) : [...p, t]);

  const allEdges = useMemo(() => buildAllEdges(countries || []), [countries]);
  const visibleEdges = allEdges.filter(e => filterTypes.includes(e.type));

  // Наведение мышью имеет приоритет над кликом при подсветке связей.
  const activeNode = hovered || selectedCountry;
  const connectedSet = activeNode
    ? new Set(visibleEdges.filter(e => e.source === activeNode || e.target === activeNode).flatMap(e => [e.source, e.target]))
    : null;

  const selectedData = selectedCountry ? countries?.find(c => c.name === selectedCountry) : null;
  const selectedEdges = selectedCountry
    ? visibleEdges.filter(e => e.source === selectedCountry || e.target === selectedCountry)
    : [];

  const directionNote = {
    trade: 'двусторонняя торговля',
    debt: 'стрелка от кредитора к должнику',
    energy: 'стрелка от поставщика к импортёру',
  };

  return (
    <div className="connection-graph">
      <div className="graph-filters">
        {(['trade', 'debt', 'energy']).map(t => {
          const on = filterTypes.includes(t);
          return (
            <button key={t} className={`filter-btn ${on ? 'active' : ''}`}
              style={on ? { borderColor: CONN_COLORS[t], color: CONN_COLORS[t], background: `${CONN_COLORS[t]}18`, boxShadow: `0 0 8px ${CONN_COLORS[t]}40` } : {}}
              onClick={() => toggleFilter(t)}
            >
              <span className="filter-dot" style={{ background: on ? CONN_COLORS[t] : '#555' }} />
              {CONN_LABELS[t]}
            </button>
          );
        })}
        {filterTypes.map(t => (
          <span key={t} className="graph-dir-note" style={{ color: CONN_COLORS[t] }}>
            {directionNote[t]}
          </span>
        ))}
      </div>

      <div className="graph-body">
        <div className="graph-svg-wrap">
          <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: '100%', background: '#060a14', borderRadius: 16, display: 'block' }}>
            <defs>
              {/* SVG <defs> — определения многоразовых элементов (стрелок), на которые ссылаются рёбра */}
              {/* Стрелки фиксированного размера в пикселях (markerUnits="userSpaceOnUse") */}
              {(['debt', 'energy']).map(t => (
                // <marker> — SVG-примитив для рисования стрелок на конце линии
                // id="arr-debt" и id="arr-energy" — чтобы ссылаться через markerEnd="url(#arr-debt)"
                // refX="13" refY="7" — точка "прикрепления" маркера к концу линии (кончик стрелки)
                // orient="auto" — стрелка автоматически поворачивается вдоль линии
                <marker key={t} id={`arr-${t}`}
                  markerWidth="14" markerHeight="14"
                  refX="13" refY="7"
                  orient="auto"
                  markerUnits="userSpaceOnUse">
                  {/* Острый треугольник: кончик в (13,7), основание слева; M=moveto, L=lineto, Z=close */}
                  <path d="M0,1 L13,7 L0,13 L3,7 Z" fill={CONN_COLORS[t]} opacity="0.95" />
                </marker>
              ))}
            </defs>

            {visibleEdges.map((e, i) => {
              const s = positions[e.source], tgt = positions[e.target];
              if (!s || !tgt) return null;

              const dx = tgt.x - s.x, dy = tgt.y - s.y;
              const len = Math.sqrt(dx * dx + dy * dy) || 1;

              // Не рисуем ребро если страны слишком близко — стрелка будет перевёрнута
              if (len < 55) return null;

              // Когда выбрана страна — полностью скрываем несвязанные рёбра
              const isConnected = !activeNode || e.source === activeNode || e.target === activeNode;
              if (!isConnected) return null;

              const nodeR = 22; // радиус кружка узла в пикселях (чтобы линия не перекрывала его)
              const ar = e.directed ? 15 : 0; // запас для стрелки: 15px если направленная, 0 если нет
              // Начало линии: смещаем от центра узла на nodeR пикселей в сторону цели
              const x1 = s.x + (dx / len) * nodeR;
              const y1 = s.y + (dy / len) * nodeR;
              // Конец линии: отступаем от центра цели на nodeR + ar (чтобы стрелка не лезла в круг)
              const x2 = tgt.x - (dx / len) * (nodeR + ar);
              const y2 = tgt.y - (dy / len) * (nodeR + ar);

              // Дополнительная проверка: линия не должна идти в обратную сторону
              const rdx = x2 - x1, rdy = y2 - y1;
              if (rdx * dx + rdy * dy < 0) return null;

              // Толщина линии пропорциональна силе связи: Math.max гарантирует минимум 1.5px
              const sw = Math.max(1.5, e.strength * 5);
              return (
                <line key={i}
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={CONN_COLORS[e.type]}
                  strokeWidth={sw}
                  strokeOpacity={0.85}
                  strokeDasharray={e.type === 'debt' ? '7,4' : undefined}
                  markerEnd={e.directed ? `url(#arr-${e.type})` : undefined}
                />
              );
            })}

            {/* Рисуем узлы поверх рёбер (порядок в SVG = z-index: последние элементы сверху) */}
            {(countries || []).map(country => {
              const pos = positions[country.name];
              if (!pos) return null; // симуляция ещё не посчитала позицию этого узла
              // Размер узла зависит от "веса" страны (её значимости в мировой экономике)
              const r = 16 + country.weight * 4;
              const hc = healthColor(country.economic_health); // цвет по здоровью
              const isSel = selectedCountry === country.name;
              // !! конвертирует в булево; ?. — optional chaining: if connectedSet is null → undefined → false
              const isDim = !!activeNode && !connectedSet?.has(country.name); // затемнить несвязанные
              // Цвета альянсов для этой страны — максимум 4 кольца вокруг узла
              const allianceRings = (country.alliances || [])
                .map(a => ALLIANCE_COLORS[a?.name || a])
                .filter(Boolean)
                .slice(0, 4);
              return (
                <g key={country.name} transform={`translate(${pos.x},${pos.y})`}
                  opacity={isDim ? 0.15 : 1} style={{ cursor: 'pointer' }}
                  onClick={() => onSelectCountry(isSel ? null : country.name)}
                  onMouseEnter={() => setHovered(country.name)}
                  onMouseLeave={() => setHovered(null)}
                >
                  {(isSel || hovered === country.name) && <circle r={r + 6 + allianceRings.length * 6 + 8} fill={hc} opacity={0.08} />}
                  {/* One ring per alliance, outermost first */}
                  {allianceRings.map((color, i) => (
                    <circle key={i}
                      r={r + 6 + (allianceRings.length - 1 - i) * 6}
                      fill="none"
                      stroke={color}
                      strokeWidth={2.5}
                      strokeOpacity={0.85}
                    />
                  ))}
                  <circle r={r} fill={hc} stroke={isSel ? '#00ffff' : '#fff'} strokeWidth={isSel ? 2.5 : 0.5} strokeOpacity={isSel ? 1 : 0.3} />
                  <text textAnchor="middle" dy="4" fill="#fff" fontSize="9" fontWeight="700" style={{ pointerEvents: 'none', userSelect: 'none' }}>
                    {country.economic_health}%
                  </text>
                  <text textAnchor="middle" dy={r + 15} fill={isSel ? '#00ffff' : '#ccdeee'} fontSize="11" fontWeight={isSel ? '700' : '500'} style={{ pointerEvents: 'none', userSelect: 'none' }}>
                    {country.name}
                  </text>
                </g>
              );
            })}
          </svg>
          {!simDone && <div className="graph-loading-overlay">Строю граф...</div>}
        </div>

        <div className="graph-side-panel">
          {selectedData ? (
            <div className="graph-side-content">
              <div className="graph-side-header" style={{ borderColor: healthColor(selectedData.economic_health) }}>
                <span className="graph-side-name">{selectedData.name}</span>
                <span className="graph-side-health" style={{ background: healthColor(selectedData.economic_health) }}>{selectedData.economic_health}%</span>
              </div>

              <div className="graph-stat-bars">
                {[
                  { label: 'Долг/ВВП', val: Math.round(selectedData.debt / selectedData.gdp * 100), max: 210, threshold: 90, color: '#e74c3c', unit: '%' },
                  { label: 'Инфляция', val: selectedData.inflation, max: 30, threshold: 8, color: '#f39c12', unit: '%' },
                  { label: 'Безработица', val: selectedData.unemployment, max: 35, threshold: 10, color: '#e67e22', unit: '%' },
                  { label: 'Резервы', val: selectedData.foreign_reserves, max: 1500, threshold: -1, color: '#2ecc71', unit: '$млрд' },
                ].map(({ label, val, max, threshold, color, unit }) => {
                  const pct = Math.min(100, (val / max) * 100);
                  const hot = threshold > 0 && val > threshold;
                  return (
                    <div key={label} className="graph-stat-bar">
                      <div className="graph-stat-label">
                        <span>{label}</span>
                        <span style={{ color: hot ? '#ff8888' : '#ccdeee' }}>{Number.isInteger(val) ? val : val.toFixed(1)}{unit}</span>
                      </div>
                      <div className="graph-stat-track">
                        <div className="graph-stat-fill" style={{ width: `${pct}%`, background: hot ? '#e74c3c' : color }} />
                        {threshold > 0 && <div className="graph-threshold-line" style={{ left: `${(threshold / max) * 100}%` }} />}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="graph-badges-section">
                <div className="graph-section-label">Альянсы</div>
                <div className="graph-badges-row">
                  {(selectedData.alliances || []).map((a, i) => {
                    const name = a?.name || a;
                    const col = ALLIANCE_COLORS[name] || '#88aacc';
                    return <span key={i} className="alliance-badge" style={{ borderColor: col, color: col }}>{name}</span>;
                  })}
                  {(selectedData.trade_blocs || []).map((b, i) => <span key={`b${i}`} className="trade-bloc-badge">{b}</span>)}
                </div>
              </div>

              <div className="graph-edges-section">
                <div className="graph-section-label">Связи ({selectedEdges.length})</div>
                {selectedEdges.length === 0
                  ? <div className="graph-no-edges">Нет связей для выбранных типов</div>
                  : selectedEdges.map((e, i) => {
                    const isOut = e.source === selectedCountry;
                    const other = isOut ? e.target : e.source;
                    // Подпись направления связи в зависимости от её типа
                    let dirLabel = '';
                    if (e.type === 'energy') dirLabel = isOut ? 'поставляет в' : 'получает от';
                    else if (e.type === 'debt') dirLabel = isOut ? 'кредитует' : 'должен';
                    else dirLabel = 'торгует с';
                    return (
                      <div key={i} className="graph-edge-row">
                        <span className="edge-type-dot" style={{ background: CONN_COLORS[e.type] }} />
                        <span className="edge-dir-label">{dirLabel}</span>
                        <span className="edge-partner">{other}</span>
                        <span className="edge-strength" style={{ color: CONN_COLORS[e.type] }}>{Math.round(e.strength * 100)}%</span>
                      </div>
                    );
                  })
                }
              </div>
            </div>
          ) : (
            <div className="graph-side-empty">
              <div className="graph-empty-icon">◉</div>
              <p>Выбери страну, чтобы увидеть её связи</p>
            </div>
          )}

          <div className="alliance-legend-panel">
            <div className="graph-section-label">Кольцо = Альянс</div>
            <div className="alliance-legend-items">
              {Object.entries(ALLIANCE_COLORS).map(([name, color]) => (
                <div key={name} className="alliance-legend-row">
                  <span className="alliance-legend-dot" style={{ borderColor: color }} />
                  <span>{name}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="graph-edu-note">
        Стрелка энергии → указывает куда течёт ресурс (от поставщика к импортёру). Стрелка долга → от кредитора к должнику.
      </div>
    </div>
  );
}
