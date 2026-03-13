import React from 'react';
import Draggable from 'react-draggable';
import { GripHorizontal, TrendingUp, TrendingDown, Minus, X } from 'lucide-react';

const DataCard = ({ tag, x, y, onDragStop, onClose }) => {
  const nodeRef = React.useRef(null);

  // Determine deviation color
  let devClass = 'good';
  let DevIcon = Minus;
  if (tag.deviation !== undefined && tag.deviation !== null) {
    if (tag.deviation > 10) { devClass = 'alert'; DevIcon = TrendingUp; }
    else if (tag.deviation > 5) { devClass = 'warn'; DevIcon = TrendingUp; }
    else if (tag.deviation < -10) { devClass = 'alert'; DevIcon = TrendingDown; }
    else if (tag.deviation < -5) { devClass = 'warn'; DevIcon = TrendingDown; }
  }

  // Value formatting
  const actualStr = tag.actual !== undefined ? tag.actual.toFixed(1) : '---';
  const predictStr = tag.predict !== undefined ? tag.predict.toFixed(1) : '---';
  const devStr = tag.deviation !== undefined ? `${Math.abs(tag.deviation).toFixed(1)}%` : '-';

  return (
    <Draggable
      nodeRef={nodeRef}
      handle=".drag-handle"
      defaultPosition={{ x: x || 0, y: y || 0 }}
      onStop={(e, data) => onDragStop(tag.name, data.x, data.y)}
      bounds="parent"
    >
      <div
        ref={nodeRef}
        className="glass-panel data-card"
        style={{ position: 'absolute', top: 0, left: 0 }}
      >
        <div className="card-header">
          <div className="card-title">
            <div className={`card-status ${tag.actual !== undefined ? devClass : 'offline'}`} />
            {tag.name}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div className="drag-handle" title="Drag to move">
              <GripHorizontal size={16} />
            </div>
            {onClose && (
              <button
                onClick={onClose}
                className="close-btn"
                title="Close Card"
              >
                <X size={16} />
              </button>
            )}
          </div>
        </div>

        <div className="card-body">
          <div className="data-row">
            <span className="data-label">Actual</span>
            <div className="data-value-group">
              <span className="data-value value-actual">{actualStr}</span>
              <span className="data-unit">{tag.unit}</span>
            </div>
          </div>

          <div className="data-row">
            <span className="data-label">Predict (1h)</span>
            <div className="data-value-group">
              <span className="data-value value-predict">{predictStr}</span>
              <span className="data-unit">{tag.unit}</span>
            </div>
          </div>

          <div style={{ marginTop: '0.25rem', display: 'flex', justifyContent: 'flex-end' }}>
            <span className={`deviation-badge ${devClass}`}>
              <DevIcon size={12} />
              {devStr}
            </span>
          </div>
        </div>
      </div>
    </Draggable>
  );
};

export default DataCard;
