import React from 'react'
import { getMetricItems, METRICS_CONFIG } from '../config/metricsConfig'

const MetricsGrid = ({ metrics }) => {
  if (!metrics) {
    return (
      <div className="metrics-professional">
        <h2 className="metrics-title">Performance Summary</h2>
        <div className="metrics-table">
          <div className="metrics-row header-row">
            {METRICS_CONFIG.map(config => (
              <div key={config.id} className="metric-cell">{config.label}</div>
            ))}
          </div>
          <div className="metrics-row value-row">
            {METRICS_CONFIG.map(config => (
              <div key={config.id} className="metric-cell">Loading...</div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  const metricItems = getMetricItems(metrics)

  return (
    <div style={{ padding: '4px 0' }}>
      <h3 style={{
        fontSize: '0.75rem',
        fontWeight: 700,
        color: '#675F61',
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
        marginBottom: '12px',
        paddingLeft: '4px'
      }}>
        Performance Summary
      </h3>
      
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(2, 1fr)',
        gap: '8px'
      }}>
        {metricItems.map((item, index) => (
          <div
            key={index}
            style={{
              background: 'white',
              border: '1px solid #f0e8eb',
              borderRadius: '8px',
              padding: '10px',
              transition: 'all 0.2s ease',
              cursor: 'default',
              boxShadow: '0 1px 3px rgba(103, 95, 97, 0.05)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow = '0 4px 12px rgba(103, 95, 97, 0.1)'
              e.currentTarget.style.transform = 'translateY(-2px)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow = '0 1px 3px rgba(103, 95, 97, 0.05)'
              e.currentTarget.style.transform = 'translateY(0)'
            }}
          >
            <div style={{
              marginBottom: '6px'
            }}>
              <span style={{
                fontSize: '0.7rem',
                fontWeight: 600,
                color: '#8a7c7e',
                textTransform: 'uppercase',
                letterSpacing: '0.3px'
              }}>
                {item.label}
              </span>
            </div>
            <div style={{
              fontSize: '1.1rem',
              fontWeight: 700,
              color: item.valueClass === 'positive' ? '#27ae60' : 
                     item.valueClass === 'negative' ? '#F71941' : 
                     '#675F61',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
            }}>
              {item.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default MetricsGrid
