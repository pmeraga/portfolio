import React from 'react'
import EquityChart from '../components/EquityChart'

function EquityPanel({ data, chartRef }) {
  return (
    <div className="chart-section">
      <EquityChart 
        ref={chartRef}
        equityData={data.equityData} 
        positionsData={data.positionsData}
      />
    </div>
  )
}

export default EquityPanel
