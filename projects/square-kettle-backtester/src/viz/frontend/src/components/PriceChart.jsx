import React, { useEffect, useRef, useState, forwardRef, useImperativeHandle } from 'react'
import { createChart } from 'lightweight-charts'
import { createChartTooltip, createTooltipHeader, createCrosshairMoveHandler, createTooltipRow, createPriceValue, createChangeValue, createTradesList } from '../utils/chartTooltip'
import { normalizeTimeFormat } from '../utils/timeUtils'

const PriceChart = forwardRef(({ priceData, tradeMarkersData, tradesLookup }, ref) => {
  const chartContainerRef = useRef()
  const chartRef = useRef()
  const seriesRef = useRef()
  const rawPriceDataRef = useRef([])
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
        },
        leftPriceScale: {
          visible: true,
          borderColor: chartBorder,
          title: '', // Empty title for alignment
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
        // Enable built-in tracking mode for OHLC display
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

      let series = null

      // Get CSS custom properties for series colors
      const primaryColor = computedStyle.getPropertyValue('--primary-color').trim()
      const successColor = computedStyle.getPropertyValue('--success-color').trim()
      const dangerColor = computedStyle.getPropertyValue('--danger-color').trim()

      // Store raw price data for dynamic aggregation
      rawPriceDataRef.current = priceData || []

      // Function to determine timeframe based on visible time range (in milliseconds)
      const getTimeframeFromRange = (timeRangeMs) => {
        const minutes = timeRangeMs / (1000 * 60)
        const hours = minutes / 60
        const days = hours / 24

        if (days > 30) return '1d'      // Daily for > 30 days
        if (days > 7) return '2h'       // 2-hourly for > 7 days
        if (hours > 24) return '1h'     // Hourly for > 24 hours
        if (hours > 6) return '15m'     // 15-minute for > 6 hours
        if (hours > 1) return '5m'      // 5-minute for > 1 hour
        return '1m'                     // 1-minute for < 1 hour
      }

      // Function to aggregate price data to a specific timeframe
      const aggregatePriceData = (data, timeframe) => {
        if (!data || data.length === 0) return data
        if (timeframe === '1m') return data // No aggregation needed

        const timeframeMs = {
          '1m': 60 * 1000,
          '5m': 5 * 60 * 1000,
          '15m': 15 * 60 * 1000,
          '1h': 60 * 60 * 1000,
          '2h': 2 * 60 * 60 * 1000,
          '1d': 24 * 60 * 60 * 1000
        }[timeframe] || 60 * 1000

        const aggregated = []
        const timeMap = new Map()

        data.forEach(candle => {
          const time = typeof candle.time === 'number' ? candle.time : new Date(candle.time).getTime()
          const bucket = Math.floor(time / timeframeMs) * timeframeMs

          if (!timeMap.has(bucket)) {
            timeMap.set(bucket, {
              time: bucket / 1000, // Convert to Unix timestamp (seconds)
              open: candle.open,
              high: candle.high,
              low: candle.low,
              close: candle.close,
              count: 1
            })
          } else {
            const existing = timeMap.get(bucket)
            existing.high = Math.max(existing.high, candle.high)
            existing.low = Math.min(existing.low, candle.low)
            existing.close = candle.close // Last close in the bucket
            existing.count++
          }
        })

        return Array.from(timeMap.values()).sort((a, b) => a.time - b.time)
      }

      // Add candlestick series if we have OHLC data
      if (priceData && priceData.length > 0 && priceData[0].open !== undefined) {
        series = chart.addCandlestickSeries({
          upColor: successColor,
          downColor: dangerColor,
          borderVisible: false,
          wickUpColor: successColor,
          wickDownColor: dangerColor,
          priceLineVisible: true,
          lastValueVisible: true,
        })
        
        // Initial data with normalized time formats
        const normalizedPriceData = priceData.map(d => ({
          ...d,
          time: normalizeTimeFormat(d.time)
        }))
        
        series.setData(normalizedPriceData)
        seriesRef.current = series

        // Subscribe to visible time range changes for dynamic aggregation
        chart.timeScale().subscribeVisibleTimeRangeChange((timeRange) => {
          if (!timeRange || !series || !rawPriceDataRef.current || rawPriceDataRef.current.length === 0) return

          try {
            // Calculate visible time range in milliseconds
            const fromTime = typeof timeRange.from === 'number' ? timeRange.from * 1000 : new Date(timeRange.from).getTime()
            const toTime = typeof timeRange.to === 'number' ? timeRange.to * 1000 : new Date(timeRange.to).getTime()
            const timeRangeMs = toTime - fromTime

            // Determine appropriate timeframe based on zoom level
            const timeframe = getTimeframeFromRange(timeRangeMs)

            // Aggregate data to the determined timeframe
            const aggregatedData = aggregatePriceData(rawPriceDataRef.current, timeframe)

            // Normalize and update series
            const normalizedAggregated = aggregatedData.map(d => ({
              ...d,
              time: normalizeTimeFormat(d.time)
            }))

            series.setData(normalizedAggregated)
          } catch (error) {
            console.warn('Error updating dynamic candlestick sizing:', error)
          }
        })
      } else if (priceData && priceData.length > 0) {
        // Fallback to line series using primary palette color
        series = chart.addLineSeries({
          color: primaryColor,
          lineWidth: 2,
        })
        
        const lineData = priceData.map(d => ({ 
          time: normalizeTimeFormat(d.time), 
          value: d.close || d.value 
        }))
        
        series.setData(lineData)
        seriesRef.current = series
      }

      // Add trade markers with normalized time formats
      if (series && tradeMarkersData && tradeMarkersData.length > 0) {
        const normalizedTradesData = tradeMarkersData.map(marker => ({
          ...marker,
          time: normalizeTimeFormat(marker.time)
        }))
        
        series.setMarkers(normalizedTradesData)
      }

      // Create shared tooltip (now appended to global tooltip root)
      const tooltip = createChartTooltip()

      // Content generator for price chart tooltip
      const generatePriceTooltipContent = (param) => {
        let tooltipContent = createTooltipHeader(param.time)
        
        let seriesData = null
        if (series && param.seriesData && param.seriesData.has(series)) {
          seriesData = param.seriesData.get(series)
        }
        
        // Always show price data first if available
        if (seriesData) {
          if (seriesData.open !== undefined) {
            // OHLC data - Enhanced hover window
            const changePercent = seriesData.close && seriesData.open ? 
              ((seriesData.close - seriesData.open) / seriesData.open * 100).toFixed(2) : '0.00'
            
            tooltipContent += createTooltipRow('📈', 'Open', createPriceValue(seriesData.open))
            tooltipContent += createTooltipRow('📊', 'High', createPriceValue(seriesData.high))
            tooltipContent += createTooltipRow('📉', 'Low', createPriceValue(seriesData.low))
            tooltipContent += createTooltipRow('💰', 'Close', createPriceValue(seriesData.close), '#333')
            tooltipContent += createChangeValue(changePercent)
          } else if (seriesData.value !== undefined) {
            // Line data
            tooltipContent += createTooltipRow('💰', 'Price', createPriceValue(seriesData.value), '#333')
          }
        }
        
        // Find trades using the lookup dictionary
        if (tradesLookup) {
          // Try different time formats to find matching trades
          let tradesForBar = null
          
          // Convert param.time to different formats for lookup
          const lookupKeys = []
          
          if (typeof param.time === 'number') {
            // Unix timestamp - convert to date string formats
            const date = new Date(param.time * 1000)
            lookupKeys.push(date.toISOString().split('T')[0]) // YYYY-MM-DD
            lookupKeys.push(date.toISOString().slice(0, 16).replace('T', ' ')) // YYYY-MM-DD HH:MM
            lookupKeys.push(date.toISOString().slice(0, 19).replace('T', ' ')) // YYYY-MM-DD HH:MM:SS
          } else if (typeof param.time === 'string') {
            // String time - use as-is and try variations
            lookupKeys.push(param.time)
            if (param.time.includes(' ')) {
              lookupKeys.push(param.time.split(' ')[0]) // Date part only
            }
          }
          
          // Try each key format
          for (const key of lookupKeys) {
            tradesForBar = tradesLookup[key]
            if (tradesForBar) {
              console.log(`Found trades for key: ${key}`, tradesForBar.length, 'trades')
              break
            }
          }
          
          // Show trades if found
          if (tradesForBar && tradesForBar.length > 0) {
            tooltipContent += createTradesList(tradesForBar)
          }
        }
        
        return tooltipContent
      }

      // Add crosshair move handler using shared utility
      chart.subscribeCrosshairMove(createCrosshairMoveHandler(tooltip, chartContainerRef.current, generatePriceTooltipContent, chart))

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
      console.error('Error creating price chart:', err)
      setError(err.message)
    }
  }, [priceData, tradeMarkersData, tradesLookup])

  if (error) {
    return (
      <div className="chart-container">
        <div className="chart-error">
          <p>Error loading price chart</p>
          <small>{error}</small>
        </div>
      </div>
    )
  }

  if (!priceData || priceData.length === 0) {
    return (
      <div className="chart-container">
        <div className="chart-loading">
          Loading price data...
        </div>
      </div>
    )
  }

  return <div ref={chartContainerRef} className="chart-container" />
})

PriceChart.displayName = 'PriceChart'

export default PriceChart
