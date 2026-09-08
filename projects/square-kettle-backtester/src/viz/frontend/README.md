# Backtest Visualizer Frontend

A modern React frontend for visualizing backtest results using TradingView's lightweight-charts library.

## Features

- **Modern React Architecture**: Component-based design with hooks and functional components
- **Interactive Charts**: Professional financial charts with hover tooltips
- **Responsive Design**: Mobile-friendly layout that works on all screen sizes
- **Real-time Data**: Fetches data from Flask backend API
- **Error Handling**: Graceful error states and loading indicators
- **TypeScript Ready**: Easy to convert to TypeScript if needed

## Prerequisites

- Node.js 16+ and npm
- Python Flask backend running on port 5000

## Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Start development server**:
   ```bash
   npm run dev
   ```

3. **Access the application**:
   Open http://localhost:3000 in your browser

## Development

### Available Scripts

- `npm run dev` - Start development server with hot reload
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

### Project Structure

```
src/
├── components/          # React components
│   ├── EquityChart.jsx  # Equity curve with positions
│   ├── MetricsGrid.jsx  # Performance metrics display
│   └── PriceChart.jsx   # Price action with trades
├── utils/
│   └── api.js          # API client for Flask backend
├── App.jsx             # Main application component
├── App.css             # Global styles
└── main.jsx           # React entry point
```

### Adding New Charts

1. Create a new component in `src/components/`
2. Use lightweight-charts library for chart creation
3. Follow the existing pattern for tooltips and responsive design
4. Import and use in `App.jsx`

### Styling

The application uses CSS modules with a design system based on:
- Material Design color palette
- Apple system fonts
- Responsive grid layouts
- CSS custom properties for theming

## Building for Production

1. **Build the application**:
   ```bash
   npm run build
   ```

2. **Files are built to `../static/dist/`** and can be served by the Flask backend

## API Integration

The frontend communicates with the Flask backend through these endpoints:

- `GET /api/equity-curve` - Portfolio equity over time
- `GET /api/trades` - Trade markers and details  
- `GET /api/price-data` - OHLC price data
- `GET /api/positions` - Position size data
- `GET /api/metrics` - Performance metrics

## Browser Support

- Chrome/Edge 88+
- Firefox 78+
- Safari 14+
- Mobile browsers

## Troubleshooting

### Development Issues

- **CORS errors**: Make sure Flask backend is running on port 5000
- **Module not found**: Run `npm install` to install dependencies
- **Charts not loading**: Check browser console for lightweight-charts errors

### Production Issues

- **API calls failing**: Update `baseURL` in `src/utils/api.js`
- **Build errors**: Check Node.js version (requires 16+)
