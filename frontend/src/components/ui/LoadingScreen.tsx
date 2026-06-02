export default function LoadingScreen() {
  return (
    <div className="fixed inset-0 bg-dark-bg flex items-center justify-center z-50">
      <div className="flex flex-col items-center gap-4">
        <div className="relative">
          <div className="w-12 h-12 border-2 border-primary-500/20 rounded-full" />
          <div className="absolute inset-0 w-12 h-12 border-2 border-transparent border-t-primary-500 rounded-full animate-spin" />
        </div>
        <span className="text-sm text-dark-muted">正在加载...</span>
      </div>
    </div>
  );
}
