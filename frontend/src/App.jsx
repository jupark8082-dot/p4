import React, { useState, useEffect, useRef } from 'react';
import DataCard from './components/DataCard';
import TrendChart from './components/TrendChart';
import { Activity, Settings, Bell, LayoutDashboard, TrendingUp } from 'lucide-react';
import './App.css';

const DEFAULT_TAGS = [
  { name: 'TEMP_BOILER_OUT', unit: '°C', color: '#ff6b6b' },
  { name: 'PRESS_MAIN_STEAM', unit: 'MPa', color: '#4facfe' },
  { name: 'POWER_OUTPUT', unit: 'MW', color: '#f6d365' }
];

// 초기 핫스팟 위치 (사용자가 나중에 수정 가능하도록 대략적인 % 좌표로 설정)
const HOTSPOTS = [
  { name: 'TEMP_BOILER_OUT', x: '56.12%', y: '22.69%' },
  { name: 'PRESS_MAIN_STEAM', x: '55.85%', y: '17.33%' },
  { name: 'POWER_OUTPUT', x: '96.83%', y: '49.02%' }
];

function App() {
  const [realtimeData, setRealtimeData] = useState({});
  const [trendData, setTrendData] = useState([]);
  const [activeTag, setActiveTag] = useState(DEFAULT_TAGS[0].name);
  const [showTrend, setShowTrend] = useState(false);
  const [visibleCards, setVisibleCards] = useState([]); // 초기에는 비워둠
  const [layouts, setLayouts] = useState({
    'TEMP_BOILER_OUT': { x: 100, y: 150 },
    'PRESS_MAIN_STEAM': { x: 400, y: 150 },
    'POWER_OUTPUT': { x: 700, y: 200 }
  });

  const wsRef = useRef(null);

  useEffect(() => {
    // connect to websocket
    const connectWs = () => {
      wsRef.current = new WebSocket('ws://localhost:8000/ws/realtime');

      wsRef.current.onopen = () => console.log('WebSocket connected');
      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected, retrying...');
        setTimeout(connectWs, 3000);
      };

      wsRef.current.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'realtime') {
            const newData = {};
            msg.data.forEach(item => {
              // Mocking simple variation for predictions and deviations since AI model isn't active
              const actual = item.value;
              // Add a bit of latency mock to predict
              const predict = actual * (1 + (Math.random() * 0.04 - 0.02));
              const deviation = ((predict - actual) / actual) * 100;

              newData[item.tag_name] = {
                ...item,
                predict,
                deviation
              };
            });
            setRealtimeData(newData);

            // Collect trend for active tag (simple rolling window)
            setTrendData(prev => {
              const info = newData[activeTag];
              if (!info) return prev;
              const nowTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
              const newPoint = { time: nowTime, actual: info.value, predict: info.predict };
              const next = [...prev, newPoint];
              if (next.length > 30) next.shift(); // keep 30 points max for demo
              return next;
            });
          }
        } catch (e) {
          console.error(e);
        }
      };
    };

    connectWs();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [activeTag]);

  // Handle Drag Stop
  const handleDragStop = (tagName, x, y) => {
    setLayouts(prev => ({
      ...prev,
      [tagName]: { x, y }
    }));
  };

  const closeCard = (tagName) => {
    setVisibleCards(prev => prev.filter(name => name !== tagName));
  };

  const handleImageClick = (e) => {
    // 사용자가 이미지 위를 클릭했을 때 % 좌표를 계산하여 알려줌 (배치 편의용)
    const rect = e.target.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    console.log(`Clicked relative coordinates: x = ${x.toFixed(2)}%, y = ${y.toFixed(2)}%`);
  };

  const getTagMeta = (tagName) => DEFAULT_TAGS.find(t => t.name === tagName) || { unit: '' };

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand">
          <Activity color="var(--accent-cyan)" />
          <h1>P4 Predictor</h1>
        </div>

        <nav className="nav-menu">
          <div className="nav-item active">
            <LayoutDashboard size={18} />
            <span>Digital Twin</span>
          </div>
          <div className="nav-item">
            <TrendingUp size={18} />
            <span>Analysis</span>
          </div>
          <div className="nav-item">
            <Settings size={18} />
            <span>Settings</span>
          </div>
        </nav>

        <div style={{ marginTop: 'auto' }}>
          <h3 style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem', textTransform: 'uppercase' }}>Focus Tag</h3>
          {DEFAULT_TAGS.map(t => (
            <div
              key={t.name}
              className={`nav-item ${activeTag === t.name ? 'active' : ''}`}
              style={{
                padding: '0.5rem 1rem',
                fontSize: '0.85rem',
                borderLeftColor: activeTag === t.name ? t.color : 'transparent',
                backgroundColor: activeTag === t.name ? `${t.color}15` : 'transparent' // add 15 for 15% opacity hex
              }}
              onClick={() => {
                setActiveTag(t.name);
                setShowTrend(true);
                setTrendData([]); // clear history on switch
              }}
            >
              {t.name}
            </div>
          ))}
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <header className="header">
          <div className="header-title">Process Flow Overview</div>
          <div className="header-actions">
            <div className="btn-icon">
              <Bell size={18} />
            </div>
          </div>
        </header>

        <div className="workspace">
          {/* PFD Background */}
          <div className="pfd-container" style={{ position: 'relative' }}>
            <img
              src="/images/pfd_background.png"
              alt="PFD Diagram"
              className="pfd-image"
              onClick={handleImageClick}
              title="Click anywhere to get relative coordinates in console"
            />

            {/* Render Hotspots (Pins) */}
            {HOTSPOTS.map((spot, i) => {
              const tagMeta = DEFAULT_TAGS.find(t => t.name === spot.name);
              const color = tagMeta ? tagMeta.color : 'var(--accent-cyan)';
              return (
                <div
                  key={i}
                  className="hotspot-pin"
                  style={{ left: spot.x, top: spot.y, backgroundColor: color, boxShadow: `0 0 10px ${color}` }}
                  onClick={() => {
                    if (!visibleCards.includes(spot.name)) {
                      setVisibleCards(prev => [...prev, spot.name]);
                    }
                  }}
                  title={`Click to show ${spot.name}`}
                >
                  <div className="hotspot-pulse" style={{ backgroundColor: color }}></div>
                </div>
              )
            })}

            {/* Dynamic Data Cards */}
            {visibleCards.map(tagName => {
              const tagMeta = DEFAULT_TAGS.find(t => t.name === tagName);
              if (!tagMeta) return null;

              const rt = realtimeData[tagMeta.name];
              const layout = layouts[tagMeta.name] || { x: 0, y: 0 };

              // Only render card if we have data or want to mock it. We render empty state if no data.
              const tagInfo = {
                name: tagMeta.name,
                unit: tagMeta.unit,
                actual: rt ? rt.value : undefined,
                predict: rt ? rt.predict : undefined,
                deviation: rt ? rt.deviation : undefined,
              };

              return (
                <DataCard
                  key={tagMeta.name}
                  tag={tagInfo}
                  x={layout.x}
                  y={layout.y}
                  onDragStop={handleDragStop}
                  onClose={() => closeCard(tagMeta.name)}
                />
              );
            })}
          </div>
        </div>

        {/* Bottom Trend Chart Panel (Overlay fixed at bottom or rendered in a distinct area) */}
        <div style={{ position: 'absolute', bottom: '1rem', left: '1rem', right: '1rem', zIndex: 20 }}>
          <div style={{ maxWidth: '800px', marginLeft: 'auto' }}>
            {showTrend && (
              <TrendChart
                data={trendData}
                tagName={activeTag}
                unit={getTagMeta(activeTag).unit}
                onClose={() => setShowTrend(false)}
              />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
