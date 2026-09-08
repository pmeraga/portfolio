import React from 'react'
import PriceChart from '../components/PriceChart'

function PricePanel({ data, chartRef }) {
  return (
    <div className="chart-section">
      <PriceChart 
        ref={chartRef}
        priceData={data.priceData} 
        tradeMarkersData={data.tradeMarkersData}
        tradesLookup={data.tradesLookup}
      />
    </div>
  )
}

export default PricePanel
