import React from 'react'
import CustomIndicatorsChart from '../components/CustomIndicatorsChart'

function CustomIndicatorsPanel({ data }) {
  return (
    <div className="chart-section">
      <CustomIndicatorsChart customIndicators={data.customIndicators} />
    </div>
  )
}

export default CustomIndicatorsPanel
