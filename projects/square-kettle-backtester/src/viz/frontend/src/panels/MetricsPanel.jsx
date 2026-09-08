import React from 'react'
import MetricsGrid from '../components/MetricsGrid'

const MetricsPanel = ({ data }) => {
  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A'
    try {
      const date = new Date(dateStr)
      return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric' 
      })
    } catch {
      return dateStr
    }
  }

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      height: '100%',
      overflow: 'auto',
      background: 'linear-gradient(to bottom, #fdfcfd 0%, #f8f9fa 100%)'
    }}>
      <header style={{
        padding: '16px',
        borderBottom: '2px solid #e1d4d7',
        background: 'white',
        flexShrink: 0
      }}>
        <h2 style={{
          margin: '0 0 12px 0',
          fontSize: '1.2rem',
          fontWeight: 700,
          background: 'linear-gradient(135deg, #71C7FE, #D86897)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          lineHeight: 1.3
        }}>
          {data.metrics?.strategy_name || 'Backtest Results'}
        </h2>
        
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          marginTop: '12px'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.85rem',
            color: '#675F61'
          }}>
            <span style={{ fontWeight: 600 }}>Period:</span>
          </div>
          <div style={{
            fontSize: '0.8rem',
            color: '#8a7c7e',
            paddingLeft: '22px',
            lineHeight: 1.5
          }}>
            {formatDate(data.metrics?.start_time)} → {formatDate(data.metrics?.end_time)}
          </div>
          
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.85rem',
            color: '#675F61',
            marginTop: '4px'
          }}>
            <span style={{ fontWeight: 600 }}>Instruments:</span>
            <span style={{ 
              fontSize: '0.8rem',
              color: '#8a7c7e',
              fontFamily: 'monospace',
              background: '#f8f9fa',
              padding: '2px 6px',
              borderRadius: '3px'
            }}>
              {data.metrics?.instruments || 'N/A'}
            </span>
          </div>
        </div>
      </header>

      <div style={{ 
        flex: 1, 
        overflow: 'auto', 
        padding: '12px 8px'
      }}>
        <MetricsGrid metrics={data.metrics} />
      </div>
    </div>
  )
}

export default MetricsPanel
