import axios from 'axios'

const api = axios.create({
  baseURL: process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001',
  timeout: 10000,
})

export const fetchBacktestData = async () => {
  try {
    const [metricsRes, equityRes, priceRes, tradeMarkersRes, positionsRes, customIndicatorsRes, tradesLookupRes] = await Promise.all([
      api.get('/api/metrics'),
      api.get('/api/equity-curve'),
      api.get('/api/price-data'),
      api.get('/api/trade-markers'),
      api.get('/api/positions'),
      api.get('/api/custom-indicators'),
      api.get('/api/trades-by-time-slot')
    ])

    // Check for errors in responses
    const responses = [metricsRes, equityRes, priceRes, tradeMarkersRes, positionsRes, customIndicatorsRes, tradesLookupRes]
    for (const res of responses) {
      if (res.data.error) {
        throw new Error(`API Error: ${res.data.error}`)
      }
    }

    return {
      metrics: metricsRes.data,
      equityData: equityRes.data,
      priceData: priceRes.data,
      tradeMarkersData: tradeMarkersRes.data,
      tradesLookup: tradesLookupRes.data,
      positionsData: positionsRes.data,
      customIndicators: customIndicatorsRes.data,
    }
  } catch (error) {
    console.error('API Error:', error)
    throw new Error(
      error.response?.data?.error || 
      error.message || 
      'Failed to fetch backtest data'
    )
  }
}

export default api
