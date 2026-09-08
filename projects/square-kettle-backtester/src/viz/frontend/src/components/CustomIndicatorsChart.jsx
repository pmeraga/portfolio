import React, { useEffect, useRef, useState } from 'react'
import { createChart } from 'lightweight-charts'
import { createChartTooltip, createTooltipHeader, createCrosshairMoveHandler, createTooltipRow } from '../utils/chartTooltip'

const CustomIndicatorsChart = ({ customIndicators }) => {
  const chartContainerRef = useRef()
  const chartRef = useRef()
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

  useEffect(() => {
    if (!chartContainerRef.current || !customIndicators || Object.keys(customIndicators).length === 0) return

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
          title: 'Indicator Values',
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

      // Helper function to convert time strings to lightweight-charts format
      const normalizeTimeFormat = (timeString) => {
        try {
          // If it's already a date-only string (YYYY-MM-DD), use as-is
          if (/^\d{4}-\d{2}-\d{2}$/.test(timeString)) {
            return timeString
          }
          
          // If it has time components (YYYY-MM-DD HH:MM:SS), convert to Unix timestamp
          if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$/.test(timeString)) {
            return Math.floor(new Date(timeString).getTime() / 1000)
          }
          
          // Try to parse as date and convert to Unix timestamp
          const date = new Date(timeString)
          if (!isNaN(date.getTime())) {
            return Math.floor(date.getTime() / 1000)
          }
          
          // Fallback: return as-is
          return timeString
        } catch (error) {
          console.warn('Time format conversion failed for:', timeString)
          return timeString
        }
      }

      // Get CSS custom properties for series colors
      const colors = [
        computedStyle.getPropertyValue('--blush-sky').trim(),      // Primary blue
        computedStyle.getPropertyValue('--blush-rose').trim(),     // Secondary rose
        computedStyle.getPropertyValue('--blush-gold').trim(),     // Accent gold
        computedStyle.getPropertyValue('--blush-crimson').trim(),  // Danger crimson
        computedStyle.getPropertyValue('--blush-light').trim(),    // Light blush
        computedStyle.getPropertyValue('--success-color').trim(),  // Success green
        computedStyle.getPropertyValue('--blush-charcoal').trim(), // Text charcoal
        // Fallback hardcoded colors for additional indicators
        '#8E24AA', // Deep Purple
        '#FF8F00', // Amber
        '#00ACC1', // Cyan
      ]

      const series = []
      const indicatorNames = Object.keys(customIndicators)

      // Create a line series for each custom indicator
      indicatorNames.forEach((indicatorName, index) => {
        const data = customIndicators[indicatorName]
        
        if (!data || data.length === 0) return

        const color = colors[index % colors.length]
        
        const lineSeries = chart.addLineSeries({
          color: color,
          lineWidth: 2,
          priceFormat: {
            type: 'custom',
            formatter: (price) => price.toFixed(4),
          },
          title: indicatorName,
        })

        // Normalize time formats for the data
        const normalizedData = data.map(d => ({
          ...d,
          time: normalizeTimeFormat(d.time)
        }))

        lineSeries.setData(normalizedData)
        series.push({ series: lineSeries, name: indicatorName, color })
      })

      // Create shared tooltip (now appended to global tooltip root)
      const tooltip = createChartTooltip()

      // Content generator for custom indicators tooltip
      const generateCustomIndicatorsTooltipContent = (param) => {
        let tooltipContent = createTooltipHeader(param.time)
        
        // Get data for each indicator series
        series.forEach(({ series: lineSeries, name, color }) => {
          if (param.seriesData && param.seriesData.has(lineSeries)) {
            const value = param.seriesData.get(lineSeries)
            if (value && value.value !== undefined) {
              const formattedValue = value.value.toFixed(4)
              tooltipContent += createTooltipRow(
                '📈', 
                name, 
                `<span style="color: ${color}; font-weight: bold;">${formattedValue}</span>`
              )
            }
          }
        })

        return tooltipContent
      }

      // Add crosshair move handler
      chart.subscribeCrosshairMove(createCrosshairMoveHandler(tooltip, chartContainerRef.current, generateCustomIndicatorsTooltipContent, chart))

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
      console.error('Error creating custom indicators chart:', err)
      setError(err.message)
    }
  }, [customIndicators])

  if (error) {
    return (
      <div className="chart-container">
        <div className="chart-error">
          <p>Error loading custom indicators chart</p>
          <small>{error}</small>
        </div>
      </div>
    )
  }

  if (!customIndicators || Object.keys(customIndicators).length === 0) {
    return (
      <div className="chart-container">
        <div className="chart-loading">
          No custom indicators to display
        </div>
      </div>
    )
  }

  // Get CSS palette colors for legend
  const computedStyle = getComputedStyle(document.documentElement)
  const legendColors = [
    computedStyle.getPropertyValue('--blush-sky').trim(),      // Primary blue
    computedStyle.getPropertyValue('--blush-rose').trim(),     // Secondary rose
    computedStyle.getPropertyValue('--blush-gold').trim(),     // Accent gold
    computedStyle.getPropertyValue('--blush-crimson').trim(),  // Danger crimson
    computedStyle.getPropertyValue('--blush-light').trim(),    // Light blush
    computedStyle.getPropertyValue('--success-color').trim(),  // Success green
    computedStyle.getPropertyValue('--blush-charcoal').trim(), // Text charcoal
    // Fallback hardcoded colors for additional indicators
    '#8E24AA', // Deep Purple
    '#FF8F00', // Amber
    '#00ACC1', // Cyan
  ]

  return <div ref={chartContainerRef} className="chart-container" />
}

export default CustomIndicatorsChart
