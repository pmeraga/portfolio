// Extensible metrics configuration
// Add new metrics here to automatically display them

export const METRICS_CONFIG = [
  {
    id: 'total_return',
    label: 'Total Return',
    key: 'total_return',
    formatValue: (value) => value || 'N/A',
    getColorClass: (value) => {
      if (typeof value === 'string') {
        if (value.startsWith('+') || (value.includes('%') && !value.startsWith('-'))) {
          return 'positive'
        }
        if (value.startsWith('-')) {
          return 'negative'
        }
      }
      return ''
    }
  },
  {
    id: 'sharpe_ratio',
    label: 'Sharpe Ratio',
    key: 'sharpe_ratio',
    formatValue: (value) => value || 'N/A',
    getColorClass: () => ''
  },
  {
    id: 'max_drawdown',
    label: 'Max Drawdown',
    key: 'max_drawdown',
    formatValue: (value) => value || 'N/A',
    getColorClass: () => 'negative'
  },
  {
    id: 'win_rate',
    label: 'Win Rate',
    key: 'win_rate',
    formatValue: (value) => value || 'N/A',
    getColorClass: () => ''
  },
  {
    id: 'profit_factor',
    label: 'Profit Factor',
    key: 'profit_factor',
    formatValue: (value) => value || 'N/A',
    getColorClass: () => ''
  },
  {
    id: 'total_trades',
    label: 'Total Trades',
    key: 'total_trades',
    formatValue: (value) => value || 'N/A',
    getColorClass: () => ''
  }
]

/**
 * Helper function to get metric items from metrics data
 * @param {Object} metrics - The metrics data object
 * @returns {Array} Array of metric items with formatted values and classes
 */
export const getMetricItems = (metrics) => {
  if (!metrics) return []
  
  return METRICS_CONFIG.map(config => ({
    id: config.id,
    label: config.label,
    value: config.formatValue(metrics[config.key]),
    valueClass: config.getColorClass(metrics[config.key])
  }))
}
