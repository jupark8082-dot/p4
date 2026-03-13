import React, { Component, StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, info: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    this.setState({ error, info });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', color: '#ff6b6b', backgroundColor: '#1a1d23', height: '100vh', width: '100vw', fontFamily: 'monospace', overflow: 'auto' }}>
          <h2>React Runtime Error:</h2>
          <pre style={{ whiteSpace: 'pre-wrap', marginBottom: '20px' }}>{this.state.error && this.state.error.toString()}</pre>
          <h3>Component Stack:</h3>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{this.state.info && this.state.info.componentStack}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
