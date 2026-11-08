import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

type Props = { children: ReactNode }
type State = { error: Error | null }

/** A render crash must be visible, never a blank screen. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[Course RAG] render error:', error.message, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="crash">
          <h2>Something went wrong while rendering</h2>
          <p className="crash-detail">{this.state.error.message}</p>
          <p>Reload the app to continue. Details are in the browser console.</p>
          <button className="primary crash-reload" type="button"
            onClick={() => window.location.reload()}>
            Reload app
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
