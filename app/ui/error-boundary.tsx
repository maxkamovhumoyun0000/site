import React, { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children?: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught render error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="flex flex-col items-center justify-center min-h-screen p-6 bg-surface dark:bg-navy-950 text-center">
          <h2 className="text-2xl font-black text-navy-900 dark:text-white mb-2">Kutilmagan xatolik yuz berdi</h2>
          <p className="text-ink-600 dark:text-navy-300 mb-6 max-w-sm">
            Ilovani yuklashda muammo yuzaga keldi. Bu internet tezligi pastligi yoki ma'lumotlar to'liq kelmaganligi sababli bo'lishi mumkin.
          </p>
          <button 
            className="btn btn-primary"
            onClick={() => window.location.reload()}
          >
            Sahifani yangilash
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
