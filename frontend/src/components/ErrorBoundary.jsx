import React from "react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    console.error("[ErrorBoundary]", error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-4 border rounded bg-red-50 text-red-800">
          <div className="font-semibold">Something went wrong.</div>
          <pre className="text-xs whitespace-pre-wrap mt-2">
            {String(this.state.error)}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}
