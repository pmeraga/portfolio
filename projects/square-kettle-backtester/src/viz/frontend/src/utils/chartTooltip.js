// Shared tooltip utility for lightweight-charts
export const createChartTooltip = () => {
  const tooltip = document.createElement('div')
  tooltip.style.cssText = `
    width: 200px;
    height: auto;
    position: fixed;
    display: none;
    padding: 8px;
    box-sizing: border-box;
    font-size: 12px;
    text-align: left;
    pointer-events: none;
    border: 1px solid #2196F3;
    border-radius: 4px;
    background: white;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  `
  
  // Append to global tooltip root instead of chart container
  const tooltipRoot = document.getElementById('tooltip-root')
  if (tooltipRoot) {
    tooltipRoot.appendChild(tooltip)
  } else {
    console.warn('tooltip-root not found, appending to body')
    document.body.appendChild(tooltip)
  }
  
  return tooltip
}

export const formatDateTime = (dateStr) => {
  let formattedDate = dateStr;
  try {
    let date;
    if (typeof dateStr === 'number') {
      // Handle Unix timestamp (seconds) - use UTC to match chart axis
      date = new Date(dateStr * 1000);
    } else if (typeof dateStr === 'string') {
      // Handle string dates
      if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        // Date-only string - no timezone conversion needed
        const parts = dateStr.split('-');
        formattedDate = new Date(parts[0], parts[1] - 1, parts[2]).toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          timeZone: 'UTC'
        });
        return formattedDate;
      } else {
        date = new Date(dateStr);
      }
    }
    
    if (date && !isNaN(date.getTime())) {
      // Use UTC formatting to match chart axis display
      const hasTime = date.getUTCHours() !== 0 || date.getUTCMinutes() !== 0 || date.getUTCSeconds() !== 0;
      
      if (hasTime) {
        formattedDate = date.toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          timeZone: 'UTC'
        }) + ' ' + date.toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
          timeZone: 'UTC'
        });
      } else {
        formattedDate = date.toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          timeZone: 'UTC'
        });
      }
    }
  } catch (e) {
    // Keep original if parsing fails
    console.warn('Date parsing failed:', e);
  }
  return formattedDate;
}

export const createTooltipHeader = (dateStr) => {
  const formattedDate = formatDateTime(dateStr);
  return `<div style="color: #2196F3; font-weight: 700; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e0e0e0; font-size: 13px; background: #f8f9ff; padding: 6px; border-radius: 3px;">🕒 ${formattedDate}</div>`;
}

export const createTooltipRow = (icon, label, value, color = '#666') => {
  return `<div style="color: ${color}; margin: 2px 0;">${icon} <span style="font-weight: 400;">${label}:</span> <span style="font-weight: 600;">${value}</span></div>`;
}

export const createPriceValue = (price) => {
  return `$${price?.toFixed(2) || 'N/A'}`;
}

export const createEquityValue = (value) => {
  return `$${value ? value.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : 'N/A'}`;
}

export const createPositionValue = (value) => {
  return value?.toFixed(2) || 'N/A';
}

export const createChangeValue = (changePercent) => {
  const color = parseFloat(changePercent) >= 0 ? '#4CAF50' : '#F44336';
  return `<div style="color: ${color}; font-weight: 600; margin: 2px 0;">📈 Change: ${changePercent}%</div>`;
}

export const createTradesHeader = (tradeCount) => {
  const headerStyle = "font-weight: 600; margin: 4px 0 2px 0; padding: 2px 4px; background: #f5f5f5; border-radius: 2px; font-size: 11px; color: #333;";
  return `<div style="${headerStyle}">📊 Trades (${tradeCount}):</div>`;
}

export const createIndividualTradeInfo = (trade) => {
  const side = trade.order_side?.toUpperCase() || 'UNKNOWN';
  const sideColor = side === 'BUY' ? '#4CAF50' : '#F44336';
  const sideIcon = side === 'BUY' ? '📈' : '📉';
  const price = trade.last_px || 0;
  const quantity = trade.last_qty || 0;
  const time = trade.ts_event || '';
  
  // Format time to show just HH:MM:SS if it's a datetime
  let timeStr = '';
  try {
    const date = new Date(time);
    if (!isNaN(date.getTime())) {
      timeStr = date.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit',
        hour12: false
      });
    }
  } catch (e) {
    timeStr = String(time).slice(-8); // Last 8 chars as fallback
  }
  
  return `<div style="display: flex; justify-content: space-between; align-items: center; margin: 1px 0; font-size: 11px; color: ${sideColor};">
    <span>${sideIcon} ${side}</span>
    <span style="font-weight: 600;">${quantity} @ $${Number(price).toFixed(2)}</span>
    <span style="color: #999; font-size: 10px;">${timeStr}</span>
  </div>`;
}

export const createTradesList = (trades) => {
  if (!trades || trades.length === 0) {
    return '';
  }
  
  const tradesHtml = trades.map(trade => createIndividualTradeInfo(trade)).join('');
  const totalTrades = trades.length;
  
  return `${createTradesHeader(totalTrades)}
          <div style="max-height: 120px; overflow-y: auto; margin: 2px 0;">${tradesHtml}</div>`;
}

export const positionTooltip = (tooltip, param, container, chart = null) => {
  const toolTipWidth = 200
  const toolTipMargin = 25  // Increased margin to prevent overlap with crosshair

  // Get actual tooltip height for better positioning
  const toolTipHeight = tooltip.offsetHeight || 120

  // Get container's position in viewport - recalculated on every call to handle window movement
  const containerRect = container.getBoundingClientRect()

  // Get actual left price scale width from chart API
  let leftPriceScaleWidth = 0
  if (chart) {
    try {
      leftPriceScaleWidth = chart.priceScale('left').width() || 0
    } catch (e) {
      leftPriceScaleWidth = 0
    }
  }
  
  // Calculate position relative to container, then convert to viewport coordinates
  // param.point.x is relative to the entire container including price scales
  let left = param.point.x + toolTipMargin + leftPriceScaleWidth
  let top = param.point.y - toolTipHeight / 2 // Center vertically on crosshair

  // Prevent tooltip from going off the right edge of container
  if (left + toolTipWidth > container.clientWidth) {
    // Flip to left side, accounting for left price scale
    left = param.point.x  + leftPriceScaleWidth - toolTipWidth - toolTipMargin
  }

  // Prevent tooltip from going off the bottom edge of the container
  if (top + toolTipHeight > container.clientHeight) {
    top = container.clientHeight - toolTipHeight - toolTipMargin
  }

  // Ensure tooltip doesn't go off the top edge
  if (top < 0) {
    top = toolTipMargin
  }

  // Convert to viewport coordinates by adding container's position
  const viewportLeft = containerRect.left + left
  const viewportTop = containerRect.top + top

  // Apply viewport coordinates (tooltip uses position: fixed)
  tooltip.style.left = viewportLeft + 'px'
  tooltip.style.top = viewportTop + 'px'
}

export const createCrosshairMoveHandler = (tooltip, container, contentGenerator, chart = null) => {
  return (param) => {
    if (!param || !param.time || param.point.x < 0 || param.point.x > container.clientWidth || param.point.y < 0 || param.point.y > container.clientHeight) {
      tooltip.style.display = 'none'
      return
    }

    tooltip.style.display = 'block'
    
    // Generate content using the provided content generator function
    const content = contentGenerator(param)
    tooltip.innerHTML = content

    // Force a reflow to ensure offsetHeight is available
    tooltip.offsetHeight

    // Position the tooltip
    positionTooltip(tooltip, param, container, chart)
  }
}
