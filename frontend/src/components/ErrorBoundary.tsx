"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("[ErrorBoundary]", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="min-h-screen flex items-center justify-center bg-[var(--bg-page)] p-6">
          <div className="max-w-md w-full card p-8 text-center">
            <div className="text-5xl mb-4">⚠️</div>
            <h2 className="text-xl font-bold text-[var(--text-primary)] mb-2">页面出现错误</h2>
            <p className="text-[var(--text-secondary)] text-sm mb-6">
              {this.state.error?.message || "发生了一个意外错误"}
            </p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={this.handleReset}
                className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors text-sm"
              >
                重试
              </button>
              <button
                onClick={() => (window.location.href = "/dashboard")}
                className="px-4 py-2 border border-[var(--border-default)] bg-white hover:bg-[var(--bg-surface)] text-[var(--text-secondary)] rounded-lg transition-colors text-sm"
              >
                返回首页
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
