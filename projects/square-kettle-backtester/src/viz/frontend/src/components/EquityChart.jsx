import React, { useEffect, useRef, useState, forwardRef, useImperativeHandle } from 'react'
import { createChart } from 'lightweight-charts'
import { createChartTooltip, createTooltipHeader, createCrosshairMoveHandler, createTooltipRow, createEquityValue, createPositionValue } from '../utils/chartTooltip'
import { normalizeTimeFormat } from '../utils/timeUtils'

const EquityChart = forwardRef(({ equityData, positionsData }, ref) => {
  const chartContainerRef = useRef()
  const chartRef = useRef()
  const seriesRef = useRef()
  const [error, setError] = useState(null)

  // Calculate initial chart height
  const getInitialHeight = () => {
    if (!chartContainerRef.current) return 400
    
    const containerHeight = chartContainerRef.current.clientHeight
    if (containerHeight > 0) {
      return containerHeight
    }
    
    const containerWidth = chartContainerRef.current.clientWidth
    const viewportHeight = window.innerHeight
    const aspectRatioHeight = containerWidth / 2
    const viewportBasedHeight = viewportHeight * 0.4
    const calculatedHeight = Math.min(aspectRatioHeight, viewportBasedHeight)
    return Math.max(300, Math.min(calculatedHeight, 600))
  }

  // Expose chart instance to parent
  useImperativeHandle(ref, () => ({
    getChart: () => chartRef.current,
    getSeries: () => seriesRef.current
  }))

  useEffect(() => {
    if (!chartContainerRef.current) return

    try {
      // Get CSS custom properties for chart styling
      const computedStyle = getComputedStyle(document.documentElement)
      const chartBackground = computedStyle.getPropertyValue('--chart-background').trim()
      const chartText = computedStyle.getPropertyValue('--chart-text').trim()
      const chartGrid = computedStyle.getPropertyValue('--chart-grid').trim()
      const chartCrosshair = computedStyle.getPropertyValue('--chart-crosshair').trim()
      const chartCrosshairLabel = computedStyle.getPropertyValue('--chart-crosshair-label').trim()
      const chartBorder = computedStyle.getPropertyValue('--chart-border').trim()

      // Create chart with initial dimensions
      const chart = createChart(chartContainerRef.current, {
        width: chartContainerRef.current.clientWidth,
        height: getInitialHeight(),
        layout: {
          backgroundColor: chartBackground,
          textColor: chartText,
        },
        grid: {
          vertLines: { color: chartGrid },
          horzLines: { color: chartGrid },
        },
        crosshair: {
          mode: 1, // Normal mode
          vertLine: {
            width: 1,
            color: chartCrosshair,
            style: 0,
            labelBackgroundColor: chartCrosshairLabel,
          },
          horzLine: {
            width: 1,
            color: chartCrosshair,
            style: 0,
            labelBackgroundColor: chartCrosshairLabel,
          },
        },
        rightPriceScale: {
          borderColor: chartBorder,
          title: 'Equity ($)',
        },
        leftPriceScale: {
          visible: true,
          borderColor: chartBorder,
          title: 'Position Size',
        },
        timeScale: {
          borderColor: chartBorder,
          timeVisible: true,
          secondsVisible: false,
          rightOffset: 12,
          barSpacing: 3,
          fixLeftEdge: true,
          fixRightEdge: true,
        },
        // Enable built-in tracking mode (same as PriceChart)
        handleScroll: {
          mouseWheel: true,
          pressedMouseMove: true,
        },
        handleScale: {
          axisPressedMouseMove: true,
          mouseWheel: true,
          pinch: true,
        },
      })

      chartRef.current = chart

      // Get CSS custom properties for series colors
      const primaryColor = computedStyle.getPropertyValue('--primary-color').trim()
      const secondaryColor = computedStyle.getPropertyValue('--secondary-color').trim()
      
      // Add equity series using palette colors with title for built-in legend
      const equitySeries = chart.addAreaSeries({
        topColor: `${primaryColor}90`, // primary color with transparency
        bottomColor: `${primaryColor}0A`, // primary color with low transparency  
        lineColor: primaryColor,
        lineWidth: 2,
        priceScaleId: 'right',
        title: 'Portfolio Equity ($)',
      })

      // Store series reference for parent access
      seriesRef.current = equitySeries

      // Add position series if available using secondary palette color with title for built-in legend
      let positionSeries = null
      if (positionsData && positionsData.length > 0) {
        positionSeries = chart.addLineSeries({
          color: secondaryColor,
          lineWidth: 3,
          priceFormat: {
            type: 'custom',
            formatter: (price) => price.toFixed(2),
          },
          priceScaleId: 'left',
          title: 'Position Size',
        })
        
        // Normalize positions data time formats
        const normalizedPositionsData = positionsData.map(d => ({
          ...d,
          time: normalizeTimeFormat(d.time)
        }))
        
        positionSeries.setData(normalizedPositionsData)
      }

      // Set equity data with normalized time formats
      if (equityData && equityData.length > 0) {
        const normalizedEquityData = equityData.map(d => ({
          ...d,
          time: normalizeTimeFormat(d.time)
        }))
        
        equitySeries.setData(normalizedEquityData)
      }

      // Create shared tooltip (now appended to global tooltip root)
      const tooltip = createChartTooltip()

      // Content generator for equity chart tooltip
      const generateEquityTooltipContent = (param) => {
        let tooltipContent = createTooltipHeader(param.time)
        
        let equityValue = null
        let positionValue = null

        // Get equity data
        if (param.seriesData && param.seriesData.has(equitySeries)) {
          equityValue = param.seriesData.get(equitySeries)
        }

        // Get position data if available
        if (positionSeries && param.seriesData && param.seriesData.has(positionSeries)) {
          positionValue = param.seriesData.get(positionSeries)
        }

        if (equityValue) {
          tooltipContent += createTooltipRow('💰', 'Equity', createEquityValue(equityValue.value))
        }
        
        if (positionValue && positionValue.value !== undefined) {
          tooltipContent += createTooltipRow('📊', 'Position', createPositionValue(positionValue.value))
        }

        return tooltipContent
      }

      // Add crosshair move handler using shared utility
      chart.subscribeCrosshairMove(createCrosshairMoveHandler(tooltip, chartContainerRef.current, generateEquityTooltipContent, chart))

      // Handle resize dynamically without rebuilding the chart
      const handleResize = () => {
        if (!chartRef.current || !chartContainerRef.current) return
        
        const containerHeight = chartContainerRef.current.clientHeight
        const newHeight = containerHeight > 0 ? containerHeight : getInitialHeight()
        
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: newHeight
        })
      }

      // Use ResizeObserver to detect container size changes
      const resizeObserver = new ResizeObserver(handleResize)
      resizeObserver.observe(chartContainerRef.current)
      
      window.addEventListener('resize', handleResize)

      return () => {
        window.removeEventListener('resize', handleResize)
        resizeObserver.disconnect()
        if (chartRef.current) {
          chartRef.current.remove()
        }
      }
    } catch (err) {
      console.error('Error creating equity chart:', err)
      setError(err.message)
    }
  }, [equityData, positionsData])

  if (error) {
    return (
      <div className="chart-container">
        <div className="chart-error">
          <p>Error loading equity chart</p>
          <small>{error}</small>
        </div>
      </div>
    )
  }

  if (!equityData || equityData.length === 0) {
    return (
      <div className="chart-container">
        <div className="chart-loading">
          Loading equity data...
        </div>
      </div>
    )
  }

  return <div ref={chartContainerRef} className="chart-container" />
})

EquityChart.displayName = 'EquityChart'

export default EquityChart
