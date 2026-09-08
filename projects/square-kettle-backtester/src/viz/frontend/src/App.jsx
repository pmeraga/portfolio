import React, { useState, useEffect, useRef, useMemo } from 'react'
import { Mosaic, MosaicWindow } from 'react-mosaic-component'
import 'react-mosaic-component/react-mosaic-component.css'
import PANELS, { getAvailablePanels, buildMosaicLayout } from './panels'
import MetricsGrid from './components/MetricsGrid'
import { fetchBacktestData } from './utils/api'

function App() {
  const [data, setData] = useState({
    metrics: null,
    equityData: null,
    priceData: null,
    tradeMarkersData: null,
    tradesLookup: null,
    positionsData: null,
    customIndicators: null,
    loading: true,
    error: null
  })

  // Automatically determine available panels and build layout
  const availablePanels = getAvailablePanels(data)
  const initialValue = buildMosaicLayout(availablePanels)
  const [mosaicValue, setMosaicValue] = useState(initialValue)

  // Use a ref to store chart refs - this is extensible
  const chartRefsContainer = useRef({})
  
  // Initialize refs for panels that need them
  const chartRefs = useMemo(() => {
    const refs = {}
    Object.values(PANELS).forEach(panel => {
      if (panel.requiresRef) {
        if (!chartRefsContainer.current[panel.id]) {
          chartRefsContainer.current[panel.id] = { current: null }
        }
        refs[panel.id] = chartRefsContainer.current[panel.id]
      }
    })
    return refs
  }, [])

  useEffect(() => {
    loadData()
  }, [])

  // Update mosaic layout when data changes
  useEffect(() => {
    const newLayout = buildMosaicLayout(getAvailablePanels(data))
    setMosaicValue(newLayout)
  }, [data.customIndicators, data.equityData, data.priceData, data.metrics])

  // Synchronize charts that have syncChart: true - this is extensible
  useEffect(() => {
    // Get all panels that should be synced
    const syncPanels = Object.values(PANELS).filter(panel => panel.syncChart && panel.requiresRef)
    
    if (syncPanels.length < 2) {
      return // Need at least 2 charts to sync
    }

    // Get chart instances and series for sync-enabled panels
    const syncedCharts = []
    syncPanels.forEach(panel => {
      const ref = chartRefs[panel.id]
      if (ref?.current) {
        const chart = ref.current.getChart?.()
        const series = ref.current.getSeries?.()
        if (chart && series) {
          syncedCharts.push({ id: panel.id, chart, series })
        }
      }
    })

    if (syncedCharts.length < 2) {
      return // Need at least 2 valid charts
    }

    // Create handlers for each chart
    const subscriptions = []

    syncedCharts.forEach((source, sourceIndex) => {
      // Time scale sync - when one chart's time scale changes, update all others
      const handleTimeScaleChange = (timeRange) => {
        if (timeRange) {
          syncedCharts.forEach((target, targetIndex) => {
            if (targetIndex !== sourceIndex) {
              target.chart.timeScale().setVisibleLogicalRange(timeRange)
            }
          })
        }
      }

      // Crosshair sync - when one chart's crosshair moves, update all others
      const handleCrosshairMove = (param) => {
        if (param.time) {
          const sourceData = param.seriesData.get(source.series)
          if (sourceData) {
            // Get the value to sync (handle both OHLC and line data)
            const value = sourceData.close !== undefined ? sourceData.close : sourceData.value
            
            if (value !== undefined) {
              syncedCharts.forEach((target, targetIndex) => {
                if (targetIndex !== sourceIndex) {
                  target.chart.setCrosshairPosition(value, param.time, target.series)
                }
              })
            }
          }
        } else {
          // Clear crosshair on all other charts
          syncedCharts.forEach((target, targetIndex) => {
            if (targetIndex !== sourceIndex) {
              target.chart.clearCrosshairPosition()
            }
          })
        }
      }

      // Subscribe to events
      source.chart.timeScale().subscribeVisibleLogicalRangeChange(handleTimeScaleChange)
      source.chart.subscribeCrosshairMove(handleCrosshairMove)

      // Store cleanup functions
      subscriptions.push({
        chart: source.chart,
        unsubscribeTimeScale: () => source.chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleTimeScaleChange),
        unsubscribeCrosshair: () => source.chart.unsubscribeCrosshairMove(handleCrosshairMove)
      })
    })

    // Cleanup all subscriptions
    return () => {
      subscriptions.forEach(sub => {
        try {
          sub.unsubscribeTimeScale()
          sub.unsubscribeCrosshair()
        } catch (e) {
          console.warn('Error unsubscribing chart sync:', e)
        }
      })
    }
  }, [data.equityData, data.priceData, chartRefs, mosaicValue])

  const loadData = async () => {
    try {
      setData(prev => ({ ...prev, loading: true, error: null }))
      const backtestData = await fetchBacktestData()
      setData({
        ...backtestData,
        loading: false,
        error: null
      })
    } catch (error) {
      console.error('Error loading backtest data:', error)
      setData(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to load backtest data. Make sure the Flask server is running.'
      }))
    }
  }

  if (data.loading) {
    return (
      <div className="app-loading">
        <div className="loading-spinner"></div>
        <p>Loading backtest results...</p>
      </div>
    )
  }

  if (data.error) {
    return (
      <div className="app-error">
        <h2>Error Loading Data</h2>
        <p>{data.error}</p>
        <button onClick={loadData} className="retry-button">
          Retry
        </button>
      </div>
    )
  }

  const handleResize = () => {
    window.dispatchEvent(new Event('resize'))
  }

  const renderTile = (id, path) => {
    const panel = PANELS[id]
    if (!panel) return null

    const PanelComponent = panel.component
    const chartRef = panel.requiresRef ? chartRefs[id] : undefined

    return (
      <MosaicWindow
        path={path}
        title={panel.title}
        toolbarControls={[]}
      >
        <PanelComponent data={data} chartRef={chartRef} />
      </MosaicWindow>
    )
  }

  return (
    <div className="app">
      <Mosaic
        renderTile={renderTile}
        value={mosaicValue}
        onChange={setMosaicValue}
        onRelease={handleResize}
      />
      {/* Global tooltip container - renders above all mosaic windows */}
      <div id="tooltip-root"></div>
    </div>
  )
}

export default App
