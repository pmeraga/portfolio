/**
 * Utility functions for time format conversion
 */

/**
 * Convert time strings to lightweight-charts format (Unix timestamp or date string)
 * Treats all times as UTC to avoid timezone issues
 * 
 * @param {string} timeString - Time string in various formats
 * @returns {string|number} - Unix timestamp (seconds) or date string for daily data
 */
export const normalizeTimeFormat = (timeString) => {
  try {
    // If it's already a date-only string (YYYY-MM-DD), use as-is
    if (/^\d{4}-\d{2}-\d{2}$/.test(timeString)) {
      return timeString
    }
    
    // If it has time components (YYYY-MM-DD HH:MM:SS), convert to Unix timestamp as UTC
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$/.test(timeString)) {
      const [datePart, timePart] = timeString.split(' ')
      const [year, month, day] = datePart.split('-').map(Number)
      const [hour, minute, second = 0] = timePart.split(':').map(Number)
      return Math.floor(Date.UTC(year, month - 1, day, hour, minute, second) / 1000)
    }
    
    // Try to parse as date and convert to Unix timestamp (treat as UTC)
    const date = new Date(timeString + 'Z')
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
