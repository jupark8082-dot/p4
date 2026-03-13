import React from 'react';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ReferenceLine,
    Legend
} from 'recharts';
import { motion } from 'framer-motion';
import { X } from 'lucide-react';

const TrendChart = ({ data, tagName, unit, onClose }) => {
    // data format: [{ time: '10:00', actual: 50.1, predict: null }, { time: '10:05', actual: null, predict: 51.0 }]

    return (
        <motion.div
            className="glass-panel"
            style={{ padding: '1rem', height: '300px', width: '100%', marginTop: '1rem' }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
        >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h3 style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: 0 }}>
                    {tagName} Trend ({unit})
                </h3>
                {onClose && (
                    <button
                        onClick={onClose}
                        style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '0.2rem' }}
                    >
                        <X size={18} />
                    </button>
                )}
            </div>
            <ResponsiveContainer width="100%" height="85%">
                <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis
                        dataKey="time"
                        stroke="var(--text-muted)"
                        tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                    />
                    <YAxis
                        stroke="var(--text-muted)"
                        tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                        domain={['auto', 'auto']}
                    />
                    <Tooltip
                        contentStyle={{ backgroundColor: 'var(--bg-panel)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                        itemStyle={{ color: '#fff' }}
                    />
                    <Legend wrapperStyle={{ fontSize: '12px' }} />

                    <Line
                        type="monotone"
                        dataKey="actual"
                        name="Actual"
                        stroke="#fff"
                        strokeWidth={2}
                        dot={false}
                        activeDot={{ r: 6, fill: '#fff' }}
                    />
                    <Line
                        type="monotone"
                        dataKey="predict"
                        name="Predicted"
                        stroke="var(--accent-cyan)"
                        strokeWidth={2}
                        strokeDasharray="5 5"
                        dot={false}
                    />
                    {/* Mock Current Time Line */}
                    <ReferenceLine x={data[Math.floor(data.length / 2)]?.time} stroke="var(--accent-blue)" strokeDasharray="3 3" />
                </LineChart>
            </ResponsiveContainer>
        </motion.div>
    );
};

export default TrendChart;
