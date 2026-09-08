import EquityPanel from './EquityPanel'
import PricePanel from './PricePanel'
import CustomIndicatorsPanel from './CustomIndicatorsPanel'
import MetricsPanel from './MetricsPanel'

export const PANELS = {
  metrics: {
    id: 'metrics',
    title: 'Performance Metrics',
    component: MetricsPanel,
    requiresRef: false,
    order: 0,
    isAvailable: (data) => data.metrics
  },
  equity: {
    id: 'equity',
    title: 'Equity Curve & Position Size',
    component: EquityPanel,
    requiresRef: true,
    syncChart: true,
    order: 1,
    isAvailable: (data) => data.equityData && data.positionsData
  },
  price: {
    id: 'price',
    title: 'Price Action with Trades',
    component: PricePanel,
    requiresRef: true,
    syncChart: true,
    order: 2,
    isAvailable: (data) => data.priceData
  },
  custom: {
    id: 'custom',
    title: 'Custom Indicators',
    component: CustomIndicatorsPanel,
    requiresRef: false,
    order: 3,
    isAvailable: (data) => data.customIndicators && Object.keys(data.customIndicators).length > 0
  }
}

// Helper function to get available panels
export const getAvailablePanels = (data) => {
  return Object.values(PANELS)
    .filter(panel => panel.isAvailable(data))
    .sort((a, b) => a.order - b.order)
}

// Helper function to build mosaic layout automatically
export const buildMosaicLayout = (availablePanels) => {
  if (availablePanels.length === 0) return null
  if (availablePanels.length === 1) return availablePanels[0].id
  
  // Separate metrics panel from chart panels
  const metricsPanel = availablePanels.find(p => p.id === 'metrics')
  const chartPanels = availablePanels.filter(p => p.id !== 'metrics')
  
  // Build column layout for chart panels
  const buildChartNode = (panels) => {
    if (panels.length === 0) return null
    if (panels.length === 1) return panels[0].id
    if (panels.length === 2) {
      return {
        direction: 'column',
        first: panels[0].id,
        second: panels[1].id,
        splitPercentage: 50
      }
    }
    
    const mid = Math.floor(panels.length / 2)
    return {
      direction: 'column',
      first: buildChartNode(panels.slice(0, mid)),
      second: buildChartNode(panels.slice(mid)),
      splitPercentage: (mid / panels.length) * 100
    }
  }
  
  // If we have metrics panel, put it on the left (21% width)
  if (metricsPanel && chartPanels.length > 0) {
    const chartNode = buildChartNode(chartPanels)
    return {
      direction: 'row',
      first: metricsPanel.id,
      second: chartNode,
      splitPercentage: 21
    }
  }
  
  // If only metrics, return it
  if (metricsPanel) return metricsPanel.id
  
  // If only charts, build column layout
  return buildChartNode(chartPanels)
}

export default PANELS
